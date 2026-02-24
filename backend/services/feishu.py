"""
飞书推送服务
用于将套利机会推送到飞书机器人
"""
import asyncio
import aiohttp
import logging
import time
from datetime import datetime
from typing import Dict, Any, List

class FeishuNotifier:
    def __init__(self):
        # 防抖：记录每个币种的上次推送时间
        self.last_push_time: Dict[str, float] = {}
        
    async def send_test_message(self, webhook_url: str) -> bool:
        """发送测试消息"""
        return await self.push(
            webhook_url,
            "🟢 飞书推送测试成功",
            "您的 webhook 配置正确，可以正常接收套利机会通知。\n\n**当前时间**: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

    async def push(self, webhook_url: str, title: str, content: str) -> bool:
        """
        发送飞书卡片消息
        """
        if not webhook_url:
            return False
            
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"content": title, "tag": "plain_text"},
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {"content": content, "tag": "lark_md"}
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {"tag": "plain_text", "content": f"推送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
                        ]
                    }
                ]
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("code") == 0 or data.get("StatusCode") == 0:
                            logging.info(f"飞书推送成功: {title}")
                            return True
                        else:
                            logging.warning(f"飞书推送失败: {data}")
                            return False
                    else:
                        logging.error(f"飞书推送 HTTP 错误: {resp.status}")
                        return False
        except Exception as e:
            logging.error(f"飞书推送异常: {e}")
            return False
    
    def should_push(self, symbol: str, push_type: str, cooldown_seconds: int) -> bool:
        """
        检查是否应该推送（防抖）
        """
        key = f"{symbol}:{push_type}"
        now = time.time()
        last = self.last_push_time.get(key, 0)
        
        if now - last >= cooldown_seconds:
            self.last_push_time[key] = now
            return True
        return False
    
    async def check_and_notify(self, opps: Dict[str, Dict[str, dict]], config: Dict[str, Any]):
        """
        批量检查并通知 (Main Entry Point)
        """
        if not config.get('enabled') or not config.get('webhookUrl'):
            return

        url = config['webhookUrl']
        sf_th = float(config.get('sfSpreadThreshold', 0))
        ff_th = float(config.get('ffSpreadThreshold', 0))
        fund_th = float(config.get('fundingRateThreshold', 0))
        fund_int = int(config.get('fundingIntervalFilter', 0))
        idx_th = float(config.get('indexSpreadThreshold', 0))
        blocked = config.get('blockedSymbols', [])
        cooldown = int(config.get('cooldownMinutes', 5))

        # Flatten opps dict[symbol][pair] -> opp
        for symbol, pair_data in opps.items():
            for pair_key, opp in pair_data.items():
                # Run actual check
                await self.check_and_push(
                    url, opp,
                    sf_threshold=sf_th,
                    ff_threshold=ff_th,
                    funding_threshold=fund_th,
                    funding_interval_filter=fund_int,
                    index_threshold=idx_th,
                    blocked_symbols=blocked,
                    cooldown_minutes=cooldown
                )

    async def check_and_push(
        self,
        webhook_url: str,
        data: Dict[str, Any],
        sf_threshold: float = 0,
        ff_threshold: float = 0,
        funding_threshold: float = 0,
        funding_interval_filter: int = 0,
        index_threshold: float = 0,
        blocked_symbols: List[str] = None,
        cooldown_minutes: int = 5,
    ) -> None:
        """
        检查数据是否满足阈值条件，满足则推送
        
        Args:
            webhook_url: 飞书 Webhook URL
            data: 套利机会数据
            sf_threshold: SF 开差阈值 (%)
            ff_threshold: FF 开差阈值 (%)
            funding_threshold: 资金费率阈值 (%)
            funding_interval_filter: 资金周期过滤 (小时)
            index_threshold: 指数差价阈值 (%)
            blocked_symbols: 屏蔽的币种列表
            cooldown_minutes: 冷却时间（分钟）
        """
        if not webhook_url:
            return
        
        if blocked_symbols is None:
            blocked_symbols = []
            
        symbol = data.get("symbol", "")
        
        # 如果币种被屏蔽，直接返回
        # 支持模糊匹配：如果屏蔽 "FLOW"，则 "FLOWUSDT" 也被屏蔽
        if blocked_symbols:
            for blocked in blocked_symbols:
                if blocked.upper() in symbol.upper():
                    logging.debug(f"Blocked push for {symbol} (matched in {blocked})")
                    return
        
        pair_type = data.get("type", "")  # SF, FF, SS
        open_spread = data.get("openSpread", 0)  # 保留正负，用于判断正负
        funding_rate_a = abs(data.get("fundingRateA", 0))
        funding_rate_b = abs(data.get("fundingRateB", 0))
        interval_a = data.get("fundingIntervalA", 8)
        interval_b = data.get("fundingIntervalB", 8)
        index_diff = abs(data.get("indexDiffA", 0))
        
        # 计算冷却时间（秒）
        cooldown_seconds = cooldown_minutes * 60
        
        messages = []
        
        # 检查 SF 开差 - 只推送正开差
        if sf_threshold > 0 and pair_type == "SF" and open_spread >= sf_threshold:
            if self.should_push(symbol, "sf_spread", cooldown_seconds):
                messages.append(f"**SF 开差**: {open_spread:.2f}% (≥{sf_threshold}%)")
        
        # 检查 FF 开差 - 只推送正开差
        if ff_threshold > 0 and pair_type == "FF" and open_spread >= ff_threshold:
            if self.should_push(symbol, "ff_spread", cooldown_seconds):
                messages.append(f"**FF 开差**: {open_spread:.2f}% (≥{ff_threshold}%)")
        
        # 检查资金费率
        if funding_threshold > 0:
            # 检查 A 方资金费率
            if funding_rate_a >= funding_threshold:
                if funding_interval_filter == 0 or interval_a == funding_interval_filter:
                    if self.should_push(symbol, "funding_a", cooldown_seconds):
                        messages.append(f"**资金费率A**: {funding_rate_a:.4f}% / {interval_a}h")
            # 检查 B 方资金费率
            if funding_rate_b >= funding_threshold:
                if funding_interval_filter == 0 or interval_b == funding_interval_filter:
                    if self.should_push(symbol, "funding_b", cooldown_seconds):
                        messages.append(f"**资金费率B**: {funding_rate_b:.4f}% / {interval_b}h")
        
        # 检查指数差价
        if index_threshold > 0 and index_diff >= index_threshold:
            if self.should_push(symbol, "index_diff", cooldown_seconds):
                messages.append(f"**指数差价**: {index_diff:.2f}% (≥{index_threshold}%)")
        
        # 如果有消息需要推送（触发了至少一个条件）
        if messages:
            details = data.get("details", {})
            ex_top = details.get("ex1", "Unknown")
            ex_bot = details.get("ex2", "Unknown")
            
            # 格式化所有数据
            close_spread = data.get("closeSpread", 0)
            net_funding = data.get("netFundingRate", 0)
            
            # 格式化资金费率详情
            fr_a = data.get("fundingRateA", 0)
            int_a = data.get("fundingIntervalA", 8)
            max_a = data.get("fundingMaxA", 0)
            min_a = data.get("fundingMinA", 0)
            
            fr_b = data.get("fundingRateB", 0)
            int_b = data.get("fundingIntervalB", 8)
            max_b = data.get("fundingMaxB", 0)
            min_b = data.get("fundingMinB", 0)
            
            # 格式化指数差价
            idx_diff_a = data.get("indexDiffA", 0)
            idx_diff_b = data.get("indexDiffB", 0)
            
            # 交易额
            vol_a = data.get("volumeA", 0)
            vol_b = data.get("volumeB", 0)
            
            # 辅助格式化函数
            def fmt_vol(v):
                if v >= 1000000: return f"{v/1000000:.1f}M"
                if v >= 1000: return f"{v/1000:.1f}K"
                return f"{v:.0f}"

            # 构建详细信息块
            info_block = [
                f"**触发原因**: {', '.join(messages)}",
                "---",
                f"**开/清差价**: {open_spread:.2f}% / {close_spread:.2f}%",
                f"**交易所**: {ex_top} (Long) / {ex_bot} (Short)",
                f"**净资金费率**: {net_funding:.4f}%",
                f"**资金费率 A**: {fr_a:.4f}% / {int_a}h (限: {min_a:.1f}% ~ {max_a:.1f}%)",
                f"**资金费率 B**: {fr_b:.4f}% / {int_b}h (限: {min_b:.1f}% ~ {max_b:.1f}%)",
                f"**指数差价**: A:{idx_diff_a:.2f}% | B:{idx_diff_b:.2f}%",
                f"**24H交易额**: A: {fmt_vol(vol_a)} | B: {fmt_vol(vol_b)}"
            ]
            
            content = f"**币种**: {symbol}\n\n" + "\n".join(info_block)
            
            await self.push(webhook_url, f"🚨 套利机会: {symbol}", content)


# 全局实例
feishu_notifier = FeishuNotifier()
