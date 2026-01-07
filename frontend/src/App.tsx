import { useEffect, useState, useRef, useCallback } from 'react';
import type { RelationInfo } from './types';
import { useWebSocket } from './hooks/useWebSocket';
import { TableCanvas } from './components/TableCanvas';
import { highlightBlock, clearBlock, type DrawInfo } from './utils/canvas-utils';
import './App.css';

function App() {
  const [relations, setRelations] = useState<RelationInfo[]>([]);
  const [selectedRelations, setSelectedRelations] = useState<Set<number>>(new Set());
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Canvas management
  const canvasRefs = useRef<Map<number, HTMLCanvasElement>>(new Map());
  const drawInfos = useRef<Map<number, DrawInfo>>(new Map());
  const highlightedBlocks = useRef<Map<string, number>>(new Map()); // blockKey -> timestamp

  // Handle incoming trace events - Direct canvas manipulation
  const handleTraceEvent = useCallback((traceEvent: { relfilenode: number; block: number, hit: number }) => {
    const { relfilenode, block, hit } = traceEvent;
    console.log(`handleTraceEvent ${relfilenode}, ${block}, ${hit}`)

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
    highlightBlock(canvas, block, drawInfo, hit);
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
    return fetch('/api/relations')
      .then((res) => res.json())
      .then((data: RelationInfo[]) => {
        setRelations(data);
        // Remove selections for deleted relations
        const validFilenodes = new Set(data.map((r) => r.relfilenode));
        setSelectedRelations((prev) => prev.intersection(validFilenodes));
        return data;
      });
  }, []);

  // Fetch relations on mount (select all initially)
  useEffect(() => {
    fetchRelations()
      .then((data) => setSelectedRelations(new Set(data.map((r) => r.relfilenode))))
      .catch((err) => console.error('Error fetching relations:', err));
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
    <div className="min-h-screen flex flex-col bg-gray-100">
      <header className="bg-white px-8 py-4 shadow-md flex justify-between items-center">
        <h1 className="m-0 text-2xl text-gray-800 font-bold">PostgreSQL Buffer Trace Visualizer</h1>
        <div className="px-4 py-2 bg-gray-50 rounded text-sm">
          WebSocket: {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <div className="flex">
          <aside
            className="w-64 bg-white border-r border-gray-300 p-4 overflow-y-auto transition-[margin-left] duration-200"
            style={{ marginLeft: sidebarOpen ? 0 : '-256px' }}
          >
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg m-0 text-gray-800">Tables</h2>
              <button
                onClick={() => fetchRelations()}
                className="px-3 py-1 bg-gray-100 border border-gray-300 rounded cursor-pointer text-sm transition-colors hover:bg-gray-200 active:bg-gray-300"
              >
                🔄 Reload
              </button>
            </div>
            <div className="flex flex-col gap-2">
              {tables.map((relation) => (
                <label key={relation.relfilenode} className="flex items-center cursor-pointer text-sm hover:bg-gray-50">
                  <input
                    type="checkbox"
                    checked={selectedRelations.has(relation.relfilenode)}
                    onChange={() => toggleRelation(relation.relfilenode)}
                    className="mr-2"
                  />
                  <span className="flex-1">{relation.relname}</span>
                </label>
              ))}
            </div>

            <h2 className="text-lg mt-6 text-gray-800">Indexes</h2>
            <div className="flex flex-col gap-2">
              {indexes.map((relation) => (
                <label key={relation.relfilenode} className="flex items-center cursor-pointer text-sm hover:bg-gray-50">
                  <input
                    type="checkbox"
                    checked={selectedRelations.has(relation.relfilenode)}
                    onChange={() => toggleRelation(relation.relfilenode)}
                    className="mr-2"
                  />
                  <span className="flex-1">{relation.relname}</span>
                </label>
              ))}
            </div>
          </aside>

          <button
            className="bg-white border border-gray-300 border-l-0 rounded-r px-2 py-4 cursor-pointer text-xl hover:bg-gray-50"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
          >
            {sidebarOpen ? '◀' : '▶'}
          </button>
        </div>

        <main className="flex-1 p-4 overflow-y-auto flex flex-wrap gap-4 content-start">
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
