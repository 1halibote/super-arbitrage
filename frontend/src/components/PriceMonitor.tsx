"use client";

import { useEffect, useState, useMemo } from "react";
import { PriceRow } from "../lib/types";
import { useSettings } from "../context/SettingsContext";

export function PriceMonitor() {
    const { blockedSymbols } = useSettings();
    const [data, setData] = useState<PriceRow[]>([]);
    const [search, setSearch] = useState("");
    const [loading, setLoading] = useState(true);

    // ... (fetchData logic remains same)

    // Pagination State
    const [page, setPage] = useState(1);
    const pageSize = 50;

    const fetchData = async () => {
        try {
            const res = await fetch("/api/prices");
            const json = await res.json();

            // Hydrate logic
            let hydrated: PriceRow[] = [];
            if (json.cols && json.rows) {
                const { cols, rows } = json;
                hydrated = rows.map((row: any[]) => {
                    const obj: any = {};
                    cols.forEach((col: string, i: number) => {
                        obj[col] = row[i];
                    });
                    return obj;
                });
            }

            setData(hydrated);
            setLoading(false);
        } catch (e) {
            console.error(e);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 3000); // Refresh every 3s
        return () => clearInterval(interval);
    }, []);

    const filtered = useMemo(() => {
        // Strict USDT Filter + Search + Blocked Symbols
        let res = data.filter(row => row.symbol.endsWith("USDT"));

        // Blocked Filter
        if (blockedSymbols.length > 0) {
            res = res.filter(row => {
                const baseSymbol = row.symbol.replace(/USDT$|USDC$|BUSD$|USD$/, '').toUpperCase();
                return !blockedSymbols.includes(baseSymbol);
            });
        }

        if (search) {
            const term = search.toLowerCase();
            res = res.filter(row => row.symbol.toLowerCase().includes(term));
        }
        return res;
    }, [data, search, blockedSymbols]);

    // Pagination Logic
    const totalPages = Math.ceil(filtered.length / pageSize);
    const paginatedData = filtered.slice((page - 1) * pageSize, page * pageSize);

    // Reset page on search
    useEffect(() => {
        setPage(1);
    }, [search]);

    const fmt = (n: number) => n > 0 ? n.toString() : "-";

    // Style helper for pricing
    const pStyle = "px-2 py-2 font-mono text-xs";
    const bidStyle = "text-emerald-600";
    const askStyle = "text-rose-600";

    const handleNext = () => setPage(p => Math.min(totalPages, p + 1));
    const handlePrev = () => setPage(p => Math.max(1, p - 1));

    return (
        <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between bg-white p-4 rounded-lg border border-slate-200">
                <div className="flex items-center gap-4">
                    <div className="relative">
                        <input
                            type="text"
                            placeholder="Search Symbol (e.g. BTC)..."
                            className="px-4 pr-8 py-2 border rounded-md w-64 text-sm"
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                        />
                        {search && (
                            <button
                                onClick={() => setSearch("")}
                                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-1 hover:bg-slate-100 rounded-full transition-colors"
                                title="清空"
                            >
                                ✕
                            </button>
                        )}
                    </div>
                    <span className="text-xs text-slate-500">Auto-refresh: 3s</span>
                </div>

                {/* Pagination Controls */}
                <div className="flex items-center gap-2 text-sm text-slate-600">
                    <button
                        onClick={handlePrev}
                        disabled={page === 1}
                        className="px-3 py-1 rounded border hover:bg-slate-50 disabled:opacity-50"
                    >
                        Prev
                    </button>
                    <span className="font-mono">{page} / {totalPages || 1}</span>
                    <button
                        onClick={handleNext}
                        disabled={page === totalPages}
                        className="px-3 py-1 rounded border hover:bg-slate-50 disabled:opacity-50"
                    >
                        Next
                    </button>
                    <span className="ml-2 text-xs text-slate-400">Total: {filtered.length}</span>
                </div>
            </div>

            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
                <table className="w-full text-left text-sm text-slate-600">
                    <thead className="bg-slate-50 text-slate-700 font-bold border-b h-10">
                        <tr>
                            <th className="px-4 py-2 w-24">Symbol</th>
                            <th className="px-2 py-2 text-center border-l bg-yellow-50/50" colSpan={2}>Binance Spot</th>
                            <th className="px-2 py-2 text-center border-l bg-amber-50/50" colSpan={2}>Binance Future</th>
                            <th className="px-2 py-2 text-center border-l bg-blue-50/50" colSpan={2}>Bybit Spot</th>
                            <th className="px-2 py-2 text-center border-l bg-indigo-50/50" colSpan={2}>Bybit Future</th>
                            <th className="px-2 py-2 text-center border-l bg-orange-50/50" colSpan={2}>Bitget Spot</th>
                            <th className="px-2 py-2 text-center border-l bg-red-50/50" colSpan={2}>Bitget Future</th>
                            <th className="px-2 py-2 text-center border-l bg-teal-50/50" colSpan={2}>Gate Spot</th>
                            <th className="px-2 py-2 text-center border-l bg-cyan-50/50" colSpan={2}>Gate Future</th>
                            <th className="px-2 py-2 text-center border-l bg-violet-50/50" colSpan={2}>Nado Spot</th>
                            <th className="px-2 py-2 text-center border-l bg-purple-50/50" colSpan={2}>Nado Future</th>
                            <th className="px-2 py-2 text-center border-l bg-lime-50/50" colSpan={2}>Lighter Spot</th>
                            <th className="px-2 py-2 text-center border-l bg-emerald-50/50" colSpan={2}>Lighter Future</th>
                        </tr>
                        <tr className="text-xs text-slate-500 border-b">
                            <th></th>
                            <th className="px-2 border-l text-emerald-600">Bid</th>
                            <th className="px-2 text-rose-600">Ask</th>
                            <th className="px-2 border-l text-emerald-600">Bid</th>
                            <th className="px-2 text-rose-600">Ask</th>
                            <th className="px-2 border-l text-emerald-600">Bid</th>
                            <th className="px-2 text-rose-600">Ask</th>
                            <th className="px-2 border-l text-emerald-600">Bid</th>
                            <th className="px-2 text-rose-600">Ask</th>
                            <th className="px-2 border-l text-emerald-600">Bid</th>
                            <th className="px-2 text-rose-600">Ask</th>
                            <th className="px-2 border-l text-emerald-600">Bid</th>
                            <th className="px-2 text-rose-600">Ask</th>
                            <th className="px-2 border-l text-emerald-600">Bid</th>
                            <th className="px-2 text-rose-600">Ask</th>
                            <th className="px-2 border-l text-emerald-600">Bid</th>
                            <th className="px-2 text-rose-600">Ask</th>
                            <th className="px-2 border-l text-emerald-600">Bid</th>
                            <th className="px-2 text-rose-600">Ask</th>
                            <th className="px-2 border-l text-emerald-600">Bid</th>
                            <th className="px-2 text-rose-600">Ask</th>
                            <th className="px-2 border-l text-emerald-600">Bid</th>
                            <th className="px-2 text-rose-600">Ask</th>
                            <th className="px-2 border-l text-emerald-600">Bid</th>
                            <th className="px-2 text-rose-600">Ask</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {loading && data.length === 0 ? (
                            <tr><td colSpan={25} className="p-8 text-center">Loading Prices...</td></tr>
                        ) : paginatedData.map(row => (
                            <tr key={row.symbol} className="hover:bg-slate-50 transition-colors">
                                <td className="px-4 py-2 font-bold">{row.symbol.replace("USDT", "")}</td>

                                <td className={`${pStyle} border-l ${bidStyle}`}>{fmt(row.binance_spot.bid)}</td>
                                <td className={`${pStyle} ${askStyle}`}>{fmt(row.binance_spot.ask)}</td>

                                <td className={`${pStyle} border-l bg-amber-50/20 ${bidStyle}`}>{fmt(row.binance_future.bid)}</td>
                                <td className={`${pStyle} bg-amber-50/20 ${askStyle}`}>{fmt(row.binance_future.ask)}</td>

                                <td className={`${pStyle} border-l ${bidStyle}`}>{fmt(row.bybit_spot.bid)}</td>
                                <td className={`${pStyle} ${askStyle}`}>{fmt(row.bybit_spot.ask)}</td>

                                <td className={`${pStyle} border-l bg-indigo-50/20 ${bidStyle}`}>{fmt(row.bybit_future.bid)}</td>
                                <td className={`${pStyle} bg-indigo-50/20 ${askStyle}`}>{fmt(row.bybit_future.ask)}</td>

                                <td className={`${pStyle} border-l bg-orange-50/10 ${bidStyle}`}>{row.bitget_spot ? fmt(row.bitget_spot.bid) : '-'}</td>
                                <td className={`${pStyle} bg-orange-50/10 ${askStyle}`}>{row.bitget_spot ? fmt(row.bitget_spot.ask) : '-'}</td>

                                <td className={`${pStyle} border-l bg-red-50/10 ${bidStyle}`}>{row.bitget_future ? fmt(row.bitget_future.bid) : '-'}</td>
                                <td className={`${pStyle} bg-red-50/10 ${askStyle}`}>{row.bitget_future ? fmt(row.bitget_future.ask) : '-'}</td>

                                <td className={`${pStyle} border-l bg-teal-50/10 ${bidStyle}`}>{row.gate_spot ? fmt(row.gate_spot.bid) : '-'}</td>
                                <td className={`${pStyle} bg-teal-50/10 ${askStyle}`}>{row.gate_spot ? fmt(row.gate_spot.ask) : '-'}</td>

                                <td className={`${pStyle} border-l bg-cyan-50/10 ${bidStyle}`}>{row.gate_future ? fmt(row.gate_future.bid) : '-'}</td>
                                <td className={`${pStyle} bg-cyan-50/10 ${askStyle}`}>{row.gate_future ? fmt(row.gate_future.ask) : '-'}</td>

                                <td className={`${pStyle} border-l bg-violet-50/10 ${bidStyle}`}>{row.nado_spot ? fmt(row.nado_spot.bid) : '-'}</td>
                                <td className={`${pStyle} bg-violet-50/10 ${askStyle}`}>{row.nado_spot ? fmt(row.nado_spot.ask) : '-'}</td>

                                <td className={`${pStyle} border-l bg-purple-50/10 ${bidStyle}`}>{row.nado_future ? fmt(row.nado_future.bid) : '-'}</td>
                                <td className={`${pStyle} bg-purple-50/10 ${askStyle}`}>{row.nado_future ? fmt(row.nado_future.ask) : '-'}</td>

                                <td className={`${pStyle} border-l bg-lime-50/10 ${bidStyle}`}>{row.lighter_spot ? fmt(row.lighter_spot.bid) : '-'}</td>
                                <td className={`${pStyle} bg-lime-50/10 ${askStyle}`}>{row.lighter_spot ? fmt(row.lighter_spot.ask) : '-'}</td>

                                <td className={`${pStyle} border-l bg-emerald-50/10 ${bidStyle}`}>{row.lighter_future ? fmt(row.lighter_future.bid) : '-'}</td>
                                <td className={`${pStyle} bg-emerald-50/10 ${askStyle}`}>{row.lighter_future ? fmt(row.lighter_future.ask) : '-'}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
