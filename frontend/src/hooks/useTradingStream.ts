
import { useEffect, useState, useRef, useCallback } from 'react';

export function useTradingStream(onMessage?: (msg: any) => void) {
    const [lastEvent, setLastEvent] = useState<any>(null);
    const [status, setStatus] = useState<string>("Disconnected");
    const ws = useRef<WebSocket | null>(null);
    const reconnectAttempts = useRef(0);
    const pingInterval = useRef<NodeJS.Timeout | null>(null);
    const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);
    const throttleRef = useRef<number>(0);
    const pendingEvent = useRef<any>(null);
    const onMessageRef = useRef(onMessage);

    useEffect(() => {
        onMessageRef.current = onMessage;
    }, [onMessage]);

    const MAX_RECONNECT_ATTEMPTS = 50;
    const PING_INTERVAL = 15000;
    const THROTTLE_MS = 200; // 最多 5fps 更新

    const sendCommand = useCallback((cmd: any) => {
        if (ws.current?.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify(cmd));
        }
    }, []);

    const connect = useCallback(() => {
        if (ws.current?.readyState === WebSocket.OPEN) return;

        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host; // Includes port 3000
            const wsUrl = `${protocol}//${host}/ws/trading`;
            const socket = new WebSocket(wsUrl);

            socket.onopen = () => {
                setStatus("Connected");
                reconnectAttempts.current = 0;
                console.log("Trading WS Connected");

                if (pingInterval.current) clearInterval(pingInterval.current);
                pingInterval.current = setInterval(() => {
                    if (socket.readyState === WebSocket.OPEN) {
                        socket.send(JSON.stringify({ type: 'ping' }));
                    }
                }, PING_INTERVAL);
            };

            socket.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    if (message.type === 'pong') return;

                    // [Optimization] Immediate trigger for sound/low-latency
                    if (onMessageRef.current) {
                        onMessageRef.current(message);
                    }

                    // 节流：每 200ms 最多触发一次 React 状态更新
                    const now = Date.now();
                    pendingEvent.current = message;
                    if (now - throttleRef.current >= THROTTLE_MS) {
                        throttleRef.current = now;
                        setLastEvent(message);
                    } else if (!throttleRef.current) {
                        // 第一条消息立即触发
                        throttleRef.current = now;
                        setLastEvent(message);
                    }
                } catch (e) {
                    console.error("Trading Stream Parse error", e);
                }
            };

            socket.onclose = (event) => {
                setStatus("Disconnected");
                if (pingInterval.current) {
                    clearInterval(pingInterval.current);
                    pingInterval.current = null;
                }

                if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
                    const delay = Math.min(1000 * Math.pow(1.5, reconnectAttempts.current), 30000);
                    reconnectAttempts.current++;
                    setStatus(`Reconnecting (${reconnectAttempts.current})...`);

                    reconnectTimeout.current = setTimeout(() => {
                        connect();
                    }, delay);
                }
            };

            ws.current = socket;
        } catch (e) {
            console.error("Connect error:", e);
        }
    }, []);

    // 定期刷新积压的事件（防止最后一条消息被节流丢失）
    useEffect(() => {
        const flush = setInterval(() => {
            if (pendingEvent.current) {
                setLastEvent(pendingEvent.current);
                pendingEvent.current = null;
            }
        }, THROTTLE_MS);
        return () => clearInterval(flush);
    }, []);

    useEffect(() => {
        connect();
        return () => {
            if (pingInterval.current) clearInterval(pingInterval.current);
            if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
            if (ws.current) ws.current.close();
        };
    }, [connect]);

    return { lastEvent, status, sendCommand };
}
