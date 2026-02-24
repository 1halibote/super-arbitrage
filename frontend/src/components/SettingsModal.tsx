import { useState, useEffect } from "react";
import { X, Send } from "lucide-react";
import { useSettings } from "../context/SettingsContext";

interface Props {
    isOpen: boolean;
    onClose: () => void;
}

export function SettingsModal({ isOpen, onClose }: Props) {
    const {
        minVolume, updateSettings,
        enabledExchanges, toggleExchange,
        blockedSymbols, addBlockedSymbol, removeBlockedSymbol,
        feishu, updateFeishu
    } = useSettings();

    const [newBlock, setNewBlock] = useState("");
    const [testStatus, setTestStatus] = useState<"idle" | "sending" | "success" | "error">("idle");


    const handleAddBlock = () => {
        if (newBlock.trim()) {
            addBlockedSymbol(newBlock.trim());
            setNewBlock("");
        }
    };

    const handleTestFeishu = async () => {
        if (!feishu.webhookUrl) return;
        setTestStatus("sending");
        try {
            const res = await fetch("/api/feishu/test", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ webhookUrl: feishu.webhookUrl })
            });
            setTestStatus(res.ok ? "success" : "error");
        } catch {
            setTestStatus("error");
        }
        setTimeout(() => setTestStatus("idle"), 3000);
    };

    if (!isOpen) return null;

    // Helper to format volume for display
    const fmtVol = (val: number) => {
        if (val === 0) return "0 (USDT)";
        if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`;
        if (val >= 1000) return `${(val / 1000).toFixed(0)}K`;
        return val.toString();
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/20 backdrop-blur-sm">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden border border-slate-100 animate-in fade-in zoom-in duration-200 max-h-[90vh] overflow-y-auto">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 sticky top-0 bg-white z-10">
                    <h2 className="text-xl font-bold text-slate-800">设置</h2>
                    <button
                        onClick={onClose}
                        className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors"
                    >
                        <X size={20} />
                    </button>
                </div>

                <div className="p-6 space-y-8">
                    {/* Volume Filter Section */}
                    <div className="space-y-4">
                        <div>
                            <h3 className="text-base font-bold text-slate-800">交易额筛选</h3>
                            <p className="text-sm text-slate-500 mt-1">筛选24小时交易额（USDT）</p>
                        </div>
                        <div className="flex items-center gap-4">
                            <input
                                type="range"
                                min={0}
                                max={10000000}
                                step={100000}
                                value={minVolume}
                                onChange={(e) => updateSettings({ minVolume: parseInt(e.target.value) })}
                                className="flex-1 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                            />
                            <span className="w-20 text-right font-mono text-sm text-slate-600">{fmtVol(minVolume)}</span>
                        </div>
                    </div>

                    {/* Exchange Filter Section */}
                    <div className="space-y-4">
                        <div>
                            <h3 className="text-base font-bold text-slate-800">交易所订阅</h3>
                            <p className="text-sm text-slate-500 mt-1">启用/禁用特定交易所类型</p>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            {(['binance', 'bybit', 'bitget', 'gate', 'nado', 'lighter'] as const).map(ex => (
                                <div key={ex} className="p-4 rounded-lg bg-slate-50 border border-slate-200">
                                    <div className="font-bold text-slate-700 mb-2 capitalize">{ex}</div>
                                    <div className="flex gap-4">
                                        {(['spot', 'contract'] as const).map(type => (
                                            <label key={type} className="flex items-center gap-2 cursor-pointer">
                                                <input
                                                    type="checkbox"
                                                    checked={enabledExchanges[ex][type]}
                                                    onChange={() => toggleExchange(ex, type)}
                                                    className="w-4 h-4 accent-blue-600"
                                                />
                                                <span className="text-sm text-slate-600 capitalize">{type}</span>
                                            </label>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Blocked Symbols */}
                    <div className="space-y-4">
                        <div>
                            <h3 className="text-base font-bold text-slate-800">屏蔽币种</h3>
                            <p className="text-sm text-slate-500 mt-1">将不想展示的币种加入列表</p>
                        </div>

                        <div className="flex gap-2">
                            <div className="relative flex-1">
                                <input
                                    type="text"
                                    placeholder="输入币种名称 (例如 BTC)"
                                    className="w-full px-4 pr-8 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 uppercase"
                                    value={newBlock}
                                    onChange={(e) => setNewBlock(e.target.value)}
                                    onKeyDown={(e) => e.key === 'Enter' && handleAddBlock()}
                                />
                                {newBlock && (
                                    <button
                                        onClick={() => setNewBlock("")}
                                        className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-1 hover:bg-slate-100 rounded-full transition-colors"
                                        title="清空"
                                    >
                                        ✕
                                    </button>
                                )}
                            </div>
                            <button
                                onClick={handleAddBlock}
                                className="px-6 py-2 bg-blue-600 text-white text-sm font-bold rounded-lg hover:bg-blue-700 transition-colors"
                            >
                                添加
                            </button>
                        </div>

                        {blockedSymbols.length > 0 && (
                            <div className="flex flex-wrap gap-2 pt-2">
                                {blockedSymbols.map(s => (
                                    <div key={s} className="px-3 py-1 bg-slate-100 rounded-full text-xs font-bold text-slate-600 flex items-center gap-2 border border-slate-200">
                                        <span>{s}</span>
                                        <button
                                            onClick={() => removeBlockedSymbol(s)}
                                            className="hover:text-red-500 transition-colors"
                                        >
                                            <X size={14} />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Feishu Push Settings */}
                    <div className="space-y-4 border-t border-slate-200 pt-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="text-base font-bold text-slate-800">飞书推送</h3>
                                <p className="text-sm text-slate-500 mt-1">配置飞书 Webhook 接收套利机会提醒</p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={feishu.enabled}
                                    onChange={(e) => updateFeishu({ enabled: e.target.checked })}
                                    className="sr-only peer"
                                />
                                <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                            </label>
                        </div>

                        {feishu.enabled && (
                            <div className="space-y-4 pl-4 border-l-2 border-blue-200">
                                {/* Webhook URL */}
                                <div className="space-y-2">
                                    <label className="text-sm font-medium text-slate-700">Webhook URL</label>
                                    <div className="flex gap-2">
                                        <input
                                            type="text"
                                            placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
                                            className="flex-1 px-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            value={feishu.webhookUrl}
                                            onChange={(e) => updateFeishu({ webhookUrl: e.target.value })}
                                        />
                                        <button
                                            onClick={handleTestFeishu}
                                            disabled={!feishu.webhookUrl || testStatus === "sending"}
                                            className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-colors
                                                ${testStatus === "success" ? "bg-emerald-500 text-white" :
                                                    testStatus === "error" ? "bg-rose-500 text-white" :
                                                        "bg-slate-100 text-slate-600 hover:bg-slate-200"}
                                                disabled:opacity-50
                                            `}
                                        >
                                            <Send size={14} />
                                            {testStatus === "sending" ? "发送中..." :
                                                testStatus === "success" ? "成功!" :
                                                    testStatus === "error" ? "失败" : "测试"}
                                        </button>
                                    </div>
                                </div>

                                {/* Threshold Settings */}
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-1">
                                        <label className="text-sm font-medium text-slate-700">SF 开差阈值 (%)</label>
                                        <input
                                            type="number"
                                            step="0.1"
                                            min="0"
                                            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                                            value={feishu.sfSpreadThreshold}
                                            onChange={(e) => updateFeishu({ sfSpreadThreshold: parseFloat(e.target.value) || 0 })}
                                        />
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-sm font-medium text-slate-700">FF 开差阈值 (%)</label>
                                        <input
                                            type="number"
                                            step="0.1"
                                            min="0"
                                            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                                            value={feishu.ffSpreadThreshold}
                                            onChange={(e) => updateFeishu({ ffSpreadThreshold: parseFloat(e.target.value) || 0 })}
                                        />
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-sm font-medium text-slate-700">资金费率阈值 (%)</label>
                                        <input
                                            type="number"
                                            step="0.01"
                                            min="0"
                                            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                                            value={feishu.fundingRateThreshold}
                                            onChange={(e) => updateFeishu({ fundingRateThreshold: parseFloat(e.target.value) || 0 })}
                                        />
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-sm font-medium text-slate-700">资金周期 (小时, 0=不限)</label>
                                        <input
                                            type="number"
                                            step="1"
                                            min="0"
                                            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                                            value={feishu.fundingIntervalFilter}
                                            onChange={(e) => updateFeishu({ fundingIntervalFilter: parseInt(e.target.value) || 0 })}
                                        />
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-sm font-medium text-slate-700">指数差价阈值 (%)</label>
                                        <input
                                            type="number"
                                            step="0.1"
                                            min="0"
                                            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                                            value={feishu.indexSpreadThreshold}
                                            onChange={(e) => updateFeishu({ indexSpreadThreshold: parseFloat(e.target.value) || 0 })}
                                        />
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-sm font-medium text-slate-700">冷却时间 (分钟)</label>
                                        <input
                                            type="number"
                                            step="1"
                                            min="1"
                                            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm"
                                            value={feishu.cooldownMinutes}
                                            onChange={(e) => updateFeishu({ cooldownMinutes: parseInt(e.target.value) || 5 })}
                                        />
                                    </div>
                                </div>
                                <p className="text-xs text-slate-400">设置为 0 表示该条件不触发推送；同一币种推送间隔为冷却时间</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
