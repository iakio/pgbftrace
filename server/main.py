import asyncio
import json
import psycopg2
import struct # For packing binary data
import signal
import sys
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import List, Dict, Any, Optional

app = FastAPI()

# 静的ファイルをホストするディレクトリ
app.mount("/static", StaticFiles(directory="../static"), name="static")

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"Client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"Client disconnected. Total clients: {len(self.active_connections)}")

    async def disconnect_all(self):
        """全てのWebSocket接続を安全に閉じる"""
        connections_to_close = list(self.active_connections)
        for connection in connections_to_close:
            try:
                await connection.close(code=1001, reason="Server shutting down")
            except Exception as e:
                print(f"Error closing WebSocket connection: {e}")
        self.active_connections.clear()
        print("All WebSocket connections closed.")

    async def broadcast_bytes(self, message: bytes):
        if not self.active_connections:
            return
            
        disconnected_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_bytes(message)
            except Exception as e:
                # Handle potential connection errors during broadcast
                print(f"Failed to send to a client, marking for removal: {e}")
                disconnected_connections.append(connection)
        
        # Clean up failed connections after the loop
        for connection in disconnected_connections:
            self.disconnect(connection)

manager = ConnectionManager()

# グローバル変数としてPostgreSQLのFILENODE->名前マップをキャッシュする
relation_filenode_to_name: Dict[int, str] = {}
relation_filenode_to_info: Dict[int, Dict[str, Any]] = {} # relfilenode -> complete info (oid, name, blocks)

# グローバルなbpftraceプロセス参照
bpftrace_process: Optional[asyncio.subprocess.Process] = None

def fetch_and_cache_relations():
    """
    PostgreSQLからリレーション情報を取得し、キャッシュを更新しつつ、
    APIレスポンス用のリストを返す。
    """
    global relation_filenode_to_name, relation_filenode_to_info
    conn = None
    relations_for_api = []
    temp_filenode_map = {}
    temp_filenode_info_map = {}
    try:
        conn = psycopg2.connect("dbname='postgres' user='postgres' host='localhost' port='5432'")
        cur = conn.cursor()
        cur.execute("""
            SELECT c.oid, c.relname, c.relpages, c.relfilenode
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind IN ('r', 'i', 'p', 'I')
              AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast');
        """)
        
        results = cur.fetchall()
        cur.close()

        for oid, relname, relpages, relfilenode in results:
            if relfilenode == 0: # relfilenodeが0の場合は物理ファイルがないのでスキップ
                continue

            # APIレスポンス用のデータを作成
            total_blocks = relpages if relpages > 0 else 1 
            info = {"oid": oid, "relname": relname, "total_blocks": total_blocks, "relfilenode": relfilenode}
            relations_for_api.append(info)
            
            # キャッシュ用のデータを作成
            temp_filenode_map[relfilenode] = relname
            temp_filenode_info_map[relfilenode] = info

        relation_filenode_to_name = temp_filenode_map # キャッシュをアトミックに更新
        relation_filenode_to_info = temp_filenode_info_map
        print(f"Fetched and cached {len(relations_for_api)} relations. Cached filenodes: {list(relation_filenode_to_name.keys())}") # ★ログ追加★

    except Exception as e:
        print(f"Error fetching and caching relations: {e}")
    finally:
        if conn:
            conn.close()
    
    return relations_for_api

async def run_bpftrace():
    """
    bpftraceをサブプロセスとして実行し、その出力をバイナリ形式でWebSocketにブロードキャストする
    """
    global bpftrace_process
    
    bpftrace_path = "/usr/bin/bpftrace"
    script_path = "/app/server/trace_buffer_read.bt"
    command = [bpftrace_path, script_path]

    try:
        bpftrace_process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        print(f"bpftrace process started with PID: {bpftrace_process.pid}")

        async def log_stderr():
            try:
                async for line in bpftrace_process.stderr:
                    print(f"bpftrace stderr: {line.decode().strip()}")
            except Exception as e:
                print(f"Error reading bpftrace stderr: {e}")

        async def process_stdout():
            try:
                async for line in bpftrace_process.stdout:
                    try:
                        line_str = line.decode().strip()
                        # 16文字の16進数固定長フォーマットをチェック
                        if len(line_str) == 16 and all(c in '0123456789abcdef' for c in line_str.lower()):
                            try:
                                relfilenode = int(line_str[:8], 16)  # 最初の8文字
                                block = int(line_str[8:], 16)        # 次の8文字

                                print(f"bpftrace parsed: relfilenode={relfilenode}, block={block}")
                                
                                if relfilenode in relation_filenode_to_name:
                                    packed_data = struct.pack('!II', relfilenode, block)
                                    await manager.broadcast_bytes(packed_data)
                                else:
                                    print(f"bpftrace filtered: filenode={relfilenode} not in cache.")

                            except ValueError as e:
                                print(f"bpftrace hex parsing error for line '{line_str}': {e}")

                    except Exception as e:
                        print(f"Error processing bpftrace output line: {e}")
            except Exception as e:
                print(f"Error reading bpftrace stdout: {e}")
        
        # 両方のタスクを並行実行し、プロセス終了を待機
        await asyncio.gather(
            log_stderr(),
            process_stdout(),
            bpftrace_process.wait()
        )
        
        print(f"bpftrace process finished with return code: {bpftrace_process.returncode}")
        
    except Exception as e:
        print(f"Error running bpftrace: {e}")
    finally:
        # クリーンアップ
        if bpftrace_process and bpftrace_process.returncode is None:
            print("Terminating bpftrace process...")
            bpftrace_process.terminate()
            try:
                await asyncio.wait_for(bpftrace_process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                print("Force killing bpftrace process...")
                bpftrace_process.kill()
                await bpftrace_process.wait()
        bpftrace_process = None

async def cleanup_resources():
    """アプリケーション終了時のクリーンアップ処理"""
    global bpftrace_process
    
    print("Starting cleanup process...")
    
    # WebSocket接続をクローズ
    await manager.disconnect_all()
    
    # bpftraceプロセスを終了
    if bpftrace_process and bpftrace_process.returncode is None:
        print("Terminating bpftrace process...")
        bpftrace_process.terminate()
        try:
            await asyncio.wait_for(bpftrace_process.wait(), timeout=5.0)
            print("bpftrace process terminated gracefully")
        except asyncio.TimeoutError:
            print("Force killing bpftrace process...")
            bpftrace_process.kill()
            await bpftrace_process.wait()
            print("bpftrace process killed")
    
    print("Cleanup completed.")

def signal_handler():
    """シグナルハンドラー"""
    print("Received termination signal, initiating graceful shutdown...")
    asyncio.create_task(cleanup_resources())

@app.on_event("startup")
async def startup_event():
    # シグナルハンドラーの設定
    for sig in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, lambda s, f: signal_handler())
    
    await asyncio.sleep(5)
    fetch_and_cache_relations() # 起動時に一度キャッシュを作成
    asyncio.create_task(run_bpftrace())

@app.on_event("shutdown")
async def shutdown_event():
    """FastAPI終了時のクリーンアップ"""
    await cleanup_resources()

@app.get("/")
async def read_root():
    with open("../static/index.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content, status_code=200)

@app.get("/api/relations", response_class=JSONResponse)
def get_relations():
    """HTTP GETエンドポイントでリレーション情報を返し、同時にOIDマップも更新する"""
    return fetch_and_cache_relations()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 接続を維持する
            await asyncio.sleep(3600)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected")

