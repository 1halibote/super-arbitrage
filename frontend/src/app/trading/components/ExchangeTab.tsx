"use client";

import { useState, useEffect } from "react";
import { Plus, Check, AlertCircle, X, Loader2, Trash2, Settings, Wallet, RefreshCw, Link2 } from "lucide-react";

interface Asset {
    asset: string;
    balance?: number;
    available?: number;
    unrealized_pnl?: number;
    free?: number;
    locked?: number;
    total?: number;
}

interface AssetsResult {
    valid: boolean;
    error?: string;
    is_unified?: boolean;
    is_hedged?: boolean;
    spot_assets?: Asset[];
    contract_assets?: Asset[];
}

interface Exchange {
    name: string;
    connected: boolean;
    balance: number;
}

export default function ExchangeTab() {
    const [assets, setAssets] = useState<Record<string, AssetsResult>>({});
    const [exchanges, setExchanges] = useState<Exchange[]>([]);
    const [loading, setLoading] = useState(false);

    // Add Exchange Modal State
    const [showAddModal, setShowAddModal] = useState(false);
    const [newExchange, setNewExchange] = useState({ exchange: "binance", apiKey: "", apiSecret: "", passphrase: "" });
    const [verifying, setVerifying] = useState(false);
    const [saving, setSaving] = useState(false);
    const [verifyResult, setVerifyResult] = useState<AssetsResult | null>(null);

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            const [assetsRes, exchRes] = await Promise.all([
                fetch("/api/trading/assets"),
                fetch("/api/trading/exchanges")
            ]);

            const assetsData = await assetsRes.json();
            const exchData = await exchRes.json();

            setAssets(assetsData.assets || {});
            setExchanges(exchData.exchanges || []);
        } catch (e) {
            console.error(e);
        }
        setLoading(false);
    };

    const handleVerify = async () => {
        setVerifying(true);
        setVerifyResult(null);
        try {
            const res = await fetch("/api/trading/exchange/verify", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(newExchange)
            });
            const data = await res.json();
            setVerifyResult(data);
        } catch (e) {
            console.error(e);
            setVerifyResult({ valid: false, error: "Network Error" });
        }
        setVerifying(false);
    };

    const handleConfirmAdd = async () => {
        if (!verifyResult?.valid || saving) return;

        setSaving(true);
        try {
            const res = await fetch("/api/trading/exchange", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(newExchange)
            });
            const data = await res.json();
            if (data.success) {
                setShowAddModal(false);
                setNewExchange({ exchange: "binance", apiKey: "", apiSecret: "", passphrase: "" });
                setVerifyResult(null);
                loadData();
            } else {
                alert("保存失败，请重试");
            }
        } catch (e) {
            console.error(e);
            alert("网络错误，请重试");
        }
        setSaving(false);
    };

    const handleDelete = async (name: string) => {
        if (!confirm(`Delete ${name}?`)) return;
        await fetch(`/api/trading/exchange/${name}`, { method: "DELETE" });
        loadData();
    };

    return (
        <div className="space-y-6 animate-in fade-in duration-300">
            {/* 1. 持仓概览 */}
            <section>
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-base font-bold flex items-center gap-2">
                        <Wallet className="w-5 h-5 text-cyan-400" />
                        持仓概览
                    </h2>
                    <button onClick={loadData} className="p-1.5 rounded bg-slate-800 hover:bg-slate-700 transition">
                        <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
                    </button>
                </div>

                <div className="space-y-3">
                    {Object.entries(assets).map(([name, data]) => {
                        if (!data.valid) return null;

                        const contractTotal = data.contract_assets?.reduce((sum, a) => sum + (a.balance || 0), 0) || 0;
                        const spotTotal = data.spot_assets?.reduce((sum, a) => sum + (a.total || 0), 0) || 0;

                        return (
                            <div key={name} className="bg-[#12171f] border border-slate-700/50 rounded-lg p-4">
                                <div className="flex items-center justify-between mb-4">
                                    <div className="flex items-center gap-2">
                                        <img src={`/icons/${name}.svg`} alt={name} className="w-6 h-6 rounded-full bg-slate-700" onError={(e) => e.currentTarget.style.display = 'none'} />
                                        <span className="font-bold capitalize text-lg">{name}</span>
                                        {data.is_unified && <span className="text-[10px] bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded">统一账户</span>}
                                        {data.is_hedged && <span className="text-[10px] bg-purple-500/20 text-purple-400 px-1.5 py-0.5 rounded">双向持仓</span>}
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                    {/* 合约资产 */}
                                    <div>
                                        <div className="flex items-center justify-between mb-2 pb-2 border-b border-slate-700/50">
                                            <span className="text-sm text-slate-400">合约账户</span>
                                            <span className="font-mono text-cyan-400">{contractTotal.toFixed(2)} USDT</span>
                                        </div>
                                        <div className="space-y-1">
                                            {data.contract_assets?.map(asset => (
                                                <div key={asset.asset} className="flex justify-between text-xs">
                                                    <span className="font-bold text-slate-300">{asset.asset}</span>
                                                    <span className="font-mono text-slate-400">{asset.balance?.toFixed(8)}</span>
                                                </div>
                                            ))}
                                            {(!data.contract_assets || data.contract_assets.length === 0) && (
                                                <div className="text-xs text-slate-600 text-center py-2">无资产</div>
                                            )}
                                        </div>
                                    </div>

                                    {/* 现货资产 */}
                                    <div>
                                        <div className="flex items-center justify-between mb-2 pb-2 border-b border-slate-700/50">
                                            <span className="text-sm text-slate-400">现货账户</span>
                                            <span className="font-mono text-orange-400">{spotTotal.toFixed(2)} USDT (Est.)</span>
                                        </div>
                                        <div className="space-y-1">
                                            {data.spot_assets?.map(asset => (
                                                <div key={asset.asset} className="flex justify-between text-xs">
                                                    <span className="font-bold text-green-400">{asset.asset}</span>
                                                    <span className="font-mono text-slate-400">{asset.total?.toFixed(8)}</span>
                                                </div>
                                            ))}
                                            {(!data.spot_assets || data.spot_assets.length === 0) && (
                                                <div className="text-xs text-slate-600 text-center py-2">无资产</div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        );
                    })}

                    {Object.keys(assets).length === 0 && !loading && (
                        <div className="text-center py-8 text-slate-500 bg-[#12171f] rounded-lg border border-slate-800">
                            暂无持仓数据，请先配置交易所 API
                        </div>
                    )}
                </div>
            </section>

            {/* 2. API 设置 */}
            <section className="pt-8">
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-base font-bold flex items-center gap-2">
                        <Settings className="w-5 h-5 text-slate-400" />
                        API 设置
                    </h2>
                    <button
                        onClick={() => setShowAddModal(true)}
                        className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-sm font-medium transition flex items-center gap-1"
                    >
                        <Plus className="w-4 h-4" />
                        添加
                    </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                    {/* 已配置的卡片 */}
                    {exchanges.map(ex => (
                        <div key={ex.name} className="bg-[#12171f] border border-slate-700 rounded-lg p-4 group hover:border-slate-600 transition">
                            <div className="flex items-center justify-between mb-3">
                                <div className="flex items-center gap-2">
                                    {/* 简单的 Logo 占位 */}
                                    <div className="w-8 h-8 rounded bg-slate-800 flex items-center justify-center font-bold text-xs uppercase">
                                        {ex.name[0]}
                                    </div>
                                    <span className="font-bold capitalize">{ex.name}</span>
                                </div>
                                <div className={`w-2 h-2 rounded-full ${ex.connected ? "bg-green-500" : "bg-red-500"}`} />
                            </div>

                            <div className="flex gap-2 mt-4 opacity-0 group-hover:opacity-100 transition">
                                <button className="flex-1 py-1.5 bg-slate-700 hover:bg-slate-600 rounded text-xs transition">
                                    配置
                                </button>
                                <button
                                    onClick={() => handleDelete(ex.name)}
                                    className="flex-1 py-1.5 bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded text-xs transition"
                                >
                                    删除
                                </button>
                            </div>
                        </div>
                    ))}

                    {/* 预设的占位卡片 (模仿图2) */}
                    {["okx", "gate", "bitget", "kucoin", "mexc", "htx", "nado"].map(name => {
                        const isConfigured = exchanges.some(e => e.name === name);
                        if (isConfigured) return null;

                        return (
                            <div key={name} className="bg-[#0f131a] border border-slate-800 rounded-lg p-4 opacity-70 hover:opacity-100 transition cursor-not-allowed">
                                <div className="flex items-center gap-2 mb-3">
                                    <div className="w-8 h-8 rounded bg-slate-800 flex items-center justify-center font-bold text-xs uppercase text-slate-500">
                                        {name[0]}
                                    </div>
                                    <span className="font-bold capitalize text-slate-500">{name}</span>
                                </div>
                                <div className="flex gap-2">
                                    <button className="p-1.5 rounded bg-slate-800 text-slate-600">
                                        <Settings className="w-3 h-3" />
                                    </button>
                                    <button className="p-1.5 rounded bg-slate-800 text-slate-600">
                                        <Link2 className="w-3 h-3" />
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </section>

            {/* 3. 添加/验证 Modal (图3) */}
            {showAddModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
                    <div className="bg-[#12171f] rounded-xl border border-slate-700 w-full max-w-lg shadow-2xl overflow-hidden">
                        <div className="px-5 py-4 border-b border-slate-700 flex justify-between items-center">
                            <h3 className="font-bold text-lg">添加 API 密钥</h3>
                            <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-white">
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="p-5 space-y-4">
                            {!verifyResult ? (
                                <>
                                    <div className="space-y-3">
                                        <div>
                                            <label className="block text-xs text-slate-400 mb-1">交易所</label>
                                            <select
                                                className="w-full bg-[#0a0e17] border border-slate-700 rounded px-3 py-2 text-sm focus:border-blue-500 outline-none"
                                                value={newExchange.exchange}
                                                onChange={e => setNewExchange({ ...newExchange, exchange: e.target.value })}
                                            >
                                                <option value="binance">Binance</option>
                                                <option value="bybit">Bybit</option>
                                                <option value="bitget">Bitget</option>
                                                <option value="gate">Gate</option>
                                                <option value="nado">Nado (DEX)</option>
                                            </select>
                                        </div>
                                        <div>
                                            <label className="block text-xs text-slate-400 mb-1">API Key</label>
                                            <input
                                                type="text"
                                                className="w-full bg-[#0a0e17] border border-slate-700 rounded px-3 py-2 text-sm focus:border-blue-500 outline-none"
                                                placeholder={newExchange.exchange === "nado" ? "输入 EVM 私钥 (0x...)" : "输入 API Key"}
                                                value={newExchange.apiKey}
                                                onChange={e => setNewExchange({ ...newExchange, apiKey: e.target.value })}
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs text-slate-400 mb-1">API Secret</label>
                                            <input
                                                type="password"
                                                className="w-full bg-[#0a0e17] border border-slate-700 rounded px-3 py-2 text-sm focus:border-blue-500 outline-none"
                                                placeholder={newExchange.exchange === "nado" ? "输入子账户名 (如: default)" : "输入 API Secret"}
                                                value={newExchange.apiSecret}
                                                onChange={e => setNewExchange({ ...newExchange, apiSecret: e.target.value })}
                                            />
                                        </div>
                                        {newExchange.exchange === "bitget" && (
                                            <div>
                                                <label className="block text-xs text-slate-400 mb-1">API Passphrase</label>
                                                <input
                                                    type="password"
                                                    className="w-full bg-[#0a0e17] border border-slate-700 rounded px-3 py-2 text-sm focus:border-blue-500 outline-none"
                                                    placeholder="输入 Passphrase"
                                                    value={newExchange.passphrase}
                                                    onChange={e => setNewExchange({ ...newExchange, passphrase: e.target.value })}
                                                />
                                            </div>
                                        )}
                                    </div>

                                    <div className="pt-2">
                                        <button
                                            onClick={handleVerify}
                                            disabled={verifying || !newExchange.apiKey || !newExchange.apiSecret}
                                            className="w-full py-2.5 rounded bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 font-medium transition flex items-center justify-center gap-2"
                                        >
                                            {verifying && <Loader2 className="w-4 h-4 animate-spin" />}
                                            {verifying ? "验证中..." : "验证 API"}
                                        </button>
                                    </div>
                                </>
                            ) : (
                                <div className="space-y-4 animate-in slide-in-from-right duration-200">
                                    <div className={`p-3 rounded-lg flex items-center gap-3 ${verifyResult.valid ? "bg-green-500/10 border border-green-500/30" : "bg-red-500/10 border border-red-500/30"}`}>
                                        {verifyResult.valid ? (
                                            <div className="w-8 h-8 rounded-full bg-green-500 text-white flex items-center justify-center flex-shrink-0">
                                                <Check className="w-5 h-5" />
                                            </div>
                                        ) : (
                                            <div className="w-8 h-8 rounded-full bg-red-500 text-white flex items-center justify-center flex-shrink-0">
                                                <X className="w-5 h-5" />
                                            </div>
                                        )}
                                        <div>
                                            <h4 className={`font-bold ${verifyResult.valid ? "text-green-400" : "text-red-400"}`}>
                                                {verifyResult.valid ? `${newExchange.exchange.toUpperCase()} API 测试结果` : "验证失败"}
                                            </h4>
                                            {!verifyResult.valid && <p className="text-xs text-red-300 mt-1">{verifyResult.error}</p>}
                                        </div>
                                    </div>

                                    {verifyResult.valid && (
                                        <div className="space-y-2 text-sm bg-[#0a0e17] p-4 rounded-lg border border-slate-800">
                                            <div className="flex items-center gap-2">
                                                <Check className="w-3.5 h-3.5 text-green-500" />
                                                <span className="text-slate-400">检查是否为统一账户:</span>
                                                <span className={verifyResult.is_unified ? "text-green-400" : "text-slate-500"}>
                                                    {verifyResult.is_unified ? "是 (支持现货/合约保证金共享)" : "否 (经典账户)"}
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <Check className="w-3.5 h-3.5 text-green-500" />
                                                <span className="text-slate-400">设置双向持仓模式:</span>
                                                <span className={verifyResult.is_hedged ? "text-green-400" : "text-slate-500"}>
                                                    {verifyResult.is_hedged ? "成功" : "失败 (建议手动开启)"}
                                                </span>
                                            </div>

                                            <div className="mt-3 pt-3 border-t border-slate-800">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <div className={`w-3 h-3 rounded bg-green-500/20 border border-green-500/50 flex items-center justify-center`}>
                                                        <Check className="w-2 h-2 text-green-500" />
                                                    </div>
                                                    <span className="font-bold text-slate-300">现货账户余额:</span>
                                                </div>
                                                <div className="pl-5 text-xs font-mono text-slate-400 grid grid-cols-2 gap-x-4 gap-y-1">
                                                    {verifyResult.spot_assets?.map(a => (
                                                        <span key={a.asset}>"{a.asset}": {a.total}</span>
                                                    ))}
                                                    {(!verifyResult.spot_assets || verifyResult.spot_assets.length === 0) && <span>无</span>}
                                                </div>
                                            </div>

                                            <div className="mt-2 text-xs text-slate-500 italic">
                                                * 仅显示余额大于 0 的资产
                                            </div>
                                        </div>
                                    )}

                                    <div className="flex gap-3 pt-2">
                                        <button
                                            onClick={() => setVerifyResult(null)}
                                            className="flex-1 py-2 rounded bg-slate-700 hover:bg-slate-600 text-sm transition"
                                        >
                                            返回修改
                                        </button>
                                        <button
                                            onClick={handleConfirmAdd}
                                            disabled={!verifyResult.valid || saving}
                                            className="flex-1 py-2 rounded bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 font-medium transition flex items-center justify-center gap-2"
                                        >
                                            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
                                            {saving ? "保存中..." : "保存配置"}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
