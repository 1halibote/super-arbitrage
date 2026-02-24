export interface ArbitrageOpportunity {
    symbol: string;
    type: "SF" | "FF" | "SS";
    pair: string;          // e.g. "Binance/Bybit"
    openSpread: number;    // Open Position Spread %
    closeSpread: number;   // Close Position Spread %
    fundingRateA: number;  // Funding Rate % for Ex1
    fundingIntervalA: string; // e.g. "8h"
    fundingRateB: number;  // Funding Rate % for Ex2
    fundingIntervalB: string;
    netFundingRate: number;// Net Funding Rate %
    indexSpread: number;   // Index Price Spread %
    volume: number;        // 24h Volume (Aggregated)
    volumeA: number;
    volumeB: number;
    fundingMaxA?: number;
    fundingMinA?: number;
    fundingMaxB?: number;
    fundingMinB?: number;
    indexDiffA: number;
    indexDiffB: number;
    indexPriceA?: number;
    indexPriceB?: number;
    details: {
        ex1: string;
        ex1_price: number;
        ex2: string;
        ex2_price: number;
    };
}

export interface ArbitrageData {
    sf: ArbitrageOpportunity[];
    ff: ArbitrageOpportunity[];
    ss: ArbitrageOpportunity[];
}

export interface PriceData {
    bid: number;
    ask: number;
    last: number;
}

export interface PriceRow {
    symbol: string;
    binance_spot: PriceData;
    binance_future: PriceData;
    bybit_spot: PriceData;
    bybit_future: PriceData;
    bitget_spot: PriceData;
    bitget_future: PriceData;
    gate_spot: PriceData;
    gate_future: PriceData;
    nado_spot: PriceData;
    nado_future: PriceData;
    lighter_spot: PriceData;
    lighter_future: PriceData;
}
