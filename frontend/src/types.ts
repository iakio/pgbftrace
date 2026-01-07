export interface RelationInfo {
  oid: number;
  relname: string;
  total_blocks: number;
  relfilenode: number;
  relkind: string;
}

export interface TraceEvent {
  relfilenode: number;
  block: number;
  hit: number;
}

export interface DrawInfo {
  blocksStartY: number;
  blocksPerRow: number;
}

export interface RelationWithDrawInfo extends RelationInfo {
  drawInfo?: DrawInfo;
}
