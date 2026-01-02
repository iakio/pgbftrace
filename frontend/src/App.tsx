import { useEffect, useState, useRef, useCallback } from 'react';
import type { RelationInfo } from './types';
import { useWebSocket } from './hooks/useWebSocket';
import { TableCanvas } from './components/TableCanvas';
import { highlightBlock, clearBlock, type DrawInfo } from './utils/canvas-utils';
import './App.css';

function App() {
  const [relations, setRelations] = useState<RelationInfo[]>([]);
  const [selectedRelations, setSelectedRelations] = useState<Set<number>>(new Set());

  // Canvas management
  const canvasRefs = useRef<Map<number, HTMLCanvasElement>>(new Map());
  const drawInfos = useRef<Map<number, DrawInfo>>(new Map());
  const highlightedBlocks = useRef<Map<string, number>>(new Map()); // blockKey -> timestamp

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

    // Record timestamp
    highlightedBlocks.current.set(blockKey, Date.now());

    // Highlight block immediately
    highlightBlock(canvas, block, drawInfo);
  }, [selectedRelations]);

  // requestAnimationFrame loop to manage block clearing
  useEffect(() => {
    let rafId: number;

    const animate = () => {
      const now = Date.now();

      highlightedBlocks.current.forEach((timestamp, blockKey) => {
        if (now - timestamp > 500) {
          // 500ms elapsed, clear the block
          const [relfilenodeStr, blockStr] = blockKey.split('-');
          const relfilenode = parseInt(relfilenodeStr, 10);
          const block = parseInt(blockStr, 10);

          const canvas = canvasRefs.current.get(relfilenode);
          const drawInfo = drawInfos.current.get(relfilenode);

          if (canvas && drawInfo) {
            clearBlock(canvas, block, drawInfo);
          }

          highlightedBlocks.current.delete(blockKey);
        }
      });

      rafId = requestAnimationFrame(animate);
    };

    rafId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafId);
  }, []);

  const wsUrl = `ws://${window.location.host}/ws`;
  const { isConnected } = useWebSocket(wsUrl, { onMessage: handleTraceEvent });

  // Fetch relations function
  const fetchRelations = useCallback(() => {
    fetch('/api/relations')
      .then((res) => res.json())
      .then((data: RelationInfo[]) => {
        setRelations(data);
        // Select all relations by default
        setSelectedRelations(new Set(data.map((r) => r.relfilenode)));
      })
      .catch((err) => console.error('Error fetching relations:', err));
  }, []);

  // Fetch relations on mount
  useEffect(() => {
    fetchRelations();
  }, [fetchRelations]);

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

  // Separate tables and indexes, sort alphabetically
  const tables = relations
    .filter((r) => r.relkind === 'r' || r.relkind === 'p')
    .sort((a, b) => a.relname.localeCompare(b.relname));

  const indexes = relations
    .filter((r) => r.relkind === 'i' || r.relkind === 'I')
    .sort((a, b) => a.relname.localeCompare(b.relname));

  return (
    <div className="app">
      <header className="app-header">
        <h1>PostgreSQL Buffer Trace Visualizer</h1>
        <div className="connection-status text-sm">
          WebSocket: {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
        </div>
      </header>

      <div className="app-content">
        <aside className="sidebar">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 className="text-lg" style={{ margin: 0 }}>Tables</h2>
            <button onClick={fetchRelations} className="reload-button text-sm">
              🔄 Reload
            </button>
          </div>
          <div className="table-list">
            {tables.map((relation) => (
              <label key={relation.relfilenode} className="table-item text-sm">
                <input
                  type="checkbox"
                  checked={selectedRelations.has(relation.relfilenode)}
                  onChange={() => toggleRelation(relation.relfilenode)}
                />
                <span>{relation.relname}</span>
              </label>
            ))}
          </div>

          <h2 className="text-lg" style={{ marginTop: '1.5rem' }}>Indexes</h2>
          <div className="table-list">
            {indexes.map((relation) => (
              <label key={relation.relfilenode} className="table-item text-sm">
                <input
                  type="checkbox"
                  checked={selectedRelations.has(relation.relfilenode)}
                  onChange={() => toggleRelation(relation.relfilenode)}
                />
                <span>{relation.relname}</span>
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
