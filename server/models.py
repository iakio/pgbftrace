from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class RelationInfo:
    """PostgreSQL relation information"""
    oid: int
    relname: str
    total_blocks: int
    relfilenode: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "oid": self.oid,
            "relname": self.relname,
            "total_blocks": self.total_blocks,
            "relfilenode": self.relfilenode
        }


@dataclass
class TraceEvent:
    """BPF trace event data"""
    relfilenode: int
    block: int
    
    @classmethod
    def from_hex_string(cls, hex_str: str) -> Optional["TraceEvent"]:
        """Parse 16-character hex string into TraceEvent"""
        if len(hex_str) != 16 or not all(c in '0123456789abcdef' for c in hex_str.lower()):
            return None
        
        try:
            relfilenode = int(hex_str[:8], 16)
            block = int(hex_str[8:], 16)
            return cls(relfilenode=relfilenode, block=block)
        except ValueError:
            return None