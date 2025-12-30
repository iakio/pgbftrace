import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from typing import List

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
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

async def read_stream(stream, callback):
    while True:
        line = await stream.readline()
        if line:
            callback(line)
        else:
            break

async def run_bpftrace():
    """
    bpftraceをサブプロセスとして実行し、その出力をWebSocketでブロードキャストする
    """
    bpftrace_path = "/usr/bin/bpftrace"
    script_path = "/app/server/trace_buffer_read.bt"
    
    # 注意: bpftraceの実行には管理者権限が必要です。
    # このコンテナは --privileged で実行されていることを前提とします。
    command = [bpftrace_path, script_path]

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    print("bpftrace process starting...")

    def log_stderr(line):
        print(f"bpftrace stderr: {line.decode().strip()}")

    async def process_stdout():
        while process.returncode is None:
            try:
                line = await process.stdout.readline()
                if not line:
                    break
                
                line_str = line.decode().strip()
                if not line_str.startswith("oid:"):
                    continue

                parts = line_str.split()
                oid_part = parts[0].split(':')
                block_part = parts[1].split(':')

                if len(oid_part) == 2 and len(block_part) == 2:
                    data = {
                        "oid": int(oid_part[1]),
                        "block": int(block_part[1])
                    }
                    await manager.broadcast(json.dumps(data))

            except Exception as e:
                print(f"Error reading bpftrace output: {e}")
                break
    
    await asyncio.gather(
        read_stream(process.stderr, log_stderr),
        process_stdout()
    )
    
    print("bpftrace process finished.")

@app.on_event("startup")
async def startup_event():
    # アプリケーション起動時にbpftraceをバックグラウンドで実行
    asyncio.create_task(run_bpftrace())

@app.get("/")
async def read_root():
    with open("../static/index.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content, status_code=200)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # クライアントからのメッセージは受け取らず、サーバーからの送信のみ
        while True:
            await asyncio.sleep(3600) # 接続を維持するための一時的なスリープ
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected")

# 以前の/itemsエンドポイントはデモのため削除（必要なら残しても良い）
# if __name__ == "__main__" ブロックはuvicornから直接起動するため不要


