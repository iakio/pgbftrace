import { useEffect, useState, useRef, useCallback } from 'react';
import type { RelationInfo } from './types';
import { useWebSocket } from './hooks/useWebSocket';
import { TableCanvas } from './components/TableCanvas';
import { highlightBlock, type DrawInfo } from './utils/canvas-utils';
import './App.css';

function App() {
  const [relations, setRelations] = useState<RelationInfo[]>([]);
  const [selectedRelations, setSelectedRelations] = useState<Set<number>>(new Set());

  // Canvas management
  const canvasRefs = useRef<Map<number, HTMLCanvasElement>>(new Map());
  const drawInfos = useRef<Map<number, DrawInfo>>(new Map());
  const timeouts = useRef<Map<string, number>>(new Map());  // Key: "relfilenode-block"

  // Handle incoming trace events - Direct canvas manipulation
  const handleTraceEvent = useCallback((traceEvent: { relfilenode: number; block: number }) => {
    const { relfilenode, block } = traceEvent;

    // Only process if relation is selected
    if (!selectedRelations.has(relfilenode)) return;

    const canvas = canvasRefs.current.get(relfilenode);
    const drawInfo = drawInfos.current.get(relfilenode);

    if (!canvas || !drawInfo) return;

    // Create unique key for this specific block
    const blockKey = `${relfilenode}-${block}`;

    // Clear previous timeout for this specific block
    const previousTimeout = timeouts.current.get(blockKey);
    if (previousTimeout !== undefined) {
      clearTimeout(previousTimeout);
    }

    // Highlight block and get cleanup function
    const cleanup = highlightBlock(canvas, block, drawInfo);

    // Schedule cleanup
    const timeoutId = window.setTimeout(() => {
      cleanup();
      timeouts.current.delete(blockKey);
    }, 500);

    timeouts.current.set(blockKey, timeoutId);
  }, [selectedRelations]);

  const wsUrl = `ws://${window.location.host}/ws`;
  const { isConnected } = useWebSocket(wsUrl, { onMessage: handleTraceEvent });

  // Fetch relations on mount
  useEffect(() => {
    fetch('/api/relations')
      .then((res) => res.json())
      .then((data: RelationInfo[]) => {
        setRelations(data);
        // Select all relations by default
        setSelectedRelations(new Set(data.map((r) => r.relfilenode)));
      })
      .catch((err) => console.error('Error fetching relations:', err));
  }, []);

  // Handle canvas initialization
  const handleCanvasInitialized = useCallback((relfilenode: number, drawInfo: DrawInfo) => {
    drawInfos.current.set(relfilenode, drawInfo);
  }, []);

  const toggleRelation = (relfilenode: number) => {
    setSelectedRelations((prev) => {
      const next = new Set(prev);
      if (next.has(relfilenode)) {
        next.delete(relfilenode);
      } else {
        next.add(relfilenode);
      }
      return next;
    });
  };

  const selectedRelationsList = relations.filter((r) =>
    selectedRelations.has(r.relfilenode)
  );

  return (
    <div className="app">
      <header className="app-header">
        <h1>PostgreSQL Buffer Trace Visualizer</h1>
        <div className="connection-status">
          WebSocket: {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
        </div>
      </header>

      <div className="app-content">
        <aside className="sidebar">
          <h2>Tables</h2>
          <div className="table-list">
            {relations.map((relation) => (
              <label key={relation.relfilenode} className="table-item">
                <input
                  type="checkbox"
                  checked={selectedRelations.has(relation.relfilenode)}
                  onChange={() => toggleRelation(relation.relfilenode)}
                />
                <span>{relation.relname}</span>
                <span className="table-blocks">({relation.total_blocks} blocks)</span>
              </label>
            ))}
          </div>
        </aside>

        <main className="canvas-container">
          {selectedRelationsList.map((relation) => (
            <TableCanvas
              key={relation.relfilenode}
              ref={(el) => {
                if (el) {
                  canvasRefs.current.set(relation.relfilenode, el);
                } else {
                  canvasRefs.current.delete(relation.relfilenode);
                }
              }}
              relation={relation}
              onInitialized={handleCanvasInitialized}
            />
          ))}
        </main>
      </div>
    </div>
  );
}

export default App;
