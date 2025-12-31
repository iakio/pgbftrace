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

def get_pg_relation_info():
    """PostgreSQLからリレーション情報を取得する"""
    conn = None
    relations = []
    try:
        conn = psycopg2.connect("dbname='postgres' user='postgres' host='localhost' port='5432'")
        cur = conn.cursor()
        cur.execute("""
            SELECT c.oid, c.relname, c.relpages
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind IN ('r', 'i', 'p', 'I')
              AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY c.relname;
        """)
        
        for oid, relname, relpages in cur.fetchall():
            total_blocks = relpages if relpages > 0 else 1 
            relations.append({"oid": oid, "relname": relname, "total_blocks": total_blocks})
        cur.close()
        print(f"Fetched {len(relations)} PostgreSQL relations.")
    except Exception as e:
        print(f"Error connecting to PostgreSQL or fetching relation info: {e}")
    finally:
        if conn:
            conn.close()
    return relations

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
                    block = int(block_part[1])
                    
                    # OIDとBlock Numberを2つの符号なし4バイト整数としてパック
                    packed_data = struct.pack('!II', oid, block) # Network byte order
                    await manager.broadcast_bytes(packed_data)

            except Exception as e:
                print(f"Error processing bpftrace output: {e}")
    
    await asyncio.gather(log_stderr(), process_stdout())
    print("bpftrace process finished.")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bpftrace())

@app.get("/")
async def read_root():
    with open("../static/index.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content, status_code=200)

@app.get("/api/relations", response_class=JSONResponse)
def get_relations():
    """HTTP GETエンドポイントでリレーション情報を返す"""
    relations = get_pg_relation_info()
    return relations

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


