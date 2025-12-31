export interface RelationInfo {
  oid: number;
  relname: string;
  total_blocks: number;
  relfilenode: number;
}

export interface TraceEvent {
  relfilenode: number;
  block: number;
}

export interface DrawInfo {
  blocksStartY: number;
  blocksPerRow: number;
}

export interface RelationWithDrawInfo extends RelationInfo {
  drawInfo?: DrawInfo;
}
