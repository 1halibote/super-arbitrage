"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

interface FeishuSettings {
    enabled: boolean;
    webhookUrl: string;
    sfSpreadThreshold: number;   // SF 开清差价阈值 (%)
    ffSpreadThreshold: number;   // FF 开清差价阈值 (%)
    fundingRateThreshold: number; // 资金费率阈值 (%)
    fundingIntervalFilter: number; // 周期过滤 (小时，0=不限)
    indexSpreadThreshold: number; // 指数差价阈值 (%)
    cooldownMinutes: number;      // 冷却时间 (分钟)
}

interface Settings {
    minVolume: number;
    spreadAlertThreshold: number;
    clockAlertEnabled: boolean;
    pinnedSymbols: string[];
    enabledExchanges: {
        binance: { spot: boolean; contract: boolean };
        bybit: { spot: boolean; contract: boolean };
        bitget: { spot: boolean; contract: boolean };
        gate: { spot: boolean; contract: boolean };
        nado: { spot: boolean; contract: boolean };
        lighter: { spot: boolean; contract: boolean };
    };
    blockedSymbols: string[];
    feishu: FeishuSettings;
}

interface SettingsContextType extends Settings {
    updateSettings: (newSettings: Partial<Settings>) => void;
    togglePin: (symbol: string) => void;
    clearPinned: () => void;
    toggleExchange: (exchange: 'binance' | 'bybit' | 'bitget' | 'gate' | 'nado' | 'lighter', type: 'spot' | 'contract') => void;
    addBlockedSymbol: (symbol: string) => void;
    removeBlockedSymbol: (symbol: string) => void;
    updateFeishu: (newFeishu: Partial<FeishuSettings>) => void;
}

const defaultFeishu: FeishuSettings = {
    enabled: false,
    webhookUrl: '',
    sfSpreadThreshold: 0,
    ffSpreadThreshold: 0,
    fundingRateThreshold: 0,
    fundingIntervalFilter: 0,
    indexSpreadThreshold: 0,
    cooldownMinutes: 5,
};

const defaultSettings: Settings = {
    minVolume: 0,
    spreadAlertThreshold: 0.5,
    clockAlertEnabled: true,
    pinnedSymbols: [],
    enabledExchanges: {
        binance: { spot: true, contract: true },
        bybit: { spot: true, contract: true },
        bitget: { spot: true, contract: true },
        gate: { spot: true, contract: true },
        nado: { spot: true, contract: true },
        lighter: { spot: true, contract: true },
    },
    blockedSymbols: [],
    feishu: defaultFeishu,
};

const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

export function SettingsProvider({ children }: { children: React.ReactNode }) {
    const [settings, setSettings] = useState<Settings>(defaultSettings);
    const [isLoaded, setIsLoaded] = useState(false);

    // Load from localStorage on mount
    useEffect(() => {
        const saved = localStorage.getItem("arbitrage_settings_v1");
        if (saved) {
            try {
                // Deep merge to ensure nested objects (enabledExchanges) are preserved if missing in saved data
                const parsed = JSON.parse(saved);
                setSettings({
                    ...defaultSettings,
                    ...parsed,
                    enabledExchanges: { ...defaultSettings.enabledExchanges, ...parsed.enabledExchanges },
                });
            } catch (e) {
                console.error("Failed to parse settings", e);
            }
        }
        setIsLoaded(true);
    }, []);

    // Save to localStorage on change
    useEffect(() => {
        if (isLoaded) {
            localStorage.setItem("arbitrage_settings_v1", JSON.stringify(settings));
        }
    }, [settings, isLoaded]);

    // 跨标签页同步：监听其他标签页的 localStorage 变更
    useEffect(() => {
        const handleStorage = (e: StorageEvent) => {
            if (e.key === "arbitrage_settings_v1" && e.newValue) {
                try {
                    const parsed = JSON.parse(e.newValue);
                    setSettings({
                        ...defaultSettings,
                        ...parsed,
                        enabledExchanges: { ...defaultSettings.enabledExchanges, ...parsed.enabledExchanges },
                    });
                } catch { }
            }
        };
        window.addEventListener("storage", handleStorage);
        return () => window.removeEventListener("storage", handleStorage);
    }, []);

    // Sync Feishu config to backend
    useEffect(() => {
        if (!isLoaded) return;

        // Debounce sync
        const timer = setTimeout(() => {
            fetch("/api/feishu/config", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    ...settings.feishu,
                    blockedSymbols: settings.blockedSymbols
                })
            }).catch(console.error);
        }, 1000);

        return () => clearTimeout(timer);
    }, [settings.feishu, settings.blockedSymbols, isLoaded]);

    const updateSettings = (newSettings: Partial<Settings>) => {
        setSettings(prev => ({ ...prev, ...newSettings }));
    };

    const togglePin = (symbol: string) => {
        setSettings(prev => {
            const isPinned = prev.pinnedSymbols.includes(symbol);
            const newPinned = isPinned
                ? prev.pinnedSymbols.filter(s => s !== symbol)
                : [symbol, ...prev.pinnedSymbols];
            return { ...prev, pinnedSymbols: newPinned };
        });
    };

    const clearPinned = () => {
        updateSettings({ pinnedSymbols: [] });
    };

    const toggleExchange = (exchange: 'binance' | 'bybit' | 'bitget' | 'gate' | 'nado' | 'lighter', type: 'spot' | 'contract') => {
        setSettings(prev => ({
            ...prev,
            enabledExchanges: {
                ...prev.enabledExchanges,
                [exchange]: {
                    ...prev.enabledExchanges[exchange],
                    [type]: !prev.enabledExchanges[exchange][type]
                }
            }
        }));
    };

    const addBlockedSymbol = (symbol: string) => {
        const upper = symbol.toUpperCase();
        setSettings(prev => {
            if (prev.blockedSymbols.includes(upper)) return prev;
            return { ...prev, blockedSymbols: [...prev.blockedSymbols, upper] };
        });
    };

    const removeBlockedSymbol = (symbol: string) => {
        const upper = symbol.toUpperCase();
        setSettings(prev => ({
            ...prev,
            blockedSymbols: prev.blockedSymbols.filter(s => s !== upper)
        }));
    };

    const updateFeishu = (newFeishu: Partial<typeof defaultFeishu>) => {
        setSettings(prev => ({
            ...prev,
            feishu: { ...prev.feishu, ...newFeishu }
        }));
    };

    // Prevent hydration mismatch
    if (!isLoaded) {
        return <div className="min-h-screen bg-[#f1f5f9]" />;
    }

    return (
        <SettingsContext.Provider
            value={{
                ...settings,
                updateSettings,
                togglePin,
                clearPinned,
                toggleExchange,
                addBlockedSymbol,
                removeBlockedSymbol,
                updateFeishu,
            }}
        >
            {children}
        </SettingsContext.Provider>
    );
}

export function useSettings() {
    const context = useContext(SettingsContext);
    if (context === undefined) {
        throw new Error("useSettings must be used within a SettingsProvider");
    }
    return context;
}
