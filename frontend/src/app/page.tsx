"use client";

import { useArbitrage } from "@/hooks/useArbitrage";
import { ArbitrageTable } from "@/components/ArbitrageTable";
import { PriceMonitor } from "@/components/PriceMonitor";
import { SettingsModal } from "@/components/SettingsModal";
import { useSettings } from "@/context/SettingsContext"; // Import useSettings
import { useState, useEffect } from "react";
import { Settings } from "lucide-react"; // Icon

export default function Home() {
    const { data: liveData, status } = useArbitrage();
    const { minVolume, enabledExchanges, blockedSymbols } = useSettings(); // Get settings
    const [snapshot, setSnapshot] = useState(liveData);

    // UI States
    const [activeTab, setActiveTab] = useState<"SF" | "FF" | "SS" | "PRICES">("SF");
    const [time, setTime] = useState("");
    const [searchTerm, setSearchTerm] = useState("");
    const [isPaused, setIsPaused] = useState(false);
    const [isSettingsOpen, setIsSettingsOpen] = useState(false); // Modal state

    // Sync Snapshot with Live Data if not paused
    useEffect(() => {
        if (!isPaused) {
            setSnapshot(liveData);
        }
    }, [liveData, isPaused]);

    // Real-time Clock
    useEffect(() => {
        const timer = setInterval(() => {
            const now = new Date();
            setTime(now.toLocaleTimeString('en-GB', { hour12: false })); // HH:MM:SS
        }, 1000);
        return () => clearInterval(timer);
    }, []);

    // Helper to check if exchange is enabled
    const isExchangeAllowed = (rawName: string) => {
        const lower = rawName.toLowerCase();

        // Parse exchange
        let exchange: 'binance' | 'bybit' | 'bitget' | 'gate' | 'nado' | 'lighter' | null = null;
        if (lower.includes('binance')) exchange = 'binance';
        else if (lower.includes('bybit')) exchange = 'bybit';
        else if (lower.includes('bitget')) exchange = 'bitget';
        else if (lower.includes('gate')) exchange = 'gate';
        else if (lower.includes('nado')) exchange = 'nado';
        else if (lower.includes('lighter')) exchange = 'lighter';

        // Parse type
        let type: 'spot' | 'contract' | null = null;
        if (lower.includes('future') || lower.includes('linear')) type = 'contract';
        else if (lower.includes('spot')) type = 'spot';
        // Special Case: "binance" (raw) means Binance Spot
        else if (lower === 'binance') type = 'spot';

        // If unknown, allowed (e.g. unknown new exchanges)
        if (exchange && type) {
            // @ts-ignore
            const exSettings = enabledExchanges[exchange];
            if (exSettings) {
                return exSettings[type];
            }
        }
        return true;
    };

    // Filter Logic
    const filteredData = (() => {
        if (activeTab === "PRICES") return [];

        // 1. Select Tab Data
        let currentList = [];
        if (activeTab === 'SF') currentList = snapshot.sf;
        else if (activeTab === 'FF') currentList = snapshot.ff;
        else currentList = snapshot.ss;

        if (!currentList) return [];

        let result = currentList;

        // 2. Blocked Symbols Filter
        if (blockedSymbols.length > 0) {
            result = result.filter(item => {
                // Remove common suffixes (USDT, USDC, etc.) for matching
                const symbolUpper = item.symbol.toUpperCase();
                const baseSymbol = symbolUpper.replace(/USDT$|USDC$|BUSD$|USD$/, '');
                const isBlocked = blockedSymbols.includes(baseSymbol);
                return !isBlocked;
            });
        }

        // 3. Volume Filter (某一方 volume 为 0 则跳过该方)
        if (minVolume > 0) {
            result = result.filter(item => {
                const volA = Number(item.volumeA || 0);
                const volB = Number(item.volumeB || 0);
                if (volA === 0 && volB === 0) return true;
                const effectiveMin = volA > 0 && volB > 0 ? Math.min(volA, volB) : Math.max(volA, volB);
                return effectiveMin >= minVolume;
            });
        }

        // 3. Exchange Filter
        result = result.filter(item => {
            return isExchangeAllowed(item.details.ex1) && isExchangeAllowed(item.details.ex2);
        });

        // 4. Search Filter (搜索同时匹配 symbol 和交易所对)
        if (searchTerm.trim()) {
            const terms = searchTerm.toUpperCase().split(/[\s,]+/).filter(t => t.length > 0);
            if (terms.length > 0) {
                result = result.filter(item => {
                    const symbol = item.symbol.toUpperCase();
                    const pair = (item.pair || "").toUpperCase();
                    return terms.every(term => symbol.includes(term) || pair.includes(term));
                });
            }
        }

        return result;
    })();

    // Helper for Tab Class
    const tabClass = (tab: string) =>
        `px-6 py-2 rounded-t-lg font-bold transition-all ${activeTab === tab
            ? "bg-white text-blue-600 border-t-2 border-blue-600 shadow-sm"
            : "text-slate-500 hover:text-slate-700 hover:bg-slate-100"
        }`;

    return (
        <main className="min-h-screen bg-[#f1f5f9] font-sans pb-10">
            {/* Header */}
            <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm relative h-16">
                <div className="w-full px-4 h-full flex items-center justify-between relative">
                    {/* Left: Logo, Title, Status, Tabs */}
                    <div className="flex items-center gap-6">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-lg">
                                A
                            </div>
                            <h1 className="text-xl font-bold text-slate-800 tracking-tight hidden md:block">Arbitrage</h1>
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${status === 'Connected' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
                                {status}
                            </span>
                        </div>

                        {/* Tabs (Moved here) */}
                        <div className="flex p-0.5 bg-slate-100 rounded-lg border border-slate-200">
                            {["SF", "FF", "SS", "PRICES"].map((tab) => (
                                <button
                                    key={tab}
                                    onClick={() => setActiveTab(tab as any)}
                                    className={`px-3 py-1.5 rounded-md text-sm font-bold transition-all ${activeTab === tab
                                        ? "bg-white text-blue-600 shadow-sm"
                                        : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"
                                        }`}
                                >
                                    {tab === "SF" ? "SF" : tab === "FF" ? "FF" : tab === "SS" ? "SS" : "Price"}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Center: Clock */}
                    <div
                        className={`absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 font-mono text-xl font-bold tracking-widest transition-all duration-300 px-4 py-1.5 rounded-lg shadow-sm flex items-center justify-center ${/:5[5-9]:/.test(time)
                            ? "bg-red-600 text-white scale-110 shadow-red-200 ring-2 ring-red-100"
                            : "bg-[#1E88E5] text-white"
                            }`}
                    >
                        {time}
                    </div>

                    {/* Right: Search & Actions */}
                    <div className="flex items-center gap-3">
                        {activeTab !== "PRICES" && (
                            <>
                                <div className="relative group hidden lg:block">
                                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-blue-500 transition-colors">🔍</span>
                                    <input
                                        type="text"
                                        placeholder="Search..."
                                        className="pl-9 pr-8 py-1.5 rounded-lg border border-slate-200 bg-slate-50 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent w-48 text-sm font-medium transition-all"
                                        value={searchTerm}
                                        onChange={(e) => setSearchTerm(e.target.value)}
                                    />
                                    {searchTerm && (
                                        <button
                                            onClick={() => setSearchTerm("")}
                                            className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-1 rounded-full hover:bg-slate-200 transition-colors"
                                            title="清空"
                                        >
                                            ✕
                                        </button>
                                    )}
                                </div>

                                <button
                                    onClick={() => setIsPaused(!isPaused)}
                                    className={`p-2 rounded-lg text-sm font-bold shadow-sm transition-all flex items-center gap-1 ${isPaused
                                        ? "bg-amber-100 text-amber-700 hover:bg-amber-200 border border-amber-200"
                                        : "bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 hover:text-blue-600"
                                        }`}
                                    title={isPaused ? "Resume" : "Pause"}
                                >
                                    {isPaused ? "▶" : "⏸"}
                                </button>
                            </>
                        )}

                        <button
                            onClick={() => setIsSettingsOpen(true)}
                            className="p-2 rounded-lg bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 hover:text-blue-600 shadow-sm transition-all relative overflow-hidden group"
                            title="Setting"
                        >
                            <Settings size={20} className="transition-transform group-hover:rotate-45" />
                        </button>
                    </div>
                </div>
                {/* Debug Line (Removed) */}
            </header>

            {/* Main Content */}
            <div className="w-[99%] max-w-none mx-auto px-4 mt-4">
                {/* Data Table */}
                {activeTab === "PRICES" ? (
                    <PriceMonitor />
                ) : (
                    <div className="animate-in fade-in duration-300">
                        <ArbitrageTable data={filteredData} type={activeTab as "SF" | "FF" | "SS"} />
                    </div>
                )}

            </div>

            {/* Settings Modal */}
            <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
        </main>
    );
}
