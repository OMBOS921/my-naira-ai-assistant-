import { useEffect, useRef, useState, useCallback } from 'react';

/**
 * Custom React hook for managing real-time WebSocket connection to Naira backend.
 * Handles automatic reconnects, status monitoring, and bi-directional messaging.
 *
 * @param {string} url - WebSocket endpoint URL (defaults to ws://localhost:8000/ws/naira)
 * @returns {object} { connectionState, isConnected, sendMessage, lastMessage }
 */
export const useNairaSocket = (url = 'ws://localhost:8000/ws/naira') => {
  const [connectionState, setConnectionState] = useState('disconnected'); // 'connecting' | 'connected' | 'disconnected'
  const [lastMessage, setLastMessage] = useState(null);

  const socketRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const isMountedRef = useRef(true);

  const connect = useCallback(() => {
    // Avoid duplicate connection attempts if already open or connecting
    if (
      socketRef.current &&
      (socketRef.current.readyState === WebSocket.CONNECTING || socketRef.current.readyState === WebSocket.OPEN)
    ) {
      return;
    }

    setConnectionState('connecting');

    try {
      const ws = new WebSocket(url);
      socketRef.current = ws;

      ws.onopen = () => {
        if (isMountedRef.current) {
          console.log('[useNairaSocket] Connected to backend endpoint:', url);
          setConnectionState('connected');
        }
      };

      ws.onmessage = (event) => {
        if (!isMountedRef.current) return;
        try {
          const parsed = JSON.parse(event.data);
          setLastMessage(parsed);
        } catch {
          setLastMessage({ sender: 'naira', text: event.data });
        }
      };

      ws.onerror = (err) => {
        console.warn('[useNairaSocket] Socket encountered error:', err);
      };

      ws.onclose = () => {
        if (isMountedRef.current) {
          console.log('[useNairaSocket] Connection closed. Attempting auto-reconnect in 3s...');
          setConnectionState('disconnected');
          reconnectTimerRef.current = setTimeout(() => {
            connect();
          }, 3000);
        }
      };
    } catch (err) {
      console.error('[useNairaSocket] Failed to initiate connection:', err);
      setConnectionState('disconnected');
      reconnectTimerRef.current = setTimeout(() => {
        connect();
      }, 3000);
    }
  }, [url]);

  const sendMessage = useCallback((payload) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      const messageStr = typeof payload === 'string' ? JSON.stringify({ text: payload }) : JSON.stringify(payload);
      socketRef.current.send(messageStr);
      return true;
    } else {
      console.warn('[useNairaSocket] Cannot send message: WebSocket is not open.');
      return false;
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    connect();

    return () => {
      isMountedRef.current = false;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [connect]);

  return {
    connectionState,
    isConnected: connectionState === 'connected',
    sendMessage,
    lastMessage,
  };
};

export default useNairaSocket;
