import { useEffect, useState, useRef, useCallback } from 'react';
import { ArbitrageData } from '../lib/types';

export function useArbitrage() {
    const [data, setData] = useState<ArbitrageData>({ sf: [], ff: [], ss: [] });
    const [status, setStatus] = useState<string>("Disconnected");
    const ws = useRef<WebSocket | null>(null);
    const reconnectAttempts = useRef(0);
    const pingInterval = useRef<NodeJS.Timeout | null>(null);
    const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);
    const pendingData = useRef<ArbitrageData | null>(null);
    const MAX_RECONNECT_ATTEMPTS = 50;
    const PING_INTERVAL = 15000;
    const FLUSH_INTERVAL = 500;

    const connect = useCallback(() => {
        if (ws.current?.readyState === WebSocket.OPEN) return;

        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host; // Includes port 3000
            const wsUrl = `${protocol}//${host}/ws/monitor`;
            const socket = new WebSocket(wsUrl);

            socket.onopen = () => {
                setStatus("Connected");
                reconnectAttempts.current = 0;
                console.log("WS Connected");

                // 启动心跳
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

                    if (message.type === 'update') {
                        const hydrate = (packed: any) => {
                            if (!packed || !packed.cols) return [];
                            const { cols, rows } = packed;
                            return rows.map((row: any[]) => {
                                const obj: any = {};
                                cols.forEach((col: string, i: number) => {
                                    obj[col] = row[i];
                                });
                                return obj;
                            });
                        };

                        pendingData.current = {
                            sf: hydrate(message.data.sf),
                            ff: hydrate(message.data.ff),
                            ss: hydrate(message.data.ss)
                        };
                    }
                } catch (e) {
                    console.error("Parse error", e);
                }
            };

            socket.onclose = (event) => {
                setStatus("Disconnected");
                console.log("WS Closed, code:", event.code);

                // 停止心跳
                if (pingInterval.current) {
                    clearInterval(pingInterval.current);
                    pingInterval.current = null;
                }

                // 自动重连（指数退避）
                if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
                    const delay = Math.min(1000 * Math.pow(1.5, reconnectAttempts.current), 30000);
                    reconnectAttempts.current++;
                    setStatus(`Reconnecting (${reconnectAttempts.current})...`);
                    console.log(`Reconnecting in ${delay}ms...`);

                    reconnectTimeout.current = setTimeout(() => {
                        connect();
                    }, delay);
                } else {
                    setStatus("Failed - Refresh Page");
                }
            };

            socket.onerror = (error) => {
                console.warn("WS Error (Retrying...):", error);
            };

            ws.current = socket;
        } catch (e) {
            console.error("Connect error:", e);
        }
    }, []);

    // 定期将 pendingData 刷新到 React state（500ms 节流）
    useEffect(() => {
        const flush = setInterval(() => {
            if (pendingData.current) {
                setData(pendingData.current);
                pendingData.current = null;
            }
        }, FLUSH_INTERVAL);
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

    return { data, status };
}

