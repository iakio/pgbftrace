import asyncio
import json
import psycopg2
import struct # For packing binary data
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import List, Dict, Any

app = FastAPI()

# 静的ファイルをホストするディレクトリ
app.mount("/static", StaticFiles(directory="../static"), name="static")

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"Client disconnected. Total clients: {len(self.active_connections)}")


    async def broadcast_bytes(self, message: bytes):
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

# グローバル変数としてPostgreSQLのOID->名前マップをキャッシュする
relation_oid_to_name: Dict[int, str] = {}

def fetch_and_cache_relations():
    """
    PostgreSQLからリレーション情報を取得し、キャッシュを更新しつつ、
    APIレスポンス用のリストを返す。
    """
    global relation_oid_to_name
    conn = None
    relations_for_api = []
    temp_oid_map = {}
    try:
        conn = psycopg2.connect("dbname='postgres' user='postgres' host='localhost' port='5432'")
        cur = conn.cursor()
        cur.execute("""
            SELECT c.oid, c.relname, c.relpages
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind IN ('r', 'i', 'p', 'I')
              AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast');
        """)
        
        results = cur.fetchall()
        cur.close()

        for oid, relname, relpages in results:
            # APIレスポンス用のデータを作成
            total_blocks = relpages if relpages > 0 else 1 
            relations_for_api.append({"oid": oid, "relname": relname, "total_blocks": total_blocks})
            
            # キャッシュ用のデータを作成
            temp_oid_map[oid] = relname

        relation_oid_to_name = temp_oid_map # キャッシュをアトミックに更新
        print(f"Fetched and cached {len(relations_for_api)} relations.")

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
    bpftrace_path = "/usr/bin/bpftrace"
    script_path = "/app/server/trace_buffer_read.bt"
    command = [bpftrace_path, script_path]

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    print("bpftrace process starting...")

    async def log_stderr():
        async for line in process.stderr:
            print(f"bpftrace stderr: {line.decode().strip()}")

    async def process_stdout():
        async for line in process.stdout:
            try:
                line_str = line.decode().strip()
                if not line_str.startswith("oid:"):
                    continue

                parts = line_str.split()
                oid_part = parts[0].split(':')
                block_part = parts[1].split(':')

                if len(oid_part) == 2 and len(block_part) == 2:
                    oid = int(oid_part[1])
                    
                    if oid in relation_oid_to_name:
                        block = int(block_part[1])
                        packed_data = struct.pack('!II', oid, block)
                        await manager.broadcast_bytes(packed_data)

            except Exception as e:
                print(f"Error processing bpftrace output: {e}")
    
    await asyncio.gather(log_stderr(), process_stdout())
    print("bpftrace process finished.")

@app.on_event("startup")
async def startup_event():
    await asyncio.sleep(5)
    fetch_and_cache_relations() # 起動時に一度キャッシュを作成
    asyncio.create_task(run_bpftrace())

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

