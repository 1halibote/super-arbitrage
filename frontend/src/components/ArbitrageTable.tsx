import { ArbitrageOpportunity } from "../lib/types";
import { useState, useMemo } from "react";
import { useSettings } from "../context/SettingsContext";

interface Props {
    data: ArbitrageOpportunity[];
    type: "SF" | "FF" | "SS";
}

type SortKey = "openSpread" | "netFundingRate" | "fundingRate" | "symbol" | "volume" | "indexSpread";

export function ArbitrageTable({ data, type }: Props) {
    const { pinnedSymbols, togglePin } = useSettings();
    const [sortConfig, setSortConfig] = useState<{ key: SortKey; direction: "asc" | "desc" }>({
        key: "openSpread",
        direction: "desc",
    });

    const [currentPage, setCurrentPage] = useState(1);
    const itemsPerPage = 20;

    // Reset page when data type (tab) changes
    useMemo(() => {
        setCurrentPage(1);
    }, [type]);

    const handleSort = (key: SortKey) => {
        let direction: "asc" | "desc" = "desc";
        if (sortConfig.key === key && sortConfig.direction === "desc") {
            direction = "asc";
        }
        setSortConfig({ key, direction });
    };

    const sortedData = useMemo(() => {
        if (!data) return [];

        return [...data].sort((a, b) => {
            // Pinning: Pinned always top (by row: symbol|pair)
            const aPinKey = `${a.symbol}|${a.pair}`;
            const bPinKey = `${b.symbol}|${b.pair}`;
            const aPinned = pinnedSymbols.includes(aPinKey);
            const bPinned = pinnedSymbols.includes(bPinKey);
            if (aPinned && !bPinned) return -1;
            if (!aPinned && bPinned) return 1;

            let valA: number | string = 0;
            let valB: number | string = 0;

            switch (sortConfig.key) {
                case "openSpread":
                    valA = a.openSpread;
                    valB = b.openSpread;
                    break;
                case "netFundingRate":
                    valA = a.netFundingRate;
                    valB = b.netFundingRate;
                    break;
                case "fundingRate":
                    valA = Math.max(Math.abs(a.fundingRateA), Math.abs(a.fundingRateB));
                    valB = Math.max(Math.abs(b.fundingRateA), Math.abs(b.fundingRateB));
                    break;
                case "symbol":
                    valA = a.symbol;
                    valB = b.symbol;
                    break;
                case "volume":
                    valA = a.volume;
                    valB = b.volume;
                    break;
                case "indexSpread":
                    valA = Math.max(Math.abs(a.indexDiffA || 0), Math.abs(a.indexDiffB || 0));
                    valB = Math.max(Math.abs(b.indexDiffA || 0), Math.abs(b.indexDiffB || 0));
                    break;
            }

            if (valA < valB) return sortConfig.direction === "asc" ? -1 : 1;
            if (valA > valB) return sortConfig.direction === "asc" ? 1 : -1;
            return 0;
        });
    }, [data, sortConfig, pinnedSymbols]);

    // Pagination Logic
    const totalPages = Math.ceil(sortedData.length / itemsPerPage);
    const paginatedData = sortedData.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

    // Helper to format percentage
    const fmt = (n: number) => n.toFixed(3) + "%";

    // Helper for volume
    const fmtVol = (n: number) => {
        if (!n) return "$0";
        if (n > 1000000000) return "$" + (n / 1000000000).toFixed(2) + "B";
        if (n > 1000000) return "$" + (n / 1000000).toFixed(2) + "M";
        if (n > 1000) return "$" + (n / 1000).toFixed(2) + "K";
        return "$" + n.toFixed(0);
    };

    // Helper name cleanup
    const fmtEx = (name: string) => name.replace("_future", "").replace("_linear", "").replace("_spot", "");

    // Generate exchange trading URL
    const getExchangeUrl = (exchange: string, symbol: string) => {
        const baseSymbol = symbol.replace(/USDT$/, '');
        const exLower = exchange.toLowerCase();

        if (exLower.includes('binance')) {
            if (exLower.includes('future')) {
                return `https://www.binance.com/zh-CN/futures/${symbol}`;
            }
            return `https://www.binance.com/zh-CN/trade/${baseSymbol}_USDT`;
        }
        if (exLower.includes('bybit')) {
            if (exLower.includes('linear')) {
                return `https://www.bybit.com/trade/usdt/${symbol}`;
            }
            return `https://www.bybit.com/zh-TW/trade/spot/${baseSymbol}/USDT`;
        }
        if (exLower.includes('bitget')) {
            if (exLower.includes('future') || exLower.includes('linear')) {
                return `https://www.bitget.com/zh-CN/futures/usdt/${symbol}`;
            }
            return `https://www.bitget.com/zh-CN/spot/${symbol}`;
        }
        if (exLower.includes('gate')) {
            if (exLower.includes('future') || exLower.includes('linear')) {
                return `https://www.gate.io/zh/futures_trade/USDT/${baseSymbol}_USDT`;
            }
            return `https://www.gate.io/zh/trade/${baseSymbol}_USDT`;
        }
        return '#';
    };

    const getDisplayData = (row: ArbitrageOpportunity, type: "SF" | "FF" | "SS") => {
        return {
            exTop: row.details.ex1, exBot: row.details.ex2,
            rateTop: row.fundingRateA, rateBot: row.fundingRateB,
            intTop: row.fundingIntervalA, intBot: row.fundingIntervalB,
            volTop: row.volumeA, volBot: row.volumeB,
            maxTop: row.fundingMaxA, minTop: row.fundingMinA,
            maxBot: row.fundingMaxB, minBot: row.fundingMinB,
            idxDiffTop: row.indexDiffA, idxDiffBot: row.indexDiffB,
            isLongTop: true
        };
    };

    const SortIcon = ({ active, direction }: { active: boolean; direction: "asc" | "desc" }) => (
        <span className={`ml-1 text-xs ${active ? 'text-blue-500' : 'text-slate-300'}`}>
            {active ? (direction === 'asc' ? '↑' : '↓') : '↕'}
        </span>
    );

    // Exchange link click handler
    const handleExchangeClick = (e: React.MouseEvent, exchange: string, symbol: string) => {
        e.stopPropagation(); // Prevent row click (pin toggle)
        const url = getExchangeUrl(exchange, symbol);
        if (url !== '#') {
            window.open(url, '_blank');
        }
    };

    return (
        <div className="flex flex-col gap-4">
            <div className="overflow-x-auto rounded-xl border border-slate-200 shadow-sm bg-white">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="bg-slate-50 text-slate-600 text-sm font-bold uppercase tracking-wider border-b border-slate-200 sticky top-0 z-20 shadow-sm">
                            <th
                                className="px-4 py-4 cursor-pointer hover:bg-slate-200 transition-colors select-none w-[15%]"
                                onClick={() => handleSort("openSpread")}
                            >
                                开清差价 <SortIcon active={sortConfig.key === "openSpread"} direction={sortConfig.direction} />
                            </th>
                            <th
                                className="px-4 cursor-pointer hover:bg-slate-200 transition-colors select-none w-[10%]"
                                onClick={() => handleSort("symbol")}
                            >
                                币种名称 <SortIcon active={sortConfig.key === "symbol"} direction={sortConfig.direction} />
                            </th>
                            <th className="px-4 w-[12%]">交易所 (多/空)</th>
                            <th
                                className="px-4 cursor-pointer hover:bg-slate-200 transition-colors select-none w-[12%]"
                                onClick={() => handleSort("netFundingRate")}
                            >
                                净资金费率 <SortIcon active={sortConfig.key === "netFundingRate"} direction={sortConfig.direction} />
                            </th>
                            <th
                                className="px-4 cursor-pointer hover:bg-slate-200 transition-colors select-none w-[15%]"
                                onClick={() => handleSort("fundingRate")}
                            >
                                资金费率/周期 <SortIcon active={sortConfig.key === "fundingRate"} direction={sortConfig.direction} />
                            </th>
                            <th
                                className="px-4 cursor-pointer hover:bg-slate-200 transition-colors select-none w-[12%]"
                                onClick={() => handleSort("indexSpread")}
                            >
                                指数差价(%) <SortIcon active={sortConfig.key === "indexSpread"} direction={sortConfig.direction} />
                            </th>
                            <th
                                className="px-4 cursor-pointer hover:bg-slate-200 transition-colors select-none w-[14%]"
                                onClick={() => handleSort("volume")}
                            >
                                24h交易额 <SortIcon active={sortConfig.key === "volume"} direction={sortConfig.direction} />
                            </th>
                            <th className="px-4 w-[10%] text-right">操作</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {paginatedData.length === 0 ? (
                            <tr>
                                <td colSpan={8} className="px-4 py-12 text-center text-slate-400">
                                    {data.length === 0 ? "等待数据推送... (Waiting for Data)" : "无匹配数据"}
                                </td>
                            </tr>
                        ) : (
                            paginatedData.map((row, idx) => {
                                const d = getDisplayData(row, type);

                                const isSpot = (name: string) => {
                                    const lower = name.toLowerCase();
                                    return lower.includes('spot') || lower === 'binance';
                                };

                                const pinKey = `${row.symbol}|${row.pair}`;
                                const isPinned = pinnedSymbols.includes(pinKey);

                                return (
                                    <tr
                                        key={`${row.symbol}-${idx}-${currentPage}`}
                                        className={`
                                            transition-colors h-16 border-b border-slate-100 last:border-0 group cursor-pointer
                                            ${isPinned
                                                ? 'bg-blue-50 border-l-4 border-l-blue-500 hover:bg-blue-100'
                                                : 'hover:bg-blue-50/50 even:bg-slate-50/30'
                                            }
                                        `}
                                        onClick={() => togglePin(pinKey)}
                                    >
                                        <td className="px-4 font-mono">
                                            <div className="flex items-center gap-1">
                                                <span className={`text-lg ${row.openSpread > 3 ? 'text-emerald-600' : 'text-slate-950'}`}>{fmt(row.openSpread)}</span>
                                                <span className="text-slate-300 text-lg">/</span>
                                                <span className={`text-lg ${row.closeSpread > 3 ? 'text-emerald-600' : 'text-slate-950'}`}>{fmt(row.closeSpread)}</span>
                                            </div>
                                        </td>

                                        <td
                                            className="px-4 font-medium text-slate-800 text-base cursor-pointer hover:text-blue-600 transition-colors"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                navigator.clipboard.writeText(row.symbol.replace(/USDT$/, ''));
                                            }}
                                            title="Click to copy symbol"
                                        >
                                            {row.symbol.replace(/USDT$/, '')} <span className="ml-1 text-xs text-slate-400 font-normal">🔍</span>
                                        </td>

                                        <td className="px-4 text-sm font-medium">
                                            <span
                                                className={`cursor-pointer hover:underline ${isSpot(d.exTop) ? 'text-emerald-600 hover:text-emerald-800' : 'text-amber-600 hover:text-amber-800'}`}
                                                onClick={(e) => handleExchangeClick(e, d.exTop, row.symbol)}
                                                title={`打开 ${fmtEx(d.exTop)} 交易页面`}
                                            >
                                                {fmtEx(d.exTop)}
                                            </span>
                                            <span className="text-slate-300 mx-1">/</span>
                                            <span
                                                className={`cursor-pointer hover:underline ${isSpot(d.exBot) ? 'text-emerald-600 hover:text-emerald-800' : 'text-amber-600 hover:text-amber-800'}`}
                                                onClick={(e) => handleExchangeClick(e, d.exBot, row.symbol)}
                                                title={`打开 ${fmtEx(d.exBot)} 交易页面`}
                                            >
                                                {fmtEx(d.exBot)}
                                            </span>
                                        </td>

                                        <td className={`px-4 font-mono text-lg ${row.netFundingRate > 0 ? 'text-emerald-600' : row.netFundingRate < 0 ? 'text-rose-600' : 'text-slate-950'}`}>
                                            {row.netFundingRate !== 0 ? fmt(row.netFundingRate) : '0'}
                                        </td>

                                        <td className="px-4 text-lg font-mono">
                                            <div className="flex flex-col justify-center h-full gap-1">
                                                {/* Top Row */}
                                                <div className="flex items-center">
                                                    <span className={d.rateTop > 0 ? 'text-emerald-600' : d.rateTop < 0 ? 'text-rose-600' : 'text-slate-950'}>
                                                        {d.intTop ? fmt(d.rateTop) : '-'}
                                                    </span>
                                                    {d.intTop && (
                                                        <>
                                                            <span className="mx-1 text-slate-300 text-lg">/</span>
                                                            <span className={`text-lg ${String(d.intTop) === '1' ? 'text-rose-600' : 'text-emerald-600'}`}>{d.intTop}h</span>
                                                        </>
                                                    )}
                                                    {d.maxTop !== undefined && (
                                                        <>
                                                            <span className="mx-1 text-slate-300 text-lg">/</span>
                                                            {(() => {
                                                                const limitVal = d.rateTop >= 0 ? d.maxTop : d.minTop ?? 0;
                                                                return (
                                                                    <span className={limitVal > 0 ? 'text-emerald-600 text-lg' : limitVal < 0 ? 'text-rose-600 text-lg' : 'text-slate-950 text-lg'}>
                                                                        {limitVal}
                                                                    </span>
                                                                );
                                                            })()}
                                                        </>
                                                    )}
                                                </div>

                                                {/* Bot Row */}
                                                <div className="flex items-center">
                                                    <span className={d.rateBot > 0 ? 'text-emerald-600' : d.rateBot < 0 ? 'text-rose-600' : 'text-slate-950'}>
                                                        {d.intBot ? fmt(d.rateBot) : '-'}
                                                    </span>
                                                    {d.intBot && (
                                                        <>
                                                            <span className="mx-1 text-slate-300 text-lg">/</span>
                                                            <span className={`text-lg ${String(d.intBot) === '1' ? 'text-rose-600' : 'text-emerald-600'}`}>{d.intBot}h</span>
                                                        </>
                                                    )}
                                                    {d.maxBot !== undefined && (
                                                        <>
                                                            <span className="mx-1 text-slate-300 text-lg">/</span>
                                                            {(() => {
                                                                const limitVal = d.rateBot >= 0 ? d.maxBot : d.minBot ?? 0;
                                                                return (
                                                                    <span className={limitVal > 0 ? 'text-emerald-600 text-lg' : limitVal < 0 ? 'text-rose-600 text-lg' : 'text-slate-950 text-lg'}>
                                                                        {limitVal}
                                                                    </span>
                                                                );
                                                            })()}
                                                        </>
                                                    )}
                                                </div>
                                            </div>
                                        </td>

                                        <td className="px-4 text-lg font-mono">
                                            <div className="flex items-center">
                                                <span className={(d.idxDiffTop ?? 0) > 0 ? 'text-emerald-600' : (d.idxDiffTop ?? 0) < 0 ? 'text-rose-600' : 'text-slate-950'}>
                                                    {fmt(d.idxDiffTop ?? 0)}
                                                </span>
                                                <span className="mx-1 text-slate-300 text-lg">/</span>
                                                <span className={(d.idxDiffBot ?? 0) > 0 ? 'text-emerald-600' : (d.idxDiffBot ?? 0) < 0 ? 'text-rose-600' : 'text-slate-950'}>
                                                    {fmt(d.idxDiffBot ?? 0)}
                                                </span>
                                            </div>
                                        </td>

                                        <td className="px-4 text-slate-950 text-lg font-mono">
                                            <div className="flex items-center">
                                                <span>{fmtVol(d.volTop)}</span>
                                                <span className="text-slate-300 mx-1">/</span>
                                                <span>{fmtVol(d.volBot)}</span>
                                            </div>
                                        </td>

                                        <td className="px-4 text-right">
                                            <div
                                                className="flex justify-end gap-1"
                                                onClick={(e) => e.stopPropagation()}
                                            >
                                                <button className="p-1 hover:bg-slate-200 rounded text-slate-500">📄</button>
                                                <button className="p-1 hover:bg-slate-200 rounded text-slate-500">⇄</button>
                                                <button className="p-1 hover:bg-slate-200 rounded text-slate-500">🔗</button>
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })
                        )}
                    </tbody>
                </table>
            </div>

            {/* Pagination Controls */}
            {sortedData.length > 0 && (
                <div className="flex justify-end items-center gap-2 select-none pr-2">
                    <button
                        disabled={currentPage === 1}
                        onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                        className="w-8 h-8 flex items-center justify-center rounded border border-slate-300 hover:bg-slate-50 disabled:opacity-50 disabled:hover:bg-white text-slate-600 transition-colors"
                    >
                        ‹
                    </button>

                    <div className="flex items-center gap-1">
                        {/* Page 1 */}
                        <button
                            className={`w-8 h-8 rounded text-sm font-medium transition-colors border ${currentPage === 1 ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-50'}`}
                            onClick={() => setCurrentPage(1)}
                        >
                            1
                        </button>

                        {/* Leading Ellipsis */}
                        {currentPage > 3 && <span className="text-slate-400 px-1">...</span>}

                        {/* Neighbors */}
                        {currentPage > 2 && (
                            <button
                                className="w-8 h-8 rounded text-sm font-medium bg-white text-slate-600 border border-slate-300 hover:bg-slate-50 transition-colors"
                                onClick={() => setCurrentPage(currentPage - 1)}
                            >
                                {currentPage - 1}
                            </button>
                        )}

                        {currentPage !== 1 && currentPage !== totalPages && (
                            <button className="w-8 h-8 rounded text-sm font-medium bg-blue-600 text-white border border-blue-600">
                                {currentPage}
                            </button>
                        )}

                        {currentPage < totalPages - 1 && (
                            <button
                                className="w-8 h-8 rounded text-sm font-medium bg-white text-slate-600 border border-slate-300 hover:bg-slate-50 transition-colors"
                                onClick={() => setCurrentPage(currentPage + 1)}
                            >
                                {currentPage + 1}
                            </button>
                        )}

                        {/* Trailing Ellipsis */}
                        {currentPage < totalPages - 2 && <span className="text-slate-400 px-1">...</span>}

                        {/* Last Page */}
                        {totalPages > 1 && (
                            <button
                                className={`w-8 h-8 rounded text-sm font-medium transition-colors border ${currentPage === totalPages ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-50'}`}
                                onClick={() => setCurrentPage(totalPages)}
                            >
                                {totalPages}
                            </button>
                        )}
                    </div>

                    <button
                        disabled={currentPage === totalPages}
                        onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                        className="w-8 h-8 flex items-center justify-center rounded border border-slate-300 hover:bg-slate-50 disabled:opacity-50 disabled:hover:bg-white text-slate-600 transition-colors"
                    >
                        ›
                    </button>
                </div>
            )}
        </div>
    );
}
