import psycopg2
from typing import List, Dict, Optional
from models import RelationInfo
from config import Config


class RelationCache:
    """Manages PostgreSQL relation information and caching"""
    
    def __init__(self, config: Config):
        self.config = config
        self._filenode_to_name: Dict[int, str] = {}
        self._filenode_to_info: Dict[int, RelationInfo] = {}
    
    def fetch_and_cache_relations(self) -> List[RelationInfo]:
        """
        Fetch relation information from PostgreSQL and update cache
        Returns: List of RelationInfo for API response
        """
        conn = None
        relations_for_api = []
        temp_filenode_map = {}
        temp_filenode_info_map = {}
        
        try:
            conn = psycopg2.connect(self.config.postgres_dsn)
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
                if relfilenode == 0:  # Skip relations without physical files
                    continue

                total_blocks = relpages if relpages > 0 else 1 
                relation_info = RelationInfo(
                    oid=oid,
                    relname=relname,
                    total_blocks=total_blocks,
                    relfilenode=relfilenode
                )
                
                relations_for_api.append(relation_info)
                temp_filenode_map[relfilenode] = relname
                temp_filenode_info_map[relfilenode] = relation_info

            # Atomic cache update
            self._filenode_to_name = temp_filenode_map
            self._filenode_to_info = temp_filenode_info_map
            
            print(f"Fetched and cached {len(relations_for_api)} relations. "
                  f"Cached filenodes: {list(self._filenode_to_name.keys())}")

        except Exception as e:
            print(f"Error fetching and caching relations: {e}")
        finally:
            if conn:
                conn.close()
        
        return relations_for_api
    
    def get_cached_relation_name(self, relfilenode: int) -> Optional[str]:
        """Get relation name by relfilenode from cache"""
        return self._filenode_to_name.get(relfilenode)
    
    def get_cached_relation_info(self, relfilenode: int) -> Optional[RelationInfo]:
        """Get full relation info by relfilenode from cache"""
        return self._filenode_to_info.get(relfilenode)
    
    def is_filenode_cached(self, relfilenode: int) -> bool:
        """Check if relfilenode exists in cache"""
        return relfilenode in self._filenode_to_name