import { useEffect, useRef, forwardRef, useImperativeHandle } from 'react';
import type { RelationInfo } from '../types';
import { initializeCanvas, type DrawInfo } from '../utils/canvas-utils';

interface TableCanvasProps {
  relation: RelationInfo;
  onInitialized?: (relfilenode: number, drawInfo: DrawInfo) => void;
}

const CANVAS_WIDTH = 400;

export const TableCanvas = forwardRef<HTMLCanvasElement, TableCanvasProps>(
  ({ relation, onInitialized }, ref) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useImperativeHandle(ref, () => canvasRef.current!);

    // Initialize canvas once
    useEffect(() => {
      const canvas = canvasRef.current;
      if (!canvas) return;

      const drawInfo = initializeCanvas(canvas, relation.total_blocks, CANVAS_WIDTH);

      // Notify parent about draw info
      onInitialized?.(relation.relfilenode, drawInfo);
    }, [relation, onInitialized]);

    return (
      <div className="table-canvas-wrapper">
        <div className="table-header">
          <strong>{relation.relname}</strong> (OID: {relation.oid}, Blocks: {relation.total_blocks})
        </div>
        <canvas ref={canvasRef} width={CANVAS_WIDTH} />
      </div>
    );
  }
);

TableCanvas.displayName = 'TableCanvas';
