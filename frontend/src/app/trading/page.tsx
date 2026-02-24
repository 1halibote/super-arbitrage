"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { Settings, Plus, RefreshCw, Trash2, Play, Pause, RotateCcw, X, Edit2, Package, Link2, Upload, ChevronDown, Filter, Clock, Power, Pin, MoreHorizontal, HelpCircle, AlertTriangle, Siren, Minus, PlusCircle, AlertOctagon, Volume2, VolumeX, Circle, ArrowLeftRight, Zap } from "lucide-react";
import ExchangeTab from "./components/ExchangeTab";
import { NumberTicker } from "./components/NumberTicker";
import ProfitTab from "./components/ProfitTab";
import LogTab from "./components/LogTab";
import { useArbitrage } from "@/hooks/useArbitrage";
import { useTradingStream } from "@/hooks/useTradingStream";
import { useSoundEffects } from "@/hooks/useSoundEffects";
import { useThrottle } from "@/hooks/useThrottle";

const API_BASE = "";

interface Exchange {
    name: string;
    connected: boolean;
    balance: number;
}

interface LadderStep {
    spread: number;
    amount: number;
}

interface TradingCard {
    id: string;
    symbol: string;
    status: string;
    type: string;
    exchange_a: string;
    exchange_b: string;
    leverage: number;
    open_threshold: number;
    close_threshold: number;
    max_position: number;
    order_min: number;
    order_max: number;
    position_qty: number;
    position_value: number;
    pnl: number;
    ladder_enabled: boolean;
    ladder: LadderStep[];
    open_disabled: boolean;
    close_disabled: boolean;
    stop_loss: number;
    price_alert: number;
    start_time: number; // timestamp
    is_syncing?: boolean; // [New] Suppress warnings if true

    // 实时数据
    realtime_spread?: number;
    realtime_index?: number;
    realtime_funding_a?: number;
    realtime_funding_b?: number;
    funding_countdown_a?: string;
    funding_countdown_b?: string;
    mmr_a?: number;
    mmr_b?: number;
    open_avg_price?: number;
    close_avg_price?: number;

    avg_price_a?: number;
    avg_price_b?: number;
    position_qty_a?: number;
    position_qty_b?: number;
    position_value_a?: number;
    position_value_b?: number;
    pnl_a?: number;
    pnl_b?: number;

    liq_price_a?: number;
    liq_price_b?: number;
    adl_a?: number;
    adl_b?: number;

    margin_ratio_a?: number;
    margin_ratio_b?: number;

    open_spread?: number;
    close_spread?: number;
    last_open_time?: number;
    last_close_time?: number;


    indexDiffA?: number;
    indexDiffB?: number;
}






// Timestamp Tool Component
const TimestampTool = ({ onClose, theme }: { onClose: () => void, theme: string }) => {
    // TS -> Date
    const [tsInput, setTsInput] = useState("");
    const [dateResult, setDateResult] = useState("");

    // Date -> TS
    const [dateInput, setDateInput] = useState("");
    const [tsResult, setTsResult] = useState("");

    const [now, setNow] = useState(Date.now());

    useEffect(() => {
        const timer = setInterval(() => setNow(Date.now()), 100);
        return () => clearInterval(timer);
    }, []);

    const formatDate = (ts: number) => {
        const d = new Date(ts);
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}.${String(d.getMilliseconds()).padStart(3, '0')}`;
    };

    const handleTsChange = (val: string) => {
        setTsInput(val);
        const num = Number(val);
        if (val && !isNaN(num)) {
            setDateResult(formatDate(num));
        } else {
            setDateResult("");
        }
    };

    const handleDateChange = (val: string) => {
        setDateInput(val);
        const d = new Date(val);
        if (!isNaN(d.getTime())) {
            setTsResult(d.getTime().toString());
        } else {
            setTsResult("");
        }
    };

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text);
    };

    const bgColor = theme === "dark" ? "bg-slate-800" : "bg-white";
    const borderColor = theme === "dark" ? "border-slate-700" : "border-gray-200";
    const inputBg = theme === "dark" ? "bg-slate-900" : "bg-gray-50";

    return (
        <div className={`absolute top-16 right-6 z-50 ${bgColor} border ${borderColor} p-4 rounded-lg shadow-xl w-80 text-sm`}>
            <div className="flex justify-between items-center mb-3">
                <h3 className="font-bold flex items-center gap-2"><Clock className="w-4 h-4" /> 时间戳工具</h3>
                <button onClick={onClose} className="hover:text-red-500"><X className="w-4 h-4" /></button>
            </div>

            <div className="space-y-4">
                {/* Current Time */}
                <div className={`p-2 rounded ${inputBg} font-mono text-xs`}>
                    <div className="flex justify-between items-center mb-1">
                        <span className="text-gray-400">当前时间</span>
                        <button onClick={() => copyToClipboard(String(now))} className="text-blue-500 hover:text-blue-400 text-xs">复制时间戳</button>
                    </div>
                    <div className="text-lg font-bold text-cyan-500">{now}</div>
                    <div className="text-gray-500">{formatDate(now)}</div>
                </div>

                {/* MS to Date */}
                <div>
                    <label className="block text-xs text-gray-500 mb-1">毫秒时间戳 → 日期</label>
                    <input
                        type="text"
                        value={tsInput}
                        onChange={(e) => handleTsChange(e.target.value)}
                        placeholder="输入时间戳..."
                        className={`w-full px-2 py-1.5 rounded border ${borderColor} ${inputBg} focus:outline-none focus:border-blue-500 font-mono`}
                    />
                    {dateResult && <div className="mt-1 text-xs text-green-500 font-mono">{dateResult}</div>}
                </div>

                {/* Date to MS */}
                <div>
                    <label className="block text-xs text-gray-500 mb-1">日期 → 毫秒时间戳</label>
                    <input
                        type="datetime-local"
                        step="0.001"
                        value={dateInput}
                        onChange={(e) => handleDateChange(e.target.value)}
                        className={`w-full px-2 py-1.5 rounded border ${borderColor} ${inputBg} focus:outline-none focus:border-blue-500 font-mono [&::-webkit-calendar-picker-indicator]:cursor-pointer [&::-webkit-calendar-picker-indicator]:filter-[invert(42%)_sepia(93%)_saturate(1352%)_hue-rotate(87deg)_brightness(119%)_contrast(119%)]`}
                    />
                    {tsResult && (
                        <div className="mt-1 flex justify-between items-center">
                            <span className="text-xs text-green-500 font-mono">{tsResult}</span>
                            <button onClick={() => copyToClipboard(tsResult)} className="text-blue-500 hover:text-blue-400 text-xs">复制</button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
// 利润 Tab 组件

export default function TradingPage() {
    const [exchanges, setExchanges] = useState<Exchange[]>([]);
    const [cards, setCards] = useState<TradingCard[]>([]);
    const [loading, setLoading] = useState(true);
    const [showAddExchange, setShowAddExchange] = useState(false);
    const [showAddCard, setShowAddCard] = useState(false);
    const [currentTime, setCurrentTime] = useState(new Date());
    const [monitorStatus, setMonitorStatus] = useState<"stopped" | "running" | "paused">("stopped");
    const [canStartMonitor, setCanStartMonitor] = useState(false);
    const [showDraftBox, setShowDraftBox] = useState(false);
    const draftCount = useMemo(() => cards.filter(c => c.status === "draft").length, [cards]);
    const [activeTab, setActiveTab] = useState<"pairs" | "exchanges" | "profit" | "log">("pairs");
    const [theme, setTheme] = useState<"dark" | "light">("dark");
    const [showTimeTool, setShowTimeTool] = useState(false);
    const [editingCardId, setEditingCardId] = useState<string | null>(null);
    const [soundEnabled, setSoundEnabled] = useState(true);

    // Audio effects
    const { playIncrease, playDecrease } = useSoundEffects();
    const prevPositionValuesRef = useRef<Map<string, number>>(new Map());
    const manualActionRef = useRef<number>(0);

    // Real-time arbitrage data for symbol suggestions and card display
    const { data: arbitrageData } = useArbitrage();

    // Callback for immediate sound effects (bypassing throttle)
    const handleStreamMessage = useCallback((message: any) => {
        if (message.type === 'card_update' && message.data?.card) {
            const updatedCard = message.data.card as TradingCard;

            // 音效触发逻辑：极其紧凑贴合仓位真实价值变动，摒弃乱响的轮询干预
            if (soundEnabled) {
                const prevVal = prevPositionValuesRef.current.get(updatedCard.id) ?? 0;
                const currVal = updatedCard.position_value || 0;
                const diff = currVal - prevVal;

                // 只要绝对净值变化大于 1.0U 就发出对应的声音（避免几分钱的抖动产生噪音）
                if (Math.abs(diff) > 1.0) {
                    if (diff > 0) {
                        playIncrease();
                    } else {
                        playDecrease();
                    }
                    prevPositionValuesRef.current.set(updatedCard.id, currVal);
                } else if (prevVal === 0 && currVal > 0) {
                    // 从 0 刚突破的初始建仓必须响
                    playIncrease();
                    prevPositionValuesRef.current.set(updatedCard.id, currVal);
                } else if (prevVal > 0 && currVal === 0) {
                    // 彻底清仓归零必须响
                    playDecrease();
                    prevPositionValuesRef.current.set(updatedCard.id, currVal);
                }
            }
        }
    }, [soundEnabled, playIncrease, playDecrease]);

    // Trading WebSocket stream for real-time card updates
    const { lastEvent: tradingEvent } = useTradingStream(handleStreamMessage);


    // 监听 WebSocket 事件更新卡片数据 (Throttled for UI)
    // [OPTIMIZATION] Use throttle to prevent UI lag on high-freq updates
    const handleCardUpdate = useCallback((updatedCard: TradingCard) => {
        setCards(prev => prev.map(c => c.id === updatedCard.id ? updatedCard : c));
    }, []);

    const throttledUpdate = useThrottle(handleCardUpdate, 200); // 200ms throttle

    useEffect(() => {
        if (tradingEvent && tradingEvent.type === 'card_update' && tradingEvent.data?.card) {
            const updatedCard = tradingEvent.data.card as TradingCard;
            throttledUpdate(updatedCard);
        }
    }, [tradingEvent, throttledUpdate]);

    // Audio Context for Alarms
    const audioCtxRef = useRef<AudioContext | null>(null);

    const playAlarm = useCallback(() => {
        if (!audioCtxRef.current) {
            audioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
        }
        const ctx = audioCtxRef.current;
        if (ctx.state === 'suspended') ctx.resume();

        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(880, ctx.currentTime); // A5
        osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.5); // Slide down

        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);

        osc.start();
        osc.stop(ctx.currentTime + 0.5);

        // Second beep
        setTimeout(() => {
            const osc2 = ctx.createOscillator();
            const gain2 = ctx.createGain();
            osc2.connect(gain2);
            gain2.connect(ctx.destination);
            osc2.type = 'sawtooth';
            osc2.frequency.setValueAtTime(880, ctx.currentTime);
            osc2.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.5);
            gain2.gain.setValueAtTime(0.3, ctx.currentTime);
            gain2.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
            osc2.start();
            osc2.stop(ctx.currentTime + 0.5);
        }, 600);

    }, []);

    // 报警逻辑：仓位稳定 3s 后检查，触发后持续报警 10s
    const alarmTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const alarmIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const prevCardsJsonRef = useRef<string>('');

    useEffect(() => {
        // 检查仓位是否异常
        const checkAlarmCondition = () => {
            return cards.some(c => {
                if (c.status !== 'running') return false;
                if (c.is_syncing) return false;
                const valA = c.position_value_a || 0;
                const valB = c.position_value_b || 0;
                const maxVal = Math.max(valA, valB);
                if (maxVal < 2) return false;
                const isSingleLeg = (valA > 2 && valB < 1) || (valB > 2 && valA < 1);
                const diff = Math.abs(valA - valB);
                const isImbalanced = (diff / maxVal) > 0.08;
                return isSingleLeg || isImbalanced;
            });
        };

        // 生成 cards 的稳定性指纹（只取仓位值）
        const posFingerprint = cards.map(c => `${c.id}:${Math.round(c.position_value_a || 0)}:${Math.round(c.position_value_b || 0)}`).join('|');

        // 仓位发生变化 → 重置延迟检查
        if (posFingerprint !== prevCardsJsonRef.current) {
            prevCardsJsonRef.current = posFingerprint;
            if (alarmTimerRef.current) clearTimeout(alarmTimerRef.current);

            // 8s 后检查是否仍然异常（覆盖多次 sync 周期）
            alarmTimerRef.current = setTimeout(() => {
                if (checkAlarmCondition()) {
                    // 触发持续报警 10s（每秒 beep 一次）
                    if (alarmIntervalRef.current) clearInterval(alarmIntervalRef.current);
                    let count = 0;
                    playAlarm();
                    alarmIntervalRef.current = setInterval(() => {
                        count++;
                        if (count >= 10) {
                            if (alarmIntervalRef.current) clearInterval(alarmIntervalRef.current);
                            alarmIntervalRef.current = null;
                            return;
                        }
                        playAlarm();
                    }, 1000);
                }
            }, 8000);
        }

        return () => {
            if (alarmTimerRef.current) clearTimeout(alarmTimerRef.current);
        };
    }, [cards, playAlarm]);

    // 新交易所表单
    const [newExchange, setNewExchange] = useState({ exchange: "binance", apiKey: "", apiSecret: "" });

    // 拖拽状态
    const [modalPos, setModalPos] = useState({ x: 0, y: 0 });
    const isDragging = useRef(false);
    const dragStart = useRef({ x: 0, y: 0 });

    // Position Tracker for Sound
    const lastPositionsRef = useRef<Record<string, number>>({});

    // (playBeep logic removed to prevent double-firing and delays from HTTP loading)


    // 新卡片表单
    const [newCard, setNewCard] = useState<any>({
        symbol: "",
        status: "paused",
        type: "SF",
        exchangeA: "binance",
        exchangeB: "bybit",
        leverage: 1,
        openThreshold: 1.0,
        closeThreshold: 0.0,
        maxPosition: 1000,
        orderMin: 8,
        orderMax: 10,
        ladderEnabled: false,
        ladder: [{ spread: 1.5, amount: 500 }, { spread: 2.0, amount: 1000 }],
        openDisabled: false,
        closeDisabled: false,
        stopLoss: 0,
        priceAlert: 0,
        startTime: 0 // timestamp
    });

    // 拖拽逻辑
    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (!isDragging.current) return;
            const dx = e.clientX - dragStart.current.x;
            const dy = e.clientY - dragStart.current.y;
            setModalPos(prev => ({ x: prev.x + dx, y: prev.y + dy }));
            dragStart.current = { x: e.clientX, y: e.clientY };
        };

        const handleMouseUp = () => {
            isDragging.current = false;
        };

        if (showAddCard) {
            window.addEventListener('mousemove', handleMouseMove);
            window.addEventListener('mouseup', handleMouseUp);
        }

        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
    }, [showAddCard]);

    const onModalHeaderMouseDown = (e: React.MouseEvent) => {
        isDragging.current = true;
        dragStart.current = { x: e.clientX, y: e.clientY };
    };

    // 时钟更新
    useEffect(() => {
        const timer = setInterval(() => setCurrentTime(new Date()), 1000);
        return () => clearInterval(timer);
    }, []);

    // 加载数据
    useEffect(() => {
        loadCards();
        loadExchanges();
        loadMonitor();
    }, []);

    // 5s 轮询兜底：确保 WS 事件丢失时 UI 仍能更新
    useEffect(() => {
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE}/api/trading/cards`);
                const data = await res.json();
                const newCards = data.cards || [];
                // 只有 running 卡片存在时才静默更新
                const hasRunning = newCards.some((c: TradingCard) => c.status === 'running');
                if (hasRunning) {
                    setCards(newCards);
                }
            } catch { }
        }, 5000);
        return () => clearInterval(interval);
    }, []);

    const loadCards = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/trading/cards`);
            const data = await res.json();
            // Don't sort here, use derived state
            const fetchedCards = data.cards || [];
            setCards(fetchedCards || []);

            // 废弃原先这里的轮询加载触发音效机制（因慢半拍且极易重叠报错）
            // 现全部交给 handleStreamMessage 处理 WebSockets 毫秒级原生播报
        } catch (e) {
            console.error("Failed to load cards", e);
        }
    };

    const loadExchanges = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/trading/exchanges`);
            const data = await res.json();
            setExchanges(data.exchanges || []);
        } catch (e) {
            console.error("Failed to load exchanges", e);
        }
    };

    const loadMonitor = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/monitor/status`);
            const data = await res.json();
            setMonitorStatus(data.status || "stopped");
            setCanStartMonitor(data.canStart || false);
        } catch (e) {
            console.error("Failed to load monitor", e);
        }
    };

    const loadData = async () => {
        setLoading(true);
        await Promise.all([loadCards(), loadExchanges(), loadMonitor()]);
        setLoading(false);
    };

    // 添加交易所
    const handleAddExchange = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/trading/exchange`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(newExchange)
            });
            const data = await res.json();
            if (data.success) {
                setShowAddExchange(false);
                setNewExchange({ exchange: "binance", apiKey: "", apiSecret: "" });
                loadExchanges(); // Only reload exchanges
            }
        } catch (e) {
            console.error("Failed to add exchange", e);
        }
    };

    // 删除交易所
    const handleDeleteExchange = async (exchange: string) => {
        if (!confirm(`确定删除 ${exchange} 吗？`)) return;
        try {
            await fetch(`${API_BASE}/api/trading/exchange/${exchange}`, { method: "DELETE" });
            loadExchanges(); // Only reload exchanges
        } catch (e) {
            console.error("Failed to delete exchange", e);
        }
    };

    // 切换卡片状态
    const handleToggleStatus = async (card: TradingCard) => {
        const newStatus = card.status === "running" ? "paused" : "running";
        try {
            // 只更新状态，其他字段保持原样
            const updatedCard = { ...card, status: newStatus };
            const res = await fetch(`${API_BASE}/api/trading/card/${card.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(updatedCard)
            });

            if (res.ok) {
                // Optimistic update or just loadCards (fast now)
                loadCards(); // 刷新列表 (Fast)
            } else {
                const data = await res.json();
                alert("切换状态失败: " + JSON.stringify(data));
            }
        } catch (e) {
            console.error("Failed to toggle status", e);
        }
    };

    // 添加/编辑卡片
    const handleAddCard = async () => {
        if (parseFloat(newCard.openThreshold) <= parseFloat(newCard.closeThreshold)) {
            alert("错误：开仓差价必须大于清仓差价！");
            return;
        }

        // Validation: Order sizes must be <= Position Limit
        const maxPos = parseFloat(newCard.maxPosition) || 0;
        const oMax = parseFloat(newCard.orderMax) || 0;
        const oMin = parseFloat(newCard.orderMin) || 0;

        if (oMax > maxPos) {
            alert(`错误：最大单笔额 (${oMax}) 不能超过仓位限额 (${maxPos})！`);
            return;
        }
        if (oMin > maxPos) {
            alert(`错误：最小单笔额 (${oMin}) 不能超过仓位限额 (${maxPos})！`);
            return;
        }
        if (oMin < 8) {
            alert(`错误：单笔最小金额必须至少为 8U！`);
            return;
        }

        if (oMin >= oMax) {
            alert(`错误：最小单笔额 (${oMin}) 必须小于 最大单笔额 (${oMax})！`);
            return;
        }

        // 防重校验：不允许创建同币种同类型同交易所配对的卡片
        if (!editingCardId) {
            const sym = newCard.symbol.toUpperCase();
            const ea = newCard.exchangeA.trim().toLowerCase();
            const eb = newCard.exchangeB.trim().toLowerCase();
            const duplicate = cards.find((c: any) =>
                c.symbol === sym && c.type === newCard.type &&
                c.exchange_a === ea && c.exchange_b === eb
            );
            if (duplicate) {
                alert(`错误：已存在相同配置的卡片 (${sym} ${newCard.type} ${ea}/${eb})，不能重复创建！`);
                return;
            }
        }

        try {
            const url = editingCardId ? `/api/trading/card/${editingCardId}` : "/api/trading/card";
            const method = editingCardId ? "PUT" : "POST";

            // Convert strings to numbers
            // Convert strings to numbers and map to snake_case for backend
            const cardData = {
                symbol: newCard.symbol,
                status: newCard.status,
                type: newCard.type,
                exchange_a: newCard.exchangeA.trim().toLowerCase(),
                exchange_b: newCard.exchangeB.trim().toLowerCase(),
                leverage: parseInt(newCard.leverage) || 1,
                open_threshold: parseFloat(newCard.openThreshold) || 0,
                close_threshold: parseFloat(newCard.closeThreshold) || 0,
                max_position: parseFloat(newCard.maxPosition) || 0,
                order_min: parseFloat(newCard.orderMin) || 0,
                order_max: parseFloat(newCard.orderMax) || 0,
                stop_loss: parseFloat(newCard.stopLoss) || 0,
                price_alert: parseFloat(newCard.priceAlert) || 0,
                start_time: parseInt(newCard.startTime) || 0,
                ladder_enabled: newCard.ladderEnabled,
                ladder: newCard.ladder,
                open_disabled: newCard.openDisabled,
                close_disabled: newCard.closeDisabled
            };

            const res = await fetch(url, {
                method: method,
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(cardData)
            });
            const data = await res.json();
            if (data.success) {
                setShowAddCard(false);
                setEditingCardId(null);
                resetNewCard();
                loadCards(); // Only reload cards (Fast)
            } else {
                alert((editingCardId ? "更新" : "创建") + "失败: " + JSON.stringify(data));
            }
        } catch (e) {
            console.error("Failed to save card", e);
        }
    };

    // 快捷增减阈值/限额 (防抖交由用户手速或后端的节流暂缓，前端直接发请求)
    const handleQuickUpdate = async (card: TradingCard, field: "threshold" | "position", action: "add" | "sub") => {
        let updates: any = {};
        if (field === "threshold") {
            const step = 0.1;
            const newOpen = parseFloat((card.open_threshold + (action === "add" ? step : -step)).toFixed(2));
            const newClose = parseFloat((card.close_threshold + (action === "add" ? step : -step)).toFixed(2));
            if (newOpen <= newClose) {
                alert("错误：开仓差价必须大于清仓差价！");
                return;
            }
            updates = { open_threshold: newOpen, close_threshold: newClose };
        } else if (field === "position") {
            const step = 100;
            const newPos = card.max_position + (action === "add" ? step : -step);
            if (newPos < card.order_max) {
                alert(`错误：仓位限额不能低于单笔最大下单额 (${card.order_max}U)`);
                return;
            }
            updates = { max_position: newPos };
        }

        try {
            const res = await fetch(`/api/trading/card/${card.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ...card, ...updates })
            });
            if (res.ok) {
                loadCards(); // 刷新数据
            } else {
                alert("快捷更新失败");
            }
        } catch (e) {
            console.error("Quick update failed", e);
        }
    };

    // 打开编辑弹窗
    const handleEditCard = (card: TradingCard) => {
        setNewCard({
            symbol: card.symbol,
            status: card.status,
            type: card.type,
            exchangeA: card.exchange_a,
            exchangeB: card.exchange_b,
            leverage: card.leverage,
            openThreshold: card.open_threshold,
            closeThreshold: card.close_threshold,
            maxPosition: card.max_position,
            orderMin: card.order_min,
            orderMax: card.order_max,
            ladderEnabled: card.ladder_enabled,
            ladder: card.ladder,
            openDisabled: card.open_disabled,
            closeDisabled: card.close_disabled,
            stopLoss: card.stop_loss,
            priceAlert: card.price_alert,
            startTime: card.start_time
        });
        setEditingCardId(card.id);
        setShowAddCard(true);
    };

    const resetNewCard = () => {
        setNewCard({
            symbol: "",
            status: "paused",
            type: "SF",
            exchangeA: "binance",
            exchangeB: "bybit",
            leverage: 1,
            openThreshold: 1.0,
            closeThreshold: 0.0,
            maxPosition: 1000,
            orderMin: "",
            orderMax: "",
            ladderEnabled: false,
            ladder: [{ spread: 1.5, amount: 500 }, { spread: 2.0, amount: 1000 }],
            openDisabled: false,
            closeDisabled: false,
            stopLoss: 0,
            priceAlert: 0,
            startTime: 0
        });
        setModalPos({ x: 0, y: 0 });
    };

    // 删除卡片 (移至草稿箱)
    const handleDeleteCard = async (cardId: string) => {
        // [Safety] Find card and check status
        const card = cards.find(c => c.id === cardId);
        if (card && card.status === "running") {
            alert("无法删除正在运行的卡片！\n请先暂停该卡片 (点击左上角的绿色按钮)。");
            return;
        }

        if (!confirm(`确定将 ${card?.symbol || "该卡片"} 移至草稿箱吗？`)) return;

        try {
            const updatedCard = { ...card, status: "draft" };
            await fetch(`${API_BASE}/api/trading/card/${cardId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(updatedCard)
            });
            loadCards();
        } catch (e) {
            console.error("Failed to move card to draft", e);
        }
    };

    // 批量删除卡片至草稿箱
    const handleDeleteAll = async () => {
        const nonRunningCards = cards.filter(c => c.status !== "running" && c.status !== "draft");
        if (nonRunningCards.length === 0) {
            alert("没有可删除的卡片 (运行中的卡片无法删除)！");
            return;
        }
        if (!confirm(`确定将所有非运行中的卡片（共 ${nonRunningCards.length} 张）移至草稿箱吗？`)) return;

        try {
            await Promise.all(nonRunningCards.map(c =>
                fetch(`${API_BASE}/api/trading/card/${c.id}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ ...c, status: "draft" })
                })
            ));
            loadCards();
        } catch (e) {
            console.error("Failed to delete all cards", e);
        }
    };

    // 手动执行开仓
    // 手动执行开仓
    // 一键开仓
    const handleExecute = async (card: TradingCard) => {
        console.log("[OneClickOpen] Clicked. Status:", card.status);

        // Normalize status check
        const isRunning = card.status && card.status.toLowerCase() === "running";

        if (!isRunning) {
            const confirmed = confirm(`确定开启一键开仓吗？\n\n这将把卡片状态设为“已启用”，并将开/清仓差价分别设为 -900% / -999%，以触发立即开仓。`);
            if (!confirmed) {
                console.log("[OneClickOpen] Cancelled by user.");
                return;
            }
        }

        manualActionRef.current = Date.now() + 10000;

        try {
            console.log("[OneClickOpen] Sending update...");
            const updatedCard = {
                ...card,
                open_threshold: -900,
                close_threshold: -999,
                status: "running"
            };

            const res = await fetch(`${API_BASE}/api/trading/card/${card.id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    symbol: updatedCard.symbol,
                    status: updatedCard.status,
                    type: updatedCard.type,
                    exchange_a: updatedCard.exchange_a,
                    exchange_b: updatedCard.exchange_b,
                    leverage: updatedCard.leverage,
                    open_threshold: updatedCard.open_threshold,
                    close_threshold: updatedCard.close_threshold,
                    max_position: updatedCard.max_position,
                    order_min: updatedCard.order_min,
                    order_max: updatedCard.order_max,
                    ladder_enabled: updatedCard.ladder_enabled,
                    ladder: updatedCard.ladder,
                    open_disabled: updatedCard.open_disabled,
                    close_disabled: updatedCard.close_disabled,
                    stop_loss: updatedCard.stop_loss,
                    price_alert: updatedCard.price_alert,
                    start_time: updatedCard.start_time
                })
            });

            if (res.ok) {
                console.log("[OneClickOpen] Update success");
                // 强制稍微等待一下再刷新，确保后端已写入
                await new Promise(r => setTimeout(r, 200));
                loadCards();
            } else {
                const err = await res.json();
                console.error("[OneClickOpen] Update failed:", err);
                alert(`启动失败: ${err.error || "Unknown error"}`);
            }
        } catch (e) {
            console.error("[OneClickOpen] Exception:", e);
            alert("请求失败，请检查网络或后端服务");
        }
    };

    // 手动平仓
    // 一键清仓 - 静默执行，不弹窗
    const handleClose = async (card: TradingCard) => {
        console.log("[OneClickClose] Clicked. Status:", card.status);
        const isPaused = !card.status || card.status.toLowerCase() === "paused" || card.status.toLowerCase() === "stopped";

        // [New Feature] If paused, ask to start
        if (isPaused) {
            if (!confirm("卡片已暂停。是否立即启动并执行清仓？\n(启动后将设置为: 禁止开仓, 触发清仓)")) {
                return;
            }

            // 1. Switch to Running + Safe Thresholds
            const updatedCard = {
                ...card,
                status: "running",
                open_threshold: 999.0,
                close_threshold: 900.0
            };

            try {
                await fetch(`${API_BASE}/api/trading/card/${card.id}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(updatedCard)
                });
                await new Promise(r => setTimeout(r, 200));
            } catch (e) {
                alert("启动卡片失败");
                return;
            }
        }

        try {
            manualActionRef.current = Date.now() + 10000;
            const res = await fetch(`${API_BASE}/api/trading/force-close/${card.symbol}?exchangeA=${card.exchange_a}&exchangeB=${card.exchange_b}&cardId=${card.id}`, {
                method: "POST"
            });
            const data = await res.json();

            if (data.success) {
                console.log(`[CLOSE] ${card.symbol} 成功，延迟: ${data.latency_ms?.toFixed(0) || 0}ms`);
            } else {
                console.warn(`[CLOSE] ${card.symbol} 失败: ${data.error || "未知错误"}`);
            }
        } catch (e) {
            console.error("Close failed", e);
            alert("清仓请求失败");
        } finally {
            // Always reload to reflect latest state (e.g. if sync succeeded even if orders failed)
            loadCards();
        }
    };

    // 手动校准仓位
    const handleSyncCard = async (card: TradingCard) => {
        if (card.status !== "running") {
            alert("同步功能仅对运行中的卡片起效！");
            return;
        }
        try {
            const res = await fetch(`${API_BASE}/api/trading/card/${card.id}/sync`, {
                method: "POST"
            });
            const data = await res.json();
            if (data.success) {
                loadCards();
            } else {
                console.warn(`[SYNC] ${card.symbol} 校准失败: ${data.error}`);
            }
        } catch (e) {
            console.error("Sync card failed", e);
        }
    };

    // 强制校准现货仓位（SF专用）
    const handleCalibrateCard = async (card: TradingCard) => {
        if (card.status !== "running") {
            alert("现货校准功能仅对运行中的卡片起效！");
            return;
        }
        if (!confirm("确定要强制校准现货仓位吗？这将会使用交易所的真实余额覆盖现货腿的内部账本。")) return;
        try {
            const res = await fetch(`${API_BASE}/api/trading/card/${card.id}/calibrate`, {
                method: "POST"
            });
            const data = await res.json();
            if (data.success) {
                loadCards();
            } else {
                alert(`校准失败: ${data.error}`);
            }
        } catch (e) {
            console.error("Calibrate card failed", e);
            alert("校准请求失败");
        }
    };

    // 创建反向卡片
    const handleReverseCard = async (cardId: string) => {
        // Removed confirmation dialog
        try {
            const res = await fetch(`${API_BASE}/api/trading/card/${cardId}/reverse`, {
                method: "POST"
            });
            const data = await res.json();
            if (data.success) {
                // alert("反向卡片创建成功！");
                loadCards();
            } else {
                alert(`创建失败: ${data.error}`);
            }
        } catch (e) {
            console.error("Reverse card failed", e);
            alert("请求失败");
        }
    };

    // [New] Drag & Drop State
    const [draggedCardId, setDraggedCardId] = useState<string | null>(null);

    const handleDragStart = (e: React.DragEvent, cardId: string) => {
        setDraggedCardId(cardId);
        e.dataTransfer.effectAllowed = "move";
        // Ghost image transparency hack if needed, or default browser behavior
    };

    const handleDragOver = (e: React.DragEvent, targetId: string) => {
        e.preventDefault(); // Allow drop
        e.dataTransfer.dropEffect = "move";
        if (dragOverId !== targetId) setDragOverId(targetId);
    };

    const handleDrop = (e: React.DragEvent, targetCardId: string) => {
        e.preventDefault();
        if (!draggedCardId || draggedCardId === targetCardId) return;

        const newCards = [...cards];
        const dragIndex = newCards.findIndex(c => c.id === draggedCardId);
        const hoverIndex = newCards.findIndex(c => c.id === targetCardId);

        if (dragIndex < 0 || hoverIndex < 0) return;

        // Move item
        const [removed] = newCards.splice(dragIndex, 1);
        newCards.splice(hoverIndex, 0, removed);

        setCards(newCards);
        // Save order
        const newOrderIds = newCards.map(c => c.id);
        const filteredOrder = newOrderIds.filter((id) => !pinnedIds.includes(id));
        setCardOrder(filteredOrder);
        localStorage.setItem('card_order', JSON.stringify(filteredOrder));

        setDraggedCardId(null);
        setDragOverId(null);
    };

    // [New] Pin Logic
    const [pinnedIds, setPinnedIds] = useState<string[]>([]);
    const [cardOrder, setCardOrder] = useState<string[]>([]);
    const [dragOverId, setDragOverId] = useState<string | null>(null);

    useEffect(() => {
        try {
            const p = JSON.parse(localStorage.getItem('pinned_ids') || '[]');
            setPinnedIds(p);
            const o = JSON.parse(localStorage.getItem('card_order') || '[]');
            setCardOrder(o);
        } catch (e) { console.error("Load local storage failed", e); }
    }, []);

    const togglePin = (cardId: string) => {
        const isPinned = pinnedIds.includes(cardId);
        let newPinned;
        if (isPinned) {
            newPinned = pinnedIds.filter(id => id !== cardId);
        } else {
            newPinned = [...pinnedIds, cardId];
        }
        setPinnedIds(newPinned);
        localStorage.setItem('pinned_ids', JSON.stringify(newPinned));
    };

    // Derived State: Sorted Cards
    const sortedCards = useMemo(() => {
        if (!cards) return [];
        const activeCards = cards.filter(c => c.status !== "draft");
        return activeCards.sort((a, b) => {
            const pinA = pinnedIds.includes(a.id);
            const pinB = pinnedIds.includes(b.id);
            if (pinA && !pinB) return -1;
            if (!pinA && pinB) return 1;

            if (pinA && pinB) {
                // Both pinned: simple order
                return pinnedIds.indexOf(a.id) - pinnedIds.indexOf(b.id);
            }

            // Neither pinned: use cardOrder
            const idxA = cardOrder.indexOf(a.id);
            const idxB = cardOrder.indexOf(b.id);
            if (idxA !== -1 && idxB !== -1) return idxA - idxB;
            if (idxA !== -1) return -1;
            if (idxB !== -1) return 1;
            return 0;
        });
    }, [cards, pinnedIds, cardOrder]);


    // 获取卡片的实时数据（从 WebSocket 数据中查找，需匹配交易所方向）
    const getCardRealTimeData = useCallback((symbol: string, type: string, exchangeA: string, exchangeB: string) => {
        const dataSource = type === "FF" ? arbitrageData?.ff : arbitrageData?.sf;
        if (!dataSource || dataSource.length === 0) return null;

        const suffixA = type === "SF" ? "spot" : "linear";
        const suffixB = "linear";

        const getKey = (ex: string, s: string) => {
            const k = ex.trim().toLowerCase();
            if (k === "binance") return s === "linear" ? "binance_future" : "binance";
            if (k === "bybit") return s === "linear" ? "bybit_linear" : "bybit_spot";
            return `${k}_${s}`;
        };

        const keyA = getKey(exchangeA, suffixA);
        const keyB = getKey(exchangeB, suffixB);

        // Find matching item (Long A, Short B) -> details.ex1=A, details.ex2=B
        const item = dataSource.find((opp) => {
            if (opp.symbol !== symbol) return false;
            if (opp.details) {
                return opp.details.ex1 === keyA && opp.details.ex2 === keyB;
            }
            return opp.pair === `${keyA}/${keyB}`;
        });

        if (!item) return null;
        return {
            openSpread: item.openSpread,
            closeSpread: item.closeSpread,
            indexPrice: item.indexPriceB || 0,
            indexPriceA: item.indexPriceA || 0,
            indexPriceB: item.indexPriceB || 0,
            netFundingRate: item.netFundingRate,
            indexDiffA: item.indexDiffA,
            indexDiffB: item.indexDiffB,
            fundingRateA: item.fundingRateA,
            fundingRateB: item.fundingRateB,
            fundingIntervalA: item.fundingIntervalA,
            fundingIntervalB: item.fundingIntervalB,
            fundingMaxA: item.fundingMaxA,
            fundingMinA: item.fundingMinA,
            fundingMaxB: item.fundingMaxB,
            fundingMinB: item.fundingMinB
        };
    }, [arbitrageData]);

    // 计算费率结算倒计时（基于本地时间）
    // interval 可以是数字（小时）或字符串（如 "8h"）
    const getFundingCountdown = useCallback((interval: string | number | undefined | null) => {
        // 解析 interval 为小时数
        let hours = 8; // 默认8小时
        if (typeof interval === 'number') {
            hours = interval;
        } else if (typeof interval === 'string') {
            hours = parseInt(interval.replace('h', '')) || 8;
        }
        if (!hours || hours <= 0) return "--:--:--";

        const now = new Date();

        // 计算今天的所有结算时间点 (UTC)
        const settlements = [];
        for (let h = 0; h < 24; h += hours) {
            settlements.push(h);
        }

        // 找到下一个结算时间
        const utcHour = now.getUTCHours();
        const utcMin = now.getUTCMinutes();
        const utcSec = now.getUTCSeconds();
        const currentMinutes = utcHour * 60 + utcMin + utcSec / 60;

        let nextSettlement = 24 * 60; // 默认明天0点
        for (const h of settlements) {
            const settlementMinutes = h * 60;
            if (settlementMinutes > currentMinutes) {
                nextSettlement = settlementMinutes;
                break;
            }
        }
        if (nextSettlement === 24 * 60) {
            nextSettlement = settlements[0] * 60 + 24 * 60; // 明天第一个结算时间
        }

        const diffMinutes = nextSettlement - currentMinutes;
        const diffSeconds = Math.floor(diffMinutes * 60);
        const h = Math.floor(diffSeconds / 3600);
        const m = Math.floor((diffSeconds % 3600) / 60);
        const s = diffSeconds % 60;

        return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }, []);

    // 切换卡片状态 (Optimistic + Direct API)
    const toggleCardStatus = async (card: TradingCard) => {
        const cardId = card.id;
        const originalStatus = card.status;
        const newStatus = originalStatus === 'running' ? 'paused' : 'running';

        setCards(prev => prev.map(c => c.id === cardId ? { ...c, status: newStatus } : c));

        try {
            const res = await fetch(`${API_BASE}/api/trading/card/${cardId}/toggle`, { method: "POST" });
            const data = await res.json();
            if (!data.success) {
                setCards(prev => prev.map(c => c.id === cardId ? { ...c, status: originalStatus } : c));
            }
        } catch (e) {
            console.error("Toggle request failed", e);
            setCards(prev => prev.map(c => c.id === cardId ? { ...c, status: originalStatus } : c));
        }
    };

    // 全局启动监控
    const startMonitor = async () => {
        if (!canStartMonitor) {
            alert("请先配置交易所 API");
            return;
        }
        setMonitorStatus('running');
        try {
            const res = await fetch(`${API_BASE}/api/monitor/start`, { method: "POST" });
            const data = await res.json();
            if (!data.success) setMonitorStatus('stopped');
        } catch (e) {
            console.error("Start monitor failed", e);
            setMonitorStatus('stopped');
        }
    };

    // 停止监控
    const stopMonitor = async () => {
        setMonitorStatus('stopped');
        try {
            const res = await fetch(`${API_BASE}/api/monitor/stop`, { method: "POST" });
            const data = await res.json();
            if (!data.success) setMonitorStatus(data.status || 'running');
        } catch (e) {
            console.error("Stop monitor failed", e);
            setMonitorStatus('running');
        }
    };

    // 重启监控
    const restartMonitor = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/monitor/restart`, { method: "POST" });
            const data = await res.json();
            setMonitorStatus(data.status);
        } catch (e) {
            console.error("Restart monitor failed", e);
        }
    };

    // 添加梯度
    const addLadderStep = () => {
        setNewCard({
            ...newCard,
            ladder: [...newCard.ladder, { spread: 0, amount: 0 }]
        });
    };

    // 删除梯度
    const removeLadderStep = (index: number) => {
        setNewCard({
            ...newCard,
            ladder: newCard.ladder.filter((_: any, i: number) => i !== index)
        });
    };

    // 更新梯度
    const updateLadderStep = (index: number, field: 'spread' | 'amount', value: number) => {
        const updated = [...newCard.ladder];
        updated[index][field] = value;
        setNewCard({ ...newCard, ladder: updated });
    };

    // 格式化时间
    const formatTime = (date: Date) => {
        return date.toLocaleTimeString('zh-CN', { hour12: false });
    };

    // 统计运行中的卡片数量
    const runningCount = cards.filter(c => c.status === "running").length;

    return (
        <div className={`min-h-screen transition-colors duration-300 ${theme === "dark" ? "bg-[#0d1117] text-slate-200" : "bg-gray-50 text-gray-900"}`} style={{ fontFamily: "Inter, sans-serif" }}>
            {/* 顶部导航 */}
            <header className={`${theme === "dark" ? "bg-[#161b22] border-[#30363d]" : "bg-white border-gray-200"} border-b px-6 py-3 shadow-sm relative`}>
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 bg-cyan-500 rounded-lg flex items-center justify-center text-white font-bold">
                            A
                        </div>
                        <h1 className={`text - xl font - bold tracking - tight ${theme === "dark" ? "text-white" : "text-gray-900"} `}>Arbitrage Pro</h1>
                        <span className="px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-500 text-xs font-medium border border-cyan-500/20">
                            v1.0.0
                        </span>
                    </div>

                    {/* 中间时钟 + 控制按钮 */}
                    <div className="flex items-center gap-3">
                        <div className={`px-3 py-1 rounded-lg font-mono text-3xl font-extrabold text-white tracking-wider shadow-lg transition-colors duration-500 ${currentTime.getMinutes() >= 55 ? "bg-red-600 shadow-red-600/40 animate-pulse" : "bg-blue-600 shadow-blue-600/40"}`}>
                            {formatTime(currentTime)}
                        </div>
                        <button
                            onClick={startMonitor}
                            disabled={!canStartMonitor || monitorStatus === "running"}
                            className={`px - 4 py - 1.5 rounded - lg text - sm font - medium transition ${monitorStatus === "running"
                                ? "bg-green-600 cursor-default"
                                : canStartMonitor
                                    ? "bg-blue-600 hover:bg-blue-500"
                                    : "bg-slate-600 cursor-not-allowed"
                                } `}
                        >
                            {monitorStatus === "running" ? "监控中" : "启动"}
                        </button>
                        <button
                            onClick={stopMonitor}
                            disabled={monitorStatus === "stopped"}
                            className={`px - 3 py - 1.5 rounded - lg text - sm transition ${monitorStatus === "stopped"
                                ? "bg-slate-600 cursor-not-allowed"
                                : "bg-red-600/80 hover:bg-red-500"
                                } `}
                        >
                            停止
                        </button>
                        <button
                            onClick={restartMonitor}
                            className="p-1.5 rounded-lg hover:bg-slate-700/50 transition"
                            title="重启监控"
                        >
                            <RotateCcw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                        </button>
                    </div>

                    {/* 右侧版本 */}
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setShowTimeTool(!showTimeTool)}
                            className={`p - 1.5 rounded hover: bg - slate - 700 transition ${showTimeTool ? "text-cyan-400 bg-slate-700" : "text-slate-500"} `}
                            title="时间戳工具"
                        >
                            <Clock className="w-4 h-4" />
                        </button>
                        <div className="text-xs text-slate-500">v1.0.0</div>
                    </div>
                </div>

                {/* 时间戳工具弹窗 */}
                {showTimeTool && <TimestampTool onClose={() => setShowTimeTool(false)} theme={theme} />}

                {/* 草稿箱弹窗 */}
                {showDraftBox && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm shadow-2xl">
                        <div className={`w-full max-w-2xl rounded-xl border overflow-hidden flex flex-col max-h-[85vh] ${theme === "dark" ? "bg-[#161b22] border-[#30363d]" : "bg-white border-gray-200"}`}>
                            <div className={`p-4 border-b flex items-center justify-between ${theme === "dark" ? "border-slate-800" : "border-gray-200"}`}>
                                <h3 className={`font-bold flex items-center gap-2 ${theme === "dark" ? "text-slate-200" : "text-gray-800"}`}>
                                    <Package className="w-5 h-5 text-slate-400" />
                                    草稿箱 (已删除卡片)
                                </h3>
                                <button
                                    onClick={() => setShowDraftBox(false)}
                                    className={`p-1.5 rounded-lg transition-colors ${theme === "dark" ? "hover:bg-slate-800 text-slate-400" : "hover:bg-gray-100 text-gray-500"}`}
                                >
                                    <X className="w-5 h-5" />
                                </button>
                            </div>

                            <div className={`p-4 overflow-y-auto flex-1 ${theme === "dark" ? "bg-[#0d1117]" : "bg-gray-50"}`}>
                                {cards.filter(c => c.status === "draft").length === 0 ? (
                                    <div className="py-12 text-center text-slate-500 flex flex-col items-center">
                                        <Package className="w-12 h-12 mb-3 opacity-20" />
                                        草稿箱为空
                                    </div>
                                ) : (
                                    <div className="space-y-3">
                                        {cards.filter(c => c.status === "draft").map(card => (
                                            <div key={card.id} className={`flex items-center justify-between p-3 rounded-lg border ${theme === "dark" ? "bg-[#161b22] border-slate-700" : "bg-white border-gray-200"} shadow-sm`}>
                                                <div className="flex flex-col">
                                                    <span className={`font-bold text-lg ${theme === "dark" ? "text-gray-200" : "text-gray-800"}`}>
                                                        {card.symbol}
                                                    </span>
                                                    <span className="text-xs text-slate-500 mt-1">
                                                        {card.exchange_a} / {card.exchange_b} · {card.type}
                                                    </span>
                                                </div>
                                                <div className="flex gap-2">
                                                    <button
                                                        onClick={async () => {
                                                            await fetch(`${API_BASE}/api/trading/card/${card.id}`, {
                                                                method: "PUT",
                                                                headers: { "Content-Type": "application/json" },
                                                                body: JSON.stringify({ ...card, status: "paused" })
                                                            });
                                                            loadCards();
                                                        }}
                                                        className="px-3 py-1.5 text-sm font-medium rounded-md bg-cyan-600/10 text-cyan-500 hover:bg-cyan-600/20 border border-cyan-500/20 transition-colors"
                                                    >
                                                        恢复
                                                    </button>
                                                    <button
                                                        onClick={async () => {
                                                            if (confirm("确定彻底删除该卡片吗？将无法恢复！")) {
                                                                await fetch(`${API_BASE}/api/trading/card/${card.id}`, { method: "DELETE" });
                                                                loadCards();
                                                            }
                                                        }}
                                                        className="px-3 py-1.5 text-sm font-medium rounded-md bg-red-500/10 text-red-500 hover:bg-red-500/20 border border-red-500/20 transition-colors"
                                                    >
                                                        永久删除
                                                    </button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )}

                {/* 标签栏 */}
                <div className="flex items-center gap-6 mt-3 text-sm">
                    {["pairs", "profit", "exchanges", "events", "settings", "accounts", "log"].map((tabInfo, idx) => {
                        const tabKeys = ["pairs", "profit", "exchanges", "events", "settings", "accounts", "log"];
                        const tabNames = ["币对", "利润", "交易所", "事件", "设置", "账户", "日志"];
                        const tKey = tabKeys[idx];
                        const tName = tabNames[idx];
                        const isActive = activeTab === tKey;

                        return (
                            <button
                                key={tKey}
                                onClick={() => setActiveTab(tKey as any)}
                                className={`transition pb-2 border-b-2 font-medium ${isActive
                                    ? (theme === "dark" ? "text-white border-cyan-400" : "text-gray-900 border-cyan-500")
                                    : (theme === "dark" ? "text-slate-400 border-transparent hover:text-white" : "text-gray-500 border-transparent hover:text-gray-900")
                                    }`}
                            >
                                {tName}
                            </button>
                        );
                    })}
                </div>
            </header>


            {activeTab === "pairs" ? (
                <>
                    {/* 工具栏 */}
                    <div className={`${theme === "dark" ? "bg-[#0d1421] border-slate-800" : "bg-white border-gray-200"} border-b px-10 py-2`}>
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => setShowAddCard(true)}
                                    className="flex items-center gap-1 px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-sm transition"
                                >
                                    添加
                                </button>

                                <button onClick={handleDeleteAll} className="flex items-center gap-1 px-2 py-1.5 rounded hover:bg-slate-700 text-sm text-red-400 transition">
                                    删除
                                </button>
                                <button
                                    onClick={() => setSoundEnabled(!soundEnabled)}
                                    className={`flex items - center gap - 1 px - 2 py - 1.5 rounded hover: bg - slate - 700 text - sm transition ${soundEnabled ? "text-green-400" : "text-slate-400"} `}
                                    title={soundEnabled ? "Mute Effects" : "Enable Effects"}
                                >
                                    {soundEnabled ? <Volume2 className="w-3.5 h-3.5" /> : <VolumeX className="w-3.5 h-3.5" />}
                                    音效
                                </button>
                                <button
                                    onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                                    className="flex items-center gap-1 px-2 py-1.5 rounded hover:bg-slate-700 text-sm text-slate-400 transition"
                                    title={theme === "dark" ? "切换亮色主题" : "切换暗色主题"}
                                >
                                    {theme === "dark" ? "☀️" : "🌙"}
                                </button>
                            </div>

                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => setShowDraftBox(true)}
                                    className="flex items-center gap-1 px-3 py-1.5 rounded hover:bg-slate-700/50 text-sm transition"
                                >
                                    <Package className="w-3.5 h-3.5" />
                                    草稿箱 ({draftCount})
                                </button>
                            </div>
                        </div>
                    </div>



                    {/* 交易卡片网格 */}
                    <section className="px-6 pb-6">
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-3">
                            {sortedCards.map((card: TradingCard) => {
                                const rtData = getCardRealTimeData(card.symbol, card.type, card.exchange_a, card.exchange_b);
                                const countdownA = getFundingCountdown(rtData?.fundingIntervalA);
                                const countdownB = getFundingCountdown(rtData?.fundingIntervalB);
                                const isUrgentA = countdownA.startsWith("00:") && parseInt(countdownA.split(":")[1]) <= 5;
                                const isUrgentB = countdownB.startsWith("00:") && parseInt(countdownB.split(":")[1]) <= 5;

                                // 格式化费率: rate/interval/limit
                                const formatFunding = (rate?: number, interval?: string | number, min?: number, max?: number) => {
                                    if (rate === undefined) return "--";
                                    const sign = rate > 0 ? "+" : "";
                                    const rateStr = `${sign}${rate.toFixed(3)} `;
                                    const intStr = typeof interval === 'number' ? interval : (parseInt(String(interval).replace('h', '')) || 8);
                                    // limit: positive rate -> max cap, negative rate -> min cap
                                    const limit = rate >= 0 ? (max ?? "-") : (min ?? "-");
                                    return (
                                        <span>
                                            {rateStr}/<span className={intStr === 1 ? "text-red-500" : "text-green-500"}>{intStr}h</span>/{limit}
                                        </span>
                                    );
                                };
                                const textColor = theme === "light" ? "text-gray-700" : "text-gray-200";
                                const labelColor = theme === "light" ? "text-gray-500" : "text-gray-200";
                                const borderColor = theme === "light" ? "border-gray-100" : "border-slate-700";

                                // [New] Alarm State Calculation
                                const valA = card.position_value_a || 0;
                                const valB = card.position_value_b || 0;
                                const maxVal = Math.max(valA, valB);
                                let isAlarmState = false;
                                if (maxVal > 2) {
                                    const diff = Math.abs(valA - valB);
                                    const isImbalanced = (diff / maxVal) > 0.08;
                                    const isSingleLeg = (valA > 2 && valB < 1) || (valB > 2 && valA < 1);
                                    // [New] Only alarm if NOT syncing
                                    isAlarmState = (isImbalanced || isSingleLeg) && !card.is_syncing;
                                }

                                const cardBgClass = isAlarmState
                                    ? "bg-red-950/90 border-red-500 animate-pulse ring-2 ring-red-500 shadow-[0_0_15px_rgba(239,68,68,0.5)]"
                                    : card.is_syncing
                                        ? (theme === "light" ? "bg-amber-50 border-amber-500 ring-1 ring-amber-500" : "bg-[#0d1200] border-amber-600 ring-1 ring-amber-600")
                                        : (theme === "light" ? "bg-white border-gray-200" : "bg-[#050505] border-slate-800");

                                return (
                                    <div
                                        key={card.id}
                                        draggable
                                        onDragStart={(e) => handleDragStart(e, card.id)}
                                        onDragOver={(e) => handleDragOver(e, card.id)}
                                        onDrop={(e) => handleDrop(e, card.id)}
                                        className={`rounded-lg border shadow-sm text-[13px] transition-all duration-200 ${cardBgClass} ${draggedCardId === card.id ? 'opacity-50 border-dashed border-cyan-500' : ''} cursor-move relative overflow-hidden`}
                                        style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
                                    >
                                        {/* Instant Feedback Overlay */}
                                        {card.is_syncing && (
                                            <div className="absolute top-0 right-0 px-2 py-0.5 bg-amber-500 text-black text-[10px] font-bold z-10 rounded-bl shadow-sm">
                                                EXECUTING...
                                            </div>
                                        )}

                                        {/* 头部: 状态 + 币种 + 操作图标 */}
                                        <div className={`flex items-center justify-between px-3 py-2 border-b ${borderColor} gap-4`}>
                                            <div className="flex items-center gap-2">
                                                <button
                                                    onClick={() => handleToggleStatus(card)}
                                                    className={`p-1 rounded cursor-pointer hover:opacity-80 transition ${card.status === "running" ? "bg-cyan-50 text-cyan-500" : "bg-red-50 text-red-500"}`}
                                                    title={card.status === "running" ? "点击暂停" : "点击启用"}
                                                >
                                                    {card.status === "running" ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                                                </button>
                                                <span className={`font-bold text-[15px] ${theme === "light" ? "text-gray-900" : "text-white"}`}>{card.symbol}</span>
                                            </div>
                                            <div className="flex items-center gap-5 text-gray-400">
                                                <button onClick={() => handleReverseCard(card.id)} className="hover:text-purple-500 transition" title="创建反向卡片"><ArrowLeftRight className="w-3.5 h-3.5" /></button>
                                                {card.type === "SF" && (
                                                    <button onClick={() => handleCalibrateCard(card)} className="hover:text-amber-400 transition" title="强制校准现货账本"><Zap className="w-3.5 h-3.5" /></button>
                                                )}
                                                <button onClick={() => handleSyncCard(card)} className="hover:text-cyan-400 transition" title="校准仓位（从交易所重新拉取）"><RefreshCw className="w-3.5 h-3.5" /></button>
                                                <button onClick={() => handleEditCard(card)} className="hover:text-blue-500 transition"><Edit2 className="w-3.5 h-3.5" /></button>
                                                <button onClick={() => handleDeleteCard(card.id)} className="hover:text-red-500 transition"><Trash2 className="w-3.5 h-3.5" /></button>
                                                <button
                                                    onClick={() => togglePin(card.id)}
                                                    className={`hover:text-cyan-500 transition ${pinnedIds.includes(card.id) ? "text-cyan-500" : "text-gray-600"}`}
                                                    title={pinnedIds.includes(card.id) ? "取消置顶" : "置顶"}
                                                >
                                                    <Pin className={`w-3.5 h-3.5 ${pinnedIds.includes(card.id) ? "fill-current" : ""}`} />
                                                </button>
                                            </div>
                                        </div>

                                        {/* 数据区域 */}
                                        <div className="px-3 py-2 space-y-[3px] text-[13px] leading-relaxed">
                                            {/* 交易所 + 差价 */}
                                            <div className="flex justify-between items-center mb-1">
                                                <div className="flex items-center gap-1">
                                                    <span className={labelColor}>交易所:</span>
                                                    <span className={`px - 1.5 py - [1px] border rounded text - [12px] bg - transparent ${card.type === "SF" ? "border-green-500/50 text-green-500" : "border-yellow-500/50 text-yellow-500"} `}>{card.exchange_a}</span>
                                                    <span className="px-1.5 py-[1px] border border-yellow-500/50 text-yellow-500 rounded text-[12px] bg-transparent">{card.exchange_b}</span>
                                                </div>
                                                <span className={`text - [13px] font - medium ${textColor} `}>
                                                    {rtData?.openSpread !== undefined ? (rtData.openSpread >= 0 ? "" : "") + rtData.openSpread.toFixed(2) : "--"}%
                                                    <span className="text-gray-300 mx-1">/</span>
                                                    {rtData?.closeSpread?.toFixed(2) ?? "--"}%
                                                </span>
                                            </div>

                                            <div className="flex items-center justify-start gap-2">
                                                {card.is_syncing && (
                                                    <span className="text-[11px] px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400 animate-pulse">同步中...</span>
                                                )}
                                                <span className={labelColor}>仓位价值(U):</span>
                                                <span className={textColor}>
                                                    <NumberTicker value={card.position_value_a || 0} precision={0} />
                                                    <span className="mx-1">/</span>
                                                    <NumberTicker value={card.position_value_b || 0} precision={0} />
                                                </span>
                                                {card.pnl !== undefined && card.position_value > 0 && (() => {
                                                    // 第一种精确算法：真实两腿法币盈亏相加，再减去当前总价值的千分之二（作为双边开平联合预估手续费）
                                                    const totalRealPnl = ((card.pnl_a || 0) + (card.pnl_b || 0));
                                                    const feeEstimation = card.position_value * 0.002;
                                                    const adjustedPnl = totalRealPnl - feeEstimation;
                                                    return (
                                                        <NumberTicker
                                                            value={adjustedPnl}
                                                            precision={2}
                                                            prefix={adjustedPnl >= 0 ? "+" : ""}
                                                            className={`ml-2 font-medium ${adjustedPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}
                                                        />
                                                    );
                                                })()}
                                            </div>

                                            <div className="flex items-center justify-start gap-3">
                                                <div className="flex items-center gap-1.5">
                                                    <span className={labelColor}>开清条件:</span>
                                                    <span className={textColor}>{card.open_threshold.toFixed(2)}% / {card.close_threshold.toFixed(2)}%</span>
                                                </div>
                                                <div className="flex items-center gap-1 text-gray-400">
                                                    <button onClick={() => handleQuickUpdate(card, "threshold", "sub")} className="hover:text-gray-600 cursor-pointer" title="同时减小0.1%"><Minus className="w-3.5 h-3.5" /></button>
                                                    <button onClick={() => handleQuickUpdate(card, "threshold", "add")} className="hover:text-gray-600 cursor-pointer" title="同时增加0.1%"><PlusCircle className="w-3.5 h-3.5" /></button>
                                                </div>
                                            </div>

                                            <div className="flex items-center justify-start gap-2"><span className={labelColor}>实开/实清:</span><span className={textColor}>{card.open_spread?.toFixed(2) ?? "--"}% / {card.close_spread?.toFixed(2) ?? "--"}%</span></div>
                                            <div className="flex items-center justify-start gap-2"><span className={labelColor}>开仓均价:</span><span className={textColor}>{card.avg_price_a?.toFixed(4) || "--"} / {card.avg_price_b?.toFixed(4) || "--"}</span></div>
                                            <div className="flex items-center justify-start gap-2"><span className={labelColor}>仓位数量:</span><span className={textColor}>{card.position_qty_a?.toFixed(4) || "0.0000"} / {card.position_qty_b?.toFixed(4) || "0.0000"}</span></div>

                                            <div className="flex items-center justify-start gap-3">
                                                <div className="flex items-center gap-1.5">
                                                    <span className={labelColor}>仓位限额(U):</span>
                                                    <span className={textColor}>{card.max_position}</span>
                                                </div>
                                                <div className="flex items-center gap-1 text-gray-400">
                                                    <button onClick={() => handleQuickUpdate(card, "position", "sub")} className="hover:text-gray-600 cursor-pointer" title="减少100U"><Minus className="w-3.5 h-3.5" /></button>
                                                    <button onClick={() => handleQuickUpdate(card, "position", "add")} className="hover:text-gray-600 cursor-pointer" title="增加100U"><PlusCircle className="w-3.5 h-3.5" /></button>
                                                </div>
                                            </div>

                                            <div className="flex items-center justify-start gap-2"><span className={labelColor}>下单范围(U):</span><span className={textColor}>{card.order_min} / {card.order_max}</span></div>

                                            {/* 实时数据 */}
                                            <div className="flex items-center justify-start gap-2 mt-1">
                                                <span className={labelColor}>指数差价:</span>
                                                <span className={textColor}>
                                                    {(() => {
                                                        const diffA = rtData?.indexDiffA;
                                                        const diffB = rtData?.indexDiffB;

                                                        const fmt = (v?: number) => {
                                                            if (v === undefined || v === 0) return "--"; // Spot or missing
                                                            return `${v >= 0 ? "+" : ""}${v.toFixed(3)}% `;
                                                        };

                                                        return (
                                                            <span>
                                                                <span className={diffA && Math.abs(diffA) > 0.05 ? (diffA > 0 ? "text-green-500" : "text-red-500") : ""}>{fmt(diffA)}</span>
                                                                <span className="text-gray-300 mx-1">/</span>
                                                                <span className={diffB && Math.abs(diffB) > 0.05 ? (diffB > 0 ? "text-green-500" : "text-red-500") : ""}>{fmt(diffB)}</span>
                                                            </span>
                                                        );
                                                    })()}
                                                </span>
                                            </div>


                                            <div className="flex items-center justify-start gap-2">
                                                <span className={labelColor}>实时费率:</span>
                                                <span className="text-[12px]">
                                                    <span className={rtData?.netFundingRate && rtData.netFundingRate >= 0 ? "text-green-600" : "text-red-500"}>
                                                        {rtData?.netFundingRate !== undefined ? (rtData.netFundingRate >= 0 ? "+" : "") + rtData.netFundingRate.toFixed(3) : "--"}
                                                    </span>
                                                    <span className={`${textColor} ml - 1`}>
                                                        {formatFunding(rtData?.fundingRateA, rtData?.fundingIntervalA, rtData?.fundingMinA, rtData?.fundingMaxA)}
                                                    </span>
                                                    <span className="text-gray-300 mx-1">|</span>
                                                    <span className={textColor}>
                                                        {formatFunding(rtData?.fundingRateB, rtData?.fundingIntervalB, rtData?.fundingMinB, rtData?.fundingMaxB)}
                                                    </span>
                                                </span>
                                            </div>
                                            <div className="flex items-center justify-start gap-2">
                                                <div className="flex items-center gap-1">
                                                    <span className={labelColor}>费率结算:</span>
                                                    <span className={textColor}>
                                                        <span className={isUrgentA ? "text-red-500 font-bold" : ""}>{countdownA}</span>
                                                        <span className="text-gray-300 mx-1">/</span>
                                                        <span className={isUrgentB ? "text-red-500 font-bold" : ""}>{countdownB}</span>
                                                    </span>
                                                </div>
                                                <HelpCircle className="w-3 h-3 text-gray-300" />
                                            </div>
                                            <div className="flex items-center justify-start gap-2">
                                                <div className="flex items-center gap-1">
                                                    <span className={labelColor}>实时MMR:</span>
                                                    <span className={textColor}>{(card.margin_ratio_a ? card.margin_ratio_a * 100 : 0).toFixed(2)}% / {(card.margin_ratio_b ? card.margin_ratio_b * 100 : 0).toFixed(2)}%</span>
                                                </div>
                                                <HelpCircle className="w-3 h-3 text-gray-300" />
                                            </div>

                                            {/* 爆率/ADL */}
                                            <div className="flex items-center justify-start gap-2 mt-1">
                                                <span className={labelColor}>爆率/ADL:</span>
                                                <span className={textColor}>
                                                    {(() => {
                                                        const getRisk = (mark: number, liq: number, qty: number) => {
                                                            // 纯粹的强平价距离计算 (如果接口不提供强平价如 PM账户则返回 --)
                                                            if (!qty || Math.abs(qty) < 0.0001 || !mark || !liq || liq <= 0) return "--";
                                                            const diff = Math.abs(mark - liq) / mark * 100;
                                                            return `${diff.toFixed(1)}%`;
                                                        };

                                                        const getAdlColor = (adl: number) => {
                                                            // Binance: 0-4, Bybit: 1-5
                                                            // Normalize: High is bad
                                                            if (adl >= 4) return "text-red-500";
                                                            if (adl >= 2) return "text-yellow-500";
                                                            return "text-green-500";
                                                        };

                                                        // Use Index Price as proxy for Mark if available, else Entry Price
                                                        const priceA = rtData?.indexPriceA || card.avg_price_a || 0;
                                                        const priceB = rtData?.indexPriceB || card.avg_price_b || 0;

                                                        const riskA = getRisk(priceA, card.liq_price_a || 0, card.position_qty_a || 0);
                                                        const riskB = getRisk(priceB, card.liq_price_b || 0, card.position_qty_b || 0);

                                                        const adlA = card.adl_a || 0;
                                                        const adlB = card.adl_b || 0;

                                                        return (
                                                            <div className="flex items-center">
                                                                <span>{riskA}</span>
                                                                {riskA !== "--" && <Circle className={`w-3 h-3 ml-1 ${getAdlColor(adlA)} fill-current`} />}
                                                                <span className="text-gray-300 mx-2">|</span>
                                                                <span>{riskB}</span>
                                                                {riskB !== "--" && <Circle className={`w-3 h-3 ml-1 ${getAdlColor(adlB)} fill-current`} />}
                                                            </div>
                                                        );
                                                    })()}
                                                </span>
                                            </div>



                                            {/* 开始时间 */}
                                            <div className="flex items-center justify-start gap-2 mt-1">
                                                <span className={labelColor}>开始时间:</span>
                                                <span className={labelColor}>
                                                    {card.start_time > 0 ? (() => {
                                                        const d = new Date(card.start_time);
                                                        return `${d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })} ${d.toLocaleTimeString('zh-CN', { hour12: false })}.${d.getMilliseconds().toString().padStart(3, '0')} `;
                                                    })() : "--"}
                                                </span>
                                            </div>
                                        </div>

                                        {/* 底部按钮 */}
                                        <div className={`flex gap - 4 px - 3 py - 3 mt - 1 ${theme === "dark" ? "border-t border-slate-700" : ""} `}>
                                            <button
                                                onClick={() => handleExecute(card)}
                                                disabled={card.open_disabled}
                                                className={`flex items - center justify - center gap - 2 px - 3 py - 1.5 text - [12px] border rounded shadow - sm hover: translate - y - px transition ${card.open_disabled
                                                    ? "text-gray-500 border-gray-700 cursor-not-allowed opacity-50"
                                                    : "text-yellow-400 border-yellow-500/50 hover:bg-yellow-500/10"
                                                    } `}
                                            >
                                                <AlertTriangle className="w-3.5 h-3.5" />
                                                一键开仓
                                            </button>
                                            <button
                                                onClick={() => handleClose(card)}
                                                disabled={card.close_disabled}
                                                className={`flex items - center justify - center gap - 2 px - 3 py - 1.5 text - [12px] border rounded shadow - sm hover: translate - y - px transition ${card.close_disabled
                                                    ? "text-gray-500 border-gray-700 cursor-not-allowed opacity-50"
                                                    : "text-red-400 border-red-500/50 hover:bg-red-500/10"
                                                    } `}
                                            >
                                                <Siren className="w-3.5 h-3.5" />
                                                一键清仓
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}

                            {cards.length === 0 && (
                                <div className="col-span-full text-center py-12 text-slate-500">
                                    暂无交易卡片，点击"添加"按钮创建
                                </div>
                            )}
                        </div>
                    </section>
                </>
            ) : activeTab === "profit" ? (
                <ProfitTab theme={theme} />
            ) : activeTab === "log" ? (
                <LogTab theme={theme} />
            ) : (
                <section className="px-5 py-5 max-w-7xl mx-auto">
                    <ExchangeTab />
                </section>
            )
            }

            {/* 添加卡片弹窗 */}
            {
                showAddCard && (
                    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 overflow-y-auto py-6">
                        <div
                            className={`${theme === "dark" ? "bg-[#12171f] border-slate-700 text-slate-200" : "bg-white border-gray-200 text-gray-900"} rounded - xl p - 5 w - full max - w - xl border mx - 4 shadow - 2xl transition - transform duration - 75`}
                            style={{ transform: `translate(${modalPos.x}px, ${modalPos.y}px)` }}
                        >
                            <div
                                className="flex items-center justify-between mb-4 cursor-move select-none"
                                onMouseDown={onModalHeaderMouseDown}
                            >
                                <h3 className="text-base font-bold">{editingCardId ? "编辑卡片" : "添加卡片"} <span className="text-xs text-slate-400 font-normal">(按住此处可拖拽)</span></h3>
                                <div className="flex items-center gap-2">
                                    <button
                                        onClick={() => { setShowAddCard(false); setEditingCardId(null); }}
                                        className="px-3 py-1 rounded bg-transparent border border-slate-600 hover:bg-slate-800 text-slate-300 text-xs transition"
                                    >
                                        取消
                                    </button>
                                    <button
                                        onClick={handleAddCard}
                                        className="px-4 py-1 rounded border border-blue-500 text-blue-400 bg-transparent hover:bg-blue-500 text-xs transition"
                                    >
                                        {editingCardId ? "保存" : "确定"}
                                    </button>
                                </div>
                            </div>

                            <div className="space-y-3 text-sm">
                                {/* 币种 */}
                                <div className="flex items-center gap-3">
                                    <label className={`w-20 text-xs flex-shrink-0 ${theme === "light" ? "text-gray-700 font-medium" : "text-gray-200"}`}>
                                        <span className="text-red-400">*</span> 币种
                                    </label>
                                    <div className="relative flex-1">
                                        <input
                                            type="text"
                                            list="symbolSuggestions"
                                            className={`w-full bg-transparent border border-slate-600 text-slate-300 rounded pl-3 pr-8 py-1.5 text-sm uppercase ${editingCardId ? "opacity-50 cursor-not-allowed" : ""}`}
                                            placeholder="输入币种 (如 btc)"
                                            value={newCard.symbol}
                                            disabled={!!editingCardId}
                                            onChange={e => {
                                                const val = e.target.value.toUpperCase();
                                                // Auto-append USDT if not present and value has content
                                                setNewCard({ ...newCard, symbol: val });
                                            }}
                                            onBlur={e => {
                                                const val = e.target.value.toUpperCase();
                                                if (val && !val.includes("USDT") && !val.includes("USD")) {
                                                    setNewCard({ ...newCard, symbol: val + "USDT" });
                                                }
                                            }}
                                        />
                                        {!editingCardId && newCard.symbol && (
                                            <button
                                                onClick={() => setNewCard({ ...newCard, symbol: "" })}
                                                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 p-1 hover:bg-transparent border border-slate-600 text-slate-400 rounded-full transition-colors"
                                                title="清空"
                                            >
                                                ✕
                                            </button>
                                        )}
                                        {!editingCardId && (
                                            <datalist id="symbolSuggestions">
                                                {Array.from(new Set(
                                                    [...arbitrageData.sf, ...arbitrageData.ff, ...arbitrageData.ss]
                                                        .filter((opp: any) => opp.symbol && opp.symbol.toLowerCase().includes((newCard.symbol || "").toLowerCase()))
                                                        .map((opp: any) => opp.symbol)
                                                ))
                                                    .slice(0, 10)
                                                    .map((sym: string) => (
                                                        <option key={sym} value={sym} />
                                                    ))}
                                            </datalist>
                                        )}
                                    </div>
                                </div>

                                {/* 状态 */}
                                <div className="flex items-center gap-3">
                                    <label className={`w-20 text-xs flex-shrink-0 ${theme === "light" ? "text-gray-700 font-medium" : "text-gray-200"}`}>
                                        <span className="text-red-400">*</span> 状态
                                    </label>
                                    <div className="flex items-center gap-4">
                                        <label className="flex items-center gap-1.5 cursor-pointer text-xs">
                                            <input
                                                type="radio"
                                                name="status"
                                                checked={newCard.status === "running"}
                                                onChange={() => setNewCard({ ...newCard, status: "running" })}
                                                className="accent-cyan-500"
                                            />
                                            已启用
                                        </label>
                                        <label className="flex items-center gap-1.5 cursor-pointer text-xs">
                                            <input
                                                type="radio"
                                                name="status"
                                                checked={newCard.status === "paused"}
                                                onChange={() => setNewCard({ ...newCard, status: "paused" })}
                                                className="accent-orange-500"
                                            />
                                            <span className="text-orange-400">已暂停</span>
                                        </label>
                                    </div>
                                </div>

                                {/* 类型 */}
                                <div className="flex items-center gap-3">
                                    <label className={`w-20 text-xs flex-shrink-0 ${theme === "light" ? "text-gray-700 font-medium" : "text-gray-200"}`}>
                                        <span className="text-red-400">*</span> 类型
                                    </label>
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={() => !editingCardId && setNewCard({ ...newCard, type: "SF" })}
                                            disabled={!!editingCardId}
                                            className={`px-3 py-1 rounded border text-xs transition ${newCard.type === "SF"
                                                ? "bg-green-500/20 border-green-500 text-green-400"
                                                : "border-slate-600 text-slate-400 hover:border-slate-500"
                                                } ${editingCardId ? "opacity-50 cursor-not-allowed" : ""}`}
                                        >
                                            🟢🟡 (现期)
                                        </button>
                                        <button
                                            onClick={() => !editingCardId && setNewCard({ ...newCard, type: "FF" })}
                                            disabled={!!editingCardId}
                                            className={`px-3 py-1 rounded border text-xs transition ${newCard.type === "FF"
                                                ? "bg-blue-500/20 border-blue-500 text-blue-400"
                                                : "border-slate-600 text-slate-400 hover:border-slate-500"
                                                } ${editingCardId ? "opacity-50 cursor-not-allowed" : ""}`}
                                        >
                                            🟡🟡 (期期)
                                        </button>
                                    </div>
                                </div>

                                {/* 开仓差价 */}
                                <div className="flex items-center gap-3">
                                    <label className={`w-20 text-xs flex-shrink-0 ${theme === "light" ? "text-gray-700 font-medium" : "text-gray-200"}`}>
                                        <span className="text-red-400">*</span> 开仓差价
                                    </label>
                                    <div className="flex items-center gap-2 flex-1">
                                        <input
                                            type="number"
                                            step="0.01"
                                            className="w-16 bg-transparent border border-slate-600 text-slate-300 rounded px-2 py-1.5 text-sm text-center"
                                            value={newCard.openThreshold}
                                            onChange={e => setNewCard({ ...newCard, openThreshold: e.target.value })}
                                        />
                                        <span className="text-slate-400 text-xs">%</span>
                                        <button className="p-1 rounded bg-transparent border border-slate-600 hover:bg-slate-800 text-slate-300 text-xs">➖</button>
                                        <button className="p-1 rounded bg-transparent border border-slate-600 hover:bg-slate-800 text-slate-300 text-xs">➕</button>
                                        <label className="flex items-center gap-1 ml-2 cursor-pointer text-xs">
                                            <input
                                                type="checkbox"
                                                checked={newCard.openDisabled}
                                                onChange={e => {
                                                    const checked = e.target.checked;
                                                    setNewCard({
                                                        ...newCard,
                                                        openDisabled: checked,
                                                        openThreshold: checked ? "900" : newCard.openThreshold
                                                    });
                                                }}
                                                className="accent-red-500"
                                            />
                                            禁开
                                        </label>
                                        <label className="flex items-center gap-1 cursor-pointer text-xs">
                                            <input
                                                type="checkbox"
                                                checked={newCard.ladderEnabled}
                                                onChange={e => setNewCard({ ...newCard, ladderEnabled: e.target.checked })}
                                                className="accent-blue-500"
                                            />
                                            梯度
                                        </label>
                                    </div>
                                </div>

                                {/* 清仓差价 */}
                                <div className="flex items-center gap-3">
                                    <label className={`w-20 text-xs flex-shrink-0 ${theme === "light" ? "text-gray-700 font-medium" : "text-gray-200"}`}>
                                        <span className="text-red-400">*</span> 清仓差价
                                    </label>
                                    <div className="flex items-center gap-2 flex-1">
                                        <input
                                            type="number"
                                            step="0.01"
                                            className="w-16 bg-transparent border border-slate-600 text-slate-300 rounded px-2 py-1.5 text-sm text-center"
                                            value={newCard.closeThreshold}
                                            onChange={e => setNewCard({ ...newCard, closeThreshold: e.target.value })}
                                        />
                                        <span className="text-slate-400 text-xs">%</span>
                                        <button className="p-1 rounded bg-transparent border border-slate-600 hover:bg-slate-800 text-slate-300 text-xs">➖</button>
                                        <button className="p-1 rounded bg-transparent border border-slate-600 hover:bg-slate-800 text-slate-300 text-xs">➕</button>
                                        <label className="flex items-center gap-1 ml-2 cursor-pointer text-xs">
                                            <input
                                                type="checkbox"
                                                checked={newCard.closeDisabled}
                                                onChange={e => {
                                                    const checked = e.target.checked;
                                                    setNewCard({
                                                        ...newCard,
                                                        closeDisabled: checked,
                                                        closeThreshold: checked ? "-999" : newCard.closeThreshold
                                                    });
                                                }}
                                                className="accent-red-500"
                                            />
                                            禁清
                                        </label>
                                    </div>
                                </div>

                                {/* 仓位限额 */}
                                <div className="flex items-center gap-3">
                                    <label className={`w-20 text-xs flex-shrink-0 ${theme === "light" ? "text-gray-700 font-medium" : "text-gray-200"}`}>
                                        <span className="text-red-400">*</span> 仓位限额
                                    </label>
                                    <div className="flex items-center gap-2 flex-1">
                                        <input
                                            type="number"
                                            className="flex-1 bg-transparent border border-slate-600 text-slate-300 rounded px-2 py-1.5 text-sm"
                                            value={newCard.maxPosition}
                                            onChange={e => setNewCard({ ...newCard, maxPosition: e.target.value })}
                                        />
                                        <span className="px-2 py-1 bg-transparent border border-slate-600 text-slate-400 rounded text-xs">USDT</span>
                                    </div>
                                </div>

                                {/* 杠杆倍数 */}
                                <div className="flex items-center gap-3">
                                    <label className={`w-20 text-xs flex-shrink-0 ${theme === "light" ? "text-gray-700 font-medium" : "text-gray-200"}`}>
                                        <span className="text-red-400">*</span> 杠杆倍数
                                    </label>
                                    <div className="flex items-center gap-1">
                                        {[1, 2, 3, 4, 5, 6].map(lev => (
                                            <button
                                                key={lev}
                                                onClick={() => !editingCardId && setNewCard({ ...newCard, leverage: lev })}
                                                disabled={!!editingCardId}
                                                className={`w-7 h-7 rounded text-xs transition ${newCard.leverage === lev
                                                    ? "border border-blue-500 text-blue-400 bg-transparent"
                                                    : "bg-transparent border border-slate-600 hover:bg-slate-800 text-slate-400"
                                                    } ${editingCardId ? "opacity-50 cursor-not-allowed" : ""}`}
                                            >
                                                {lev}x
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                {/* 交易所 */}
                                <div className="flex items-center gap-3">
                                    <label className={`w-20 text-xs flex-shrink-0 ${theme === "light" ? "text-gray-700 font-medium" : "text-gray-200"}`}>
                                        <span className="text-red-400">*</span> 交易所
                                    </label>
                                    <div className="flex items-center gap-2">
                                        <select
                                            className={`bg-transparent border border-slate-600 text-slate-300 rounded px-2 py-1.5 text-xs ${editingCardId ? "opacity-50 cursor-not-allowed" : ""}`}
                                            value={newCard.exchangeA}
                                            disabled={!!editingCardId}
                                            onChange={e => setNewCard({ ...newCard, exchangeA: e.target.value })}
                                        >
                                            <option value="binance">Binance</option>
                                            <option value="bybit">Bybit</option>
                                            <option value="bitget">Bitget</option>
                                            <option value="gate">Gate</option>
                                            <option value="nado">Nado</option>
                                        </select>
                                        <span className="text-slate-500 text-xs">A</span>
                                        <select
                                            className={`bg-transparent border border-slate-600 text-slate-300 rounded px-2 py-1.5 text-xs ${editingCardId ? "opacity-50 cursor-not-allowed" : ""}`}
                                            value={newCard.exchangeB}
                                            disabled={!!editingCardId}
                                            onChange={e => setNewCard({ ...newCard, exchangeB: e.target.value })}
                                        >
                                            <option value="bybit">Bybit</option>
                                            <option value="binance">Binance</option>
                                            <option value="bitget">Bitget</option>
                                            <option value="gate">Gate</option>
                                            <option value="nado">Nado</option>
                                        </select>
                                        <span className="text-slate-500 text-xs">B</span>
                                    </div>
                                </div>

                                {/* 开始时间（时间戳） */}
                                <div className="flex items-center gap-3">
                                    <label className={`w - 20 text - xs flex - shrink - 0 ${theme === "light" ? "text-gray-700 font-medium" : "text-gray-200"} `}>开始时间(ms)</label>
                                    <div className="flex items-center gap-2 flex-1">
                                        <input
                                            type="number"
                                            className="flex-1 bg-transparent border border-slate-600 text-slate-300 rounded px-2 py-1.5 text-sm"
                                            value={newCard.startTime}
                                            onChange={e => setNewCard({ ...newCard, startTime: e.target.value })}
                                            placeholder="时间戳 (毫秒)"
                                        />
                                        <button
                                            onClick={() => {
                                                const nextHour = Math.ceil(Date.now() / 3600000) * 3600000;
                                                setNewCard({ ...newCard, startTime: nextHour });
                                            }}
                                            className="px-2 py-1 rounded border border-blue-500 text-blue-400 bg-transparent hover:bg-blue-500 text-xs whitespace-nowrap transition"
                                        >
                                            整点
                                        </button>
                                        <span className="text-[10px] text-slate-500 w-24 text-right truncate">
                                            {newCard.startTime > 0 ? (() => {
                                                const d = new Date(parseInt(newCard.startTime));
                                                return `${d.toLocaleTimeString('zh-CN', { hour12: false })}.${d.getMilliseconds().toString().padStart(3, '0')} `;
                                            })() : "未设置"}
                                        </span>
                                    </div>
                                </div>

                                {/* 单笔额 */}
                                <div className="flex items-center gap-3">
                                    <label className={`w - 20 text - xs flex - shrink - 0 ${theme === "light" ? "text-gray-700 font-medium" : "text-gray-200"} `}>
                                        <span className="text-red-400">*</span> 最小单笔额
                                    </label>
                                    <div className="flex items-center gap-2 flex-1">
                                        <input
                                            type="number"
                                            className="flex-1 bg-transparent border border-slate-600 text-slate-300 rounded px-2 py-1.5 text-sm"
                                            value={newCard.orderMin}
                                            onChange={e => setNewCard({ ...newCard, orderMin: e.target.value })}
                                        />
                                        <span className="px-2 py-1 bg-transparent border border-slate-600 text-slate-400 rounded text-xs">USDT</span>
                                    </div>
                                </div>

                                <div className="flex items-center gap-3">
                                    <label className={`w - 20 text - xs flex - shrink - 0 ${theme === "light" ? "text-gray-700 font-medium" : "text-gray-200"} `}>
                                        <span className="text-red-400">*</span> 最大单笔额
                                    </label>
                                    <div className="flex items-center gap-2 flex-1">
                                        <input
                                            type="number"
                                            className="flex-1 bg-transparent border border-slate-600 text-slate-300 rounded px-2 py-1.5 text-sm"
                                            value={newCard.orderMax}
                                            onChange={e => setNewCard({ ...newCard, orderMax: e.target.value })}
                                        />
                                        <span className="px-2 py-1 bg-transparent border border-slate-600 text-slate-400 rounded text-xs">USDT</span>
                                    </div>
                                </div>

                                {/* 止损 */}
                                <div className="flex items-center gap-3">
                                    <label className={`w - 20 text - xs flex - shrink - 0 ${theme === "light" ? "text-gray-700 font-medium" : "text-gray-200"} `}>止损(可选)</label>
                                    <div className="flex items-center gap-2 flex-1">
                                        <input
                                            type="number"
                                            step="0.1"
                                            className="flex-1 bg-transparent border border-slate-600 text-slate-300 rounded px-2 py-1.5 text-sm"
                                            value={newCard.stopLoss}
                                            onChange={e => setNewCard({ ...newCard, stopLoss: e.target.value })}
                                        />
                                        <span className="text-slate-400 text-xs">%</span>
                                    </div>
                                </div>

                                {/* 价格报警 */}
                                <div className="flex items-center gap-3">
                                    <label className={`w - 20 text - xs flex - shrink - 0 ${theme === "light" ? "text-gray-700 font-medium" : "text-gray-200"} `}>价格报警(可选)</label>
                                    <div className="flex items-center gap-2 flex-1">
                                        <input
                                            type="number"
                                            step="0.1"
                                            className="flex-1 bg-transparent border border-slate-600 text-slate-300 rounded px-2 py-1.5 text-sm"
                                            value={newCard.priceAlert}
                                            onChange={e => setNewCard({ ...newCard, priceAlert: e.target.value })}
                                        />
                                        <span className="text-slate-400 text-xs">%</span>
                                    </div>
                                </div>

                                {/* 梯度配置 */}
                                {newCard.ladderEnabled && (
                                    <div className="border border-slate-700 rounded p-3 mt-2">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="text-xs font-medium">梯度配置</span>
                                            <button
                                                onClick={addLadderStep}
                                                className="text-xs px-2 py-0.5 border border-blue-500 text-blue-400 bg-transparent rounded hover:bg-blue-500 transition"
                                            >
                                                + 添加
                                            </button>
                                        </div>

                                        <div className="space-y-1.5">
                                            {newCard.ladder.map((step: any, i: number) => (
                                                <div key={i} className="flex items-center gap-2">
                                                    <span className="text-xs text-slate-400 w-4">#{i + 1}</span>
                                                    <input
                                                        type="number"
                                                        step="0.1"
                                                        className="w-14 bg-transparent border border-slate-600 text-slate-400 rounded px-1.5 py-0.5 text-xs"
                                                        value={step.spread}
                                                        onChange={e => updateLadderStep(i, 'spread', parseFloat(e.target.value) || 0)}
                                                    />
                                                    <span className="text-xs text-slate-400">%</span>
                                                    <input
                                                        type="number"
                                                        className="w-16 bg-transparent border border-slate-600 text-slate-400 rounded px-1.5 py-0.5 text-xs"
                                                        value={step.amount}
                                                        onChange={e => updateLadderStep(i, 'amount', parseFloat(e.target.value) || 0)}
                                                    />
                                                    <span className="text-xs text-slate-400">U</span>
                                                    <button
                                                        onClick={() => removeLadderStep(i)}
                                                        className="p-0.5 text-red-400 hover:bg-transparent border border-slate-600 text-slate-400 rounded"
                                                    >
                                                        <X className="w-3 h-3" />
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )
            }
        </div >
    );
}
