import asyncio
from typing import Optional, AsyncGenerator
from models import TraceEvent
from config import Config


class BpftraceManager:
    """Manages bpftrace process lifecycle and output parsing"""
    
    def __init__(self, config: Config):
        self.config = config
        self._process: Optional[asyncio.subprocess.Process] = None
    
    async def start_process(self) -> None:
        """Start bpftrace process"""
        if self._process is not None:
            raise RuntimeError("bpftrace process is already running")
        
        command = [self.config.bpftrace_path, self.config.bpftrace_script]
        
        try:
            self._process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            print(f"bpftrace process started with PID: {self._process.pid}")
            
        except Exception as e:
            print(f"Error starting bpftrace process: {e}")
            self._process = None
            raise
    
    async def stop_process(self) -> None:
        """Stop bpftrace process gracefully"""
        if self._process is None or self._process.returncode is not None:
            return
        
        print("Terminating bpftrace process...")
        self._process.terminate()
        
        try:
            await asyncio.wait_for(
                self._process.wait(), 
                timeout=self.config.process_terminate_timeout
            )
            print("bpftrace process terminated gracefully")
        except asyncio.TimeoutError:
            print("Force killing bpftrace process...")
            self._process.kill()
            await self._process.wait()
            print("bpftrace process killed")
        finally:
            self._process = None
    
    async def read_stderr(self) -> None:
        """Read and log stderr output"""
        if self._process is None or self._process.stderr is None:
            return
        
        try:
            async for line in self._process.stderr:
                print(f"bpftrace stderr: {line.decode().strip()}")
        except Exception as e:
            print(f"Error reading bpftrace stderr: {e}")
    
    async def read_trace_events(self) -> AsyncGenerator[TraceEvent, None]:
        """Read and parse stdout into TraceEvent objects"""
        if self._process is None or self._process.stdout is None:
            return
        
        try:
            async for line in self._process.stdout:
                try:
                    line_str = line.decode().strip()
                    trace_event = TraceEvent.from_hex_string(line_str)
                    
                    if trace_event is not None:
                        print(f"bpftrace parsed: relfilenode={trace_event.relfilenode}, "
                              f"block={trace_event.block}")
                        yield trace_event
                    # Skip invalid lines silently
                    
                except Exception as e:
                    print(f"Error processing bpftrace output line: {e}")
                    
        except Exception as e:
            print(f"Error reading bpftrace stdout: {e}")
    
    async def run_with_handlers(self, trace_handler) -> None:
        """
        Run bpftrace process with stderr logging and trace event handling
        
        Args:
            trace_handler: async function that takes TraceEvent and processes it
        """
        if self._process is None:
            raise RuntimeError("bpftrace process not started")
        
        async def handle_traces():
            async for trace_event in self.read_trace_events():
                await trace_handler(trace_event)
        
        try:
            await asyncio.gather(
                self.read_stderr(),
                handle_traces(),
                self._process.wait()
            )
            print(f"bpftrace process finished with return code: {self._process.returncode}")
            
        except Exception as e:
            print(f"Error running bpftrace: {e}")
        finally:
            await self.stop_process()
    
    @property
    def is_running(self) -> bool:
        """Check if bpftrace process is currently running"""
        return (self._process is not None and 
                self._process.returncode is None)