import asyncio
import signal
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import Config
from database import RelationCache
from bpftrace_manager import BpftraceManager
from websocket_manager import ConnectionManager
from models import TraceEvent

# Initialize configuration
config = Config.from_env()

# Initialize FastAPI app
app = FastAPI()
app.mount("/static", StaticFiles(directory=config.static_dir), name="static")

# Initialize managers
websocket_manager = ConnectionManager()
relation_cache = RelationCache(config)
bpftrace_manager = BpftraceManager(config)


async def handle_trace_event(trace_event: TraceEvent) -> None:
    """Handle incoming trace events from bpftrace"""
    if relation_cache.is_filenode_cached(trace_event.relfilenode):
        await websocket_manager.broadcast_trace_event(trace_event)
    else:
        print(f"bpftrace filtered: filenode={trace_event.relfilenode} not in cache.")


async def run_bpftrace():
    """Start and manage bpftrace process"""
    try:
        await bpftrace_manager.start_process()
        await bpftrace_manager.run_with_handlers(handle_trace_event)
    except Exception as e:
        print(f"Error in bpftrace management: {e}")


async def cleanup_resources():
    """Application cleanup on shutdown"""
    print("Starting cleanup process...")
    
    # Close WebSocket connections
    await websocket_manager.disconnect_all()
    
    # Stop bpftrace process
    await bpftrace_manager.stop_process()
    
    print("Cleanup completed.")


def signal_handler():
    """Handle termination signals"""
    print("Received termination signal, initiating graceful shutdown...")
    asyncio.create_task(cleanup_resources())


@app.on_event("startup")
async def startup_event():
    """Application startup initialization"""
    # Setup signal handlers
    for sig in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, lambda s, f: signal_handler())
    
    # Wait for PostgreSQL to be ready
    await asyncio.sleep(5)
    
    # Initialize relation cache
    relation_cache.fetch_and_cache_relations()
    
    # Start bpftrace process
    asyncio.create_task(run_bpftrace())


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown cleanup"""
    await cleanup_resources()


@app.get("/")
async def read_root():
    """Serve main HTML page"""
    with open(f"{config.static_dir}/index.html", "r") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content, status_code=200)


@app.get("/api/relations", response_class=JSONResponse)
def get_relations():
    """Get relation information and update cache"""
    relations = relation_cache.fetch_and_cache_relations()
    return [relation.to_dict() for relation in relations]


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for trace data streaming"""
    await websocket_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await asyncio.sleep(config.websocket_timeout)
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
        print("Client disconnected")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.host, port=config.port)