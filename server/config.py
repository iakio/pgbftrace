import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Application configuration settings"""
    
    # PostgreSQL settings
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_db: str = "postgres"
    
    # bpftrace settings
    bpftrace_path: str = "/usr/bin/bpftrace"
    bpftrace_script: str = "/app/server/trace_buffer_read.bt"
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    static_dir: str = "../static"
    
    # WebSocket settings
    websocket_timeout: int = 3600
    
    # Process management
    process_terminate_timeout: float = 5.0
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables"""
        return cls(
            postgres_host=os.getenv("POSTGRES_HOST", cls.postgres_host),
            postgres_port=int(os.getenv("POSTGRES_PORT", str(cls.postgres_port))),
            postgres_user=os.getenv("POSTGRES_USER", cls.postgres_user),
            postgres_db=os.getenv("POSTGRES_DB", cls.postgres_db),
            bpftrace_path=os.getenv("BPFTRACE_PATH", cls.bpftrace_path),
            bpftrace_script=os.getenv("BPFTRACE_SCRIPT", cls.bpftrace_script),
            host=os.getenv("SERVER_HOST", cls.host),
            port=int(os.getenv("SERVER_PORT", str(cls.port))),
            static_dir=os.getenv("STATIC_DIR", cls.static_dir),
            websocket_timeout=int(os.getenv("WEBSOCKET_TIMEOUT", str(cls.websocket_timeout))),
            process_terminate_timeout=float(os.getenv("PROCESS_TERMINATE_TIMEOUT", str(cls.process_terminate_timeout)))
        )
    
    @property
    def postgres_dsn(self) -> str:
        """PostgreSQL connection string"""
        return f"dbname='{self.postgres_db}' user='{self.postgres_user}' host='{self.postgres_host}' port='{self.postgres_port}'"