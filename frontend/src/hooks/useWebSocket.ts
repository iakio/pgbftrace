import { useEffect, useRef, useState } from 'react';
import type { TraceEvent } from '../types';

interface UseWebSocketOptions {
  onMessage?: (event: TraceEvent) => void;
}

interface UseWebSocketReturn {
  isConnected: boolean;
}

export const useWebSocket = (
  url: string,
  options?: UseWebSocketOptions
): UseWebSocketReturn => {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const onMessageRef = useRef(options?.onMessage);

  // Update callback ref when it changes
  useEffect(() => {
    onMessageRef.current = options?.onMessage;
  }, [options?.onMessage]);

  useEffect(() => {
    const ws = new WebSocket(url);
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      const dataView = new DataView(event.data);
      const relfilenode = dataView.getUint32(0, false);
      const block = dataView.getUint32(4, false);

      // Call callback directly without state update
      onMessageRef.current?.({ relfilenode, block });
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return () => {
      ws.close();
    };
  }, [url]);

  return { isConnected };
};
