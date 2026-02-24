
import { useState, useEffect, useRef } from "react";

const API_BASE = "";

const LogTab = ({ theme }: { theme: string }) => {
    const [logs, setLogs] = useState<string[]>([]);
    const [autoScroll, setAutoScroll] = useState(true);
    const scrollRef = useRef<HTMLDivElement>(null);

    const fetchLogs = async () => {
        try {
            const res = await fetch(`${API_BASE}/api/log?limit=200`);
            if (res.ok) {
                const data = await res.json();
                setLogs(data.logs || []);
            }
        } catch (e) {
            console.error(e);
        }
    };

    useEffect(() => {
        fetchLogs();
        const timer = setInterval(fetchLogs, 2000);
        return () => clearInterval(timer);
    }, []);

    useEffect(() => {
        if (autoScroll && scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs, autoScroll]);

    const handleScroll = () => {
        if (scrollRef.current) {
            const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
            const isBottom = scrollHeight - scrollTop - clientHeight < 50;
            setAutoScroll(isBottom);
        }
    };

    const bgColor = theme === "dark" ? "bg-[#0d1117]" : "bg-gray-50";
    const textColor = theme === "dark" ? "text-slate-300" : "text-gray-700";
    const borderColor = theme === "dark" ? "border-[#30363d]" : "border-gray-200";

    return (
        <section className="px-5 py-5 max-w-7xl mx-auto h-[calc(100vh-140px)] flex flex-col">
            <div className={`flex justify-between items-center mb-2 px-1`}>
                <h3 className={`font-bold ${textColor}`}>系统日志 (System Logs)</h3>
                <div className="flex gap-2">
                    <button
                        onClick={() => setLogs([])}
                        className="text-xs px-2 py-1 rounded bg-red-500/10 text-red-500 hover:bg-red-500/20"
                    >
                        Clear View
                    </button>
                    <label className={`flex items-center gap-1 text-xs ${textColor}`}>
                        <input
                            type="checkbox"
                            checked={autoScroll}
                            onChange={(e) => setAutoScroll(e.target.checked)}
                        />
                        Auto-scroll
                    </label>
                </div>
            </div>

            <div
                ref={scrollRef}
                onScroll={handleScroll}
                className={`flex-1 overflow-y-auto p-4 rounded-xl border ${bgColor} ${borderColor} font-mono text-xs whitespace-pre-wrap`}
            >
                {logs.length === 0 ? (
                    <div className="text-gray-500 italic">暂无日志 / No logs available...</div>
                ) : (
                    logs.map((line, i) => (
                        <div key={i} className={`${textColor} border-b border-gray-700/10 py-0.5 hover:bg-white/5`}>
                            {line}
                        </div>
                    ))
                )}
            </div>
        </section>
    );
};

export default LogTab;
