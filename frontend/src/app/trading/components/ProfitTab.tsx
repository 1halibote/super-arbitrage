"use client";

import { useState, useEffect, useCallback } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

const API_BASE = "";

const ProfitTab = ({ theme }: { theme: string }) => {
    const [summary, setSummary] = useState<any>(null);
    const [records, setRecords] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedDate, setSelectedDate] = useState("");

    // Pagination State
    const [page, setPage] = useState(1);
    const [itemsPerPage] = useState(20);
    const [totalRecords, setTotalRecords] = useState(0);
    const [allDailyRecords, setAllDailyRecords] = useState<any[]>([]); // Cache for client-side pagination in daily mode

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            // Always fetch summary for Total/Month stats
            const sumRes = await fetch(`${API_BASE}/api/profit/summary`);
            if (!sumRes.ok) throw new Error(`Failed to fetch summary: ${sumRes.status} ${sumRes.statusText}`);

            const sumData = await sumRes.json();

            if (selectedDate) {
                // Fetch daily stats
                const dailyRes = await fetch(`${API_BASE}/api/profit/daily?date=${selectedDate}`);
                if (!dailyRes.ok) throw new Error(`Failed to fetch daily stats: ${dailyRes.status}`);

                const dailyData = await dailyRes.json();

                if (dailyData && sumData) {
                    sumData.today_pnl = dailyData.pnl;
                    sumData.today_trades = dailyData.trades;
                    sumData.today_funding = dailyData.funding;
                    sumData.today_avg_hold = dailyData.avg_hold;

                    // Client-side pagination for daily records
                    const allRecs = dailyData.records || [];
                    setAllDailyRecords(allRecs);
                    setTotalRecords(allRecs.length);

                    const start = (page - 1) * itemsPerPage;
                    setRecords(allRecs.slice(start, start + itemsPerPage));
                }
            } else {
                setAllDailyRecords([]);
                // Server-side pagination for All Records
                const offset = (page - 1) * itemsPerPage;
                const recRes = await fetch(`${API_BASE}/api/profit/records?limit=${itemsPerPage}&offset=${offset}`);
                if (!recRes.ok) throw new Error(`Failed to fetch records: ${recRes.status}`);

                const data = await recRes.json();
                setRecords(data.records || []);
                setTotalRecords(data.total || 0);
            }

            if (sumData) setSummary(sumData);
        } catch (e: any) {
            console.error("ProfitTab fetch error:", e);
            setError(e.message || "Failed to load data");
        } finally {
            setLoading(false);
        }
    }, [selectedDate, page, itemsPerPage]);

    useEffect(() => {
        fetchData();
        const timer = setInterval(fetchData, 10000);
        return () => clearInterval(timer);
    }, [fetchData]);

    const cardBg = theme === "dark" ? "bg-[#161b22] border-[#30363d]" : "bg-white border-gray-200";
    const textPrimary = theme === "dark" ? "text-white" : "text-gray-900";
    const textSecondary = theme === "dark" ? "text-slate-200" : "text-gray-500";
    const pnlColor = (v: number) => v > 0 ? "text-emerald-400" : v < 0 ? "text-red-400" : textSecondary;

    const formatTime = (ts: number) => {
        if (!ts) return "--";
        const d = new Date(ts);
        return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
    };

    const formatDuration = (ms: number) => {
        if (!ms) return "0s";
        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (days > 0) return `${days}d ${hours % 24}h`;
        if (hours > 0) return `${hours}h ${minutes % 60}m`;
        if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
        return `${seconds}s`;
    };

    if (error) {
        return (
            <div className="flex flex-col items-center justify-center py-20 text-red-400 gap-4">
                <AlertTriangle className="w-10 h-10" />
                <div className="text-lg font-medium">{error}</div>
                <button
                    onClick={fetchData}
                    className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-white transition"
                >
                    <RefreshCw className="w-4 h-4" />
                    Retry
                </button>
            </div>
        );
    }

    if (loading && !summary) return <div className="flex items-center justify-center py-20 text-slate-200">加载中...</div>;

    return (
        <section className="px-5 py-5 min-h-[500px]">
            {/* Header & Date Picker */}
            <div className="flex items-center justify-between mb-6">
                <h2 className={`text-xl font-bold ${textPrimary}`}>收益概览</h2>
                <div className="flex items-center gap-2">
                    <span className={`text-sm ${textSecondary}`}>选择日期:</span>
                    <input
                        type="date"
                        value={selectedDate}
                        onChange={(e) => {
                            setSelectedDate(e.target.value);
                            setPage(1); // Reset page on date change
                        }}
                        className={`px-3 py-1.5 rounded text-sm ${theme === "dark" ? "bg-[#0d1421] border-slate-700 text-white [&::-webkit-calendar-picker-indicator]:filter [&::-webkit-calendar-picker-indicator]:invert" : "bg-white border-gray-200 text-gray-900"} border focus:outline-none focus:border-cyan-500 transition`}
                    />
                    {selectedDate && (
                        <button
                            onClick={() => {
                                setSelectedDate("");
                                setPage(1); // Reset page on clear
                            }}
                            className="px-3 py-1.5 text-sm text-cyan-500 hover:text-cyan-400"
                        >
                            清除
                        </button>
                    )}
                    <button
                        onClick={fetchData}
                        className={`p-1.5 rounded hover:bg-slate-700 transition ${loading ? "animate-spin" : ""}`}
                        title="刷新"
                    >
                        <RefreshCw className={`w-4 h-4 ${textSecondary}`} />
                    </button>
                </div>
            </div>

            {/* 统计卡片 */}
            <div className="grid grid-cols-3 gap-4 mb-6">
                {[
                    { label: selectedDate ? `${selectedDate} 利润` : "今日利润", pnl: summary?.today_pnl, trades: summary?.today_trades, funding: summary?.today_funding, hold: summary?.today_avg_hold },
                    { label: "当月利润", pnl: summary?.month_pnl, trades: summary?.month_trades, funding: summary?.month_funding, hold: summary?.month_avg_hold },
                    { label: "累计利润", pnl: summary?.total_pnl, trades: summary?.total_trades, funding: summary?.total_funding, hold: summary?.total_avg_hold },
                ].map((item, i) => (
                    <div key={i} className={`${cardBg} border rounded-xl p-5`}>
                        <div className="flex justify-between items-start mb-2">
                            <div className={`text-sm ${textSecondary}`}>{item.label}</div>
                            <div className={`text-xs ${textSecondary} bg-slate-800 px-2 py-0.5 rounded`}>
                                Avg: {formatDuration(item.hold || 0)}
                            </div>
                        </div>
                        <div className={`text-2xl font-bold ${pnlColor(item.pnl || 0)}`}>
                            {(item.pnl || 0) > 0 ? "+" : ""}{(item.pnl || 0).toFixed(4)} U
                        </div>
                        <div className="flex items-center gap-4 mt-2">
                            <span className={`text-xs ${textSecondary}`}>交易 {item.trades || 0} 笔</span>
                            <span className={`text-xs ${pnlColor(item.funding || 0)}`}>
                                资费 {(item.funding || 0) > 0 ? "+" : ""}{(item.funding || 0).toFixed(4)} U
                            </span>
                        </div>
                    </div>
                ))}
            </div>

            {/* 记录表格 */}
            <div className={`${cardBg} border rounded-xl overflow-hidden`}>
                <div className="px-5 py-3 border-b border-[#30363d] flex items-center justify-between">
                    <span className={`text-sm font-medium ${textPrimary}`}>利润记录</span>
                    <span className={`text-xs ${textSecondary}`}>{totalRecords} 条</span>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className={`${theme === "dark" ? "bg-[#0d1117]" : "bg-gray-50"} text-left`}>
                                <th className="w-[24px] px-0"></th>
                                <th className={`px-4 py-2.5 font-medium ${textSecondary}`}>币种</th>
                                <th className={`px-4 py-2.5 font-medium ${textSecondary}`}>利润</th>
                                <th className={`px-4 py-2.5 font-medium ${textSecondary}`}>交易所</th>
                                <th className={`px-4 py-2.5 font-medium ${textSecondary}`}>时间</th>
                                <th className={`px-4 py-2.5 font-medium ${textSecondary}`}>结算公式说明 (备注)</th>
                            </tr>
                        </thead>
                        <tbody>
                            {records.length === 0 ? (
                                <tr><td colSpan={7} className={`px-4 py-12 text-center ${textSecondary} italic`}>暂无记录</td></tr>
                            ) : records.map((r, i) => (
                                <tr key={r.id || i} className={`border-t ${theme === "dark" ? "border-[#21262d] hover:bg-[#161b22]" : "border-gray-100 hover:bg-gray-50"} transition`}>
                                    {/* Column 1: Indicators */}
                                    <td className="w-[10px] pl-3 py-3 align-top">
                                        {r.record_type === 'funding' ? (
                                            <div className="pt-1 text-base leading-none">💰</div>
                                        ) : (
                                            <div className="flex flex-col gap-1 pt-1.5">
                                                {/* Top Indicator (A) - Green if SF, Yellow if FF */}
                                                <div className={`w-1.5 h-1.5 rounded-[1px] ${(r.strategy_type === 'SF') ? "bg-emerald-500" : "bg-[#FCD535]"
                                                    }`}></div>
                                                {/* Bottom Indicator (B) - Always Yellow (Future) */}
                                                <div className={`w-1.5 h-1.5 rounded-[1px] bg-[#FCD535]`}></div>
                                            </div>
                                        )}
                                    </td>

                                    {/* Column 2: Symbol */}
                                    <td className={`px-4 py-3 align-top`}>
                                        <div className={`font-bold text-sm ${theme === "dark" ? "text-white" : "text-gray-900"}`}>
                                            {r.symbol?.replace("USDT", "")}
                                        </div>
                                    </td>

                                    {/* Column 3: Profit */}
                                    <td className={`px-4 py-3 align-top font-mono font-medium ${pnlColor(r.pnl || 0)}`}>
                                        <div className="text-base">{(r.pnl || 0) > 0 ? "+" : ""}{(r.pnl || 0).toFixed(4)}</div>
                                        <div className={`text-xs ${theme === "dark" ? "text-slate-300" : "text-gray-400"}`}>U</div>
                                    </td>

                                    {/* Column 4: Exchange Tags */}
                                    <td className={`px-4 py-3 align-top`}>
                                        <div className="flex gap-1">
                                            {/* Exchange A */}
                                            <span className={`px-1.5 py-0.5 rounded text-[10px] border ${(r.strategy_type === 'SF')
                                                ? "bg-emerald-500/10 text-emerald-500 border-emerald-500/20"
                                                : "bg-[#FCD535]/10 text-[#FCD535] border-[#FCD535]/20"
                                                }`}>
                                                {r.exchange_a}
                                            </span>
                                            {/* Exchange B (Always Linear/Future -> Yellow) */}
                                            <span className="px-1.5 py-0.5 rounded text-[10px] bg-[#FCD535]/10 text-[#FCD535] border-[#FCD535]/20">
                                                {r.exchange_b}
                                            </span>
                                        </div>
                                    </td>

                                    {/* Column 5: Time */}
                                    <td className={`px-4 py-3 align-top`}>
                                        <div className={`text-xs ${theme === "dark" ? "text-slate-200" : "text-gray-500"}`}>
                                            {formatTime(r.timestamp)}
                                        </div>
                                        {r.external_id && (
                                            <div className="text-[10px] text-pink-500/70 font-mono mt-1 break-all">
                                                {r.external_id}
                                            </div>
                                        )}
                                    </td>

                                    {/* Column 6: Remarks */}
                                    <td className={`px-4 py-3 align-top`}>
                                        {r.record_type === 'trade' ? (
                                            <div className={`text-xs font-mono leading-relaxed ${theme === "dark" ? "text-slate-200" : "text-gray-600"}`}>
                                                {r.remarks || (
                                                    // 兼容之前没有 remarks 的老数据
                                                    <>
                                                        <div className="flex items-center gap-2">
                                                            <span className="w-3 text-slate-300">A:</span>
                                                            <span>{(r.fee_a || 0).toFixed(6)} / {(r.qty || 0).toFixed(1)} / {(r.entry_price_a || 0).toFixed(4)} / {(r.exit_price_a || 0).toFixed(4)}</span>
                                                        </div>
                                                        <div className="flex items-center gap-2">
                                                            <span className="w-3 text-slate-300">B:</span>
                                                            <span>{(r.fee_b || 0).toFixed(6)} / {(r.qty || 0).toFixed(1)} / {(r.entry_price_b || 0).toFixed(4)} / {(r.exit_price_b || 0).toFixed(4)}</span>
                                                        </div>
                                                    </>
                                                )}
                                            </div>
                                        ) : (
                                            <div className={`text-xs ${theme === "dark" ? "text-slate-300" : "text-gray-400"}`}>
                                                资金费率结算: {(r.funding_rate * 100).toFixed(4)}%
                                            </div>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Pagination Controls */}
            {totalRecords > itemsPerPage && (
                <div className="flex justify-center items-center gap-4 mt-4 text-sm">
                    <button
                        onClick={() => setPage(p => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className={`px-3 py-1 rounded ${page === 1 ? "text-gray-500 cursor-not-allowed" : "text-cyan-500 hover:text-cyan-400 bg-cyan-500/10"}`}
                    >
                        上一页
                    </button>
                    <span className={textSecondary}>
                        第 {page} 页 / 共 {Math.ceil(totalRecords / itemsPerPage)} 页
                    </span>
                    <button
                        onClick={() => setPage(p => Math.min(Math.ceil(totalRecords / itemsPerPage), p + 1))}
                        disabled={page >= Math.ceil(totalRecords / itemsPerPage)}
                        className={`px-3 py-1 rounded ${page >= Math.ceil(totalRecords / itemsPerPage) ? "text-gray-500 cursor-not-allowed" : "text-cyan-500 hover:text-cyan-400 bg-cyan-500/10"}`}
                    >
                        下一页
                    </button>
                </div>
            )}
        </section>
    );
};

export default ProfitTab;
