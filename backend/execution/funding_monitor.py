
import asyncio
import logging
import time
from datetime import datetime, timedelta
import ccxt.async_support as ccxt
from backend.execution.key_store import api_key_store
from backend.execution import card_manager
from backend.execution.profit_store import profit_store, ProfitRecord

class FundingMonitor:
    def __init__(self):
        self.is_running = False
        self._task = None
        self._last_check_hour = -1

    async def start(self):
        if self.is_running: return
        self.is_running = True
        self._task = asyncio.create_task(self._loop())
        logging.info("[Funding] Monitor started")

    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try: await self._task
            except: pass
        logging.info("[Funding] Monitor stopped")

    async def _loop(self):
        while self.is_running:
            try:
                now = datetime.now()
                # Run periodically. Logic:
                # If current hour != last_check_hour, we run check.
                # But we want to run shortly after the hour (e.g. minute 1 or 2)
                # to ensure settlement is done.
                # Let's run check every 5 minutes, but filter duplicates.
                # Actually user said "Every hour on the hour".
                # Let's run at minute 1 of every hour.
                
                if now.minute == 1 and now.hour != self._last_check_hour:
                    logging.info(f"[Funding] Starting hourly check at {now}")
                    await self.check_funding()
                    self._last_check_hour = now.hour
                
                # Sleep 30s
                await asyncio.sleep(30)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"[Funding] Loop error: {e}")
                await asyncio.sleep(60)

    async def check_funding(self):
        """Check funding fees for all running cards"""
        cards = card_manager.list_cards()
        if not cards: return

        # 1. Identify target symbols per exchange
        # Strategy: SF -> Exchange B (Future). FF -> Exchange A & B.
        targets = {} # {exchange_id: set(symbols)}

        for card in cards:
            if card.status != "running": continue
            
            # Map symbol to exchange format if needed? 
            # CCXT usually needs standardized symbols 'BTC/USDT:USDT' or 'BTC/USDT'.
            # Our card.symbol is 'BTCUSDT'.
            # We will rely on load_markets to find correct symbol or try common formats.

            if card.type == "SF":
                if card.exchange_b:
                    targets.setdefault(card.exchange_b, set()).add(card.symbol)
            elif card.type == "FF":
                if card.exchange_a:
                    targets.setdefault(card.exchange_a, set()).add(card.symbol)
                if card.exchange_b:
                    targets.setdefault(card.exchange_b, set()).add(card.symbol)
        
        logging.info(f"[Funding] Targets: {targets}")

        # 2. Query each exchange
        for exchange_id, symbols in targets.items():
            keys = api_key_store.get_key(exchange_id)
            if not keys:
                logging.warning(f"[Funding] No keys for {exchange_id}")
                continue
            
            try:
                # Init CCXT client
                exchange_class = getattr(ccxt, exchange_id)
                client = exchange_class({
                    'apiKey': keys['apiKey'],
                    'secret': keys['apiSecret'],
                    'enableRateLimit': True
                })
                
                try:
                    await client.load_markets()
                    
                    # Look back 8 hours + buffer
                    since = int((datetime.now() - timedelta(hours=9)).timestamp() * 1000)

                    for symbol_str in symbols:
                        # Find market
                        market = None
                        # Try finding market 
                        # Our symbol is BTCUSDT. CCXT market id might be same, symbol BTC/USDT.
                        # We try to find by id first.
                        found_symbol = None
                        for m_symbol, m in client.markets.items():
                            if m['id'] == symbol_str:
                                found_symbol = m_symbol
                                break
                            if m['symbol'] == symbol_str:
                                found_symbol = m_symbol
                                break
                            # Removing slash
                            if m['symbol'].replace('/', '') == symbol_str:
                                found_symbol = m_symbol
                                break
                        
                        if not found_symbol:
                            # Try constructing standard linear format
                            found_symbol = f"{symbol_str.replace('USDT', '')}/USDT:USDT"
                            if found_symbol not in client.markets:
                                found_symbol = f"{symbol_str.replace('USDT', '')}/USDT"
                        
                        if not found_symbol:
                            logging.warning(f"[Funding] Market not found for {symbol_str} on {exchange_id}")
                            continue

                        # Fetch
                        records = []
                        if exchange_id == 'binance':
                            # fetchIncome
                            # Params: incomeType="FUNDING_FEE"
                            try:
                                incomes = await client.fetch_income(found_symbol, since=since, params={'incomeType': 'FUNDING_FEE'})
                                records = incomes
                            except Exception as ex:
                                logging.error(f"[Funding] Binance fetch failed for {found_symbol}: {ex}")

                        elif exchange_id == 'bybit':
                            # fetchFundingHistory is deprecated? No, usually valid.
                            # Or fetch_execution_list
                            try:
                                if client.has['fetchFundingHistory']:
                                    incomes = await client.fetch_funding_history(found_symbol, since=since)
                                    records = incomes
                                else:
                                    logging.warning(f"[Funding] Bybit fetchFundingHistory not supported?")
                            except Exception as ex:
                                logging.error(f"[Funding] Bybit fetch failed for {found_symbol}: {ex}")

                        # Process records
                        for rec in records:
                            await self._process_record(exchange_id, symbol_str, rec)
                        
                        # Rate limit buffer
                        await asyncio.sleep(0.5)

                finally:
                    await client.close()

            except Exception as e:
                logging.error(f"[Funding] Error processing {exchange_id}: {e}")

    async def _process_record(self, exchange_id, symbol, rec):
        # Filter for USDT only (simplification for now)
        asset = rec.get('asset')
        if not asset and 'info' in rec: return # Skip if can't determine
        # Binance info has 'asset', CCXT might normalize to 'currency' or keep 'asset'
        if asset and asset != 'USDT': 
            return # Skip non-USDT records for now

        # Extract fields
        rec_id = str(rec.get('id', ''))
        if not rec_id:
            # Fallback for Binance Income if id is 'tranId'
            if 'tranId' in rec: rec_id = str(rec['tranId'])
            elif 'info' in rec and 'tranId' in rec['info']: rec_id = str(rec['info']['tranId'])
        
        if not rec_id:
            rec_id = f"{exchange_id}_{symbol}_{rec.get('timestamp')}"

        # Deduplicate
        if profit_store.has_external_id(rec_id):
            return

        # Amount
        amount = float(rec.get('amount', 0) or 0)
        ts = rec.get('timestamp')
        if not ts: return

        # Look up card type
        card_obj = card_manager.get_card_by_symbol(symbol)
        sType = card_obj.type if card_obj else "SF"

        import uuid
        new_record = ProfitRecord(
            id=str(uuid.uuid4()),
            symbol=symbol,
            record_type="funding",
            strategy_type=sType,
            # Funding fees always come from Perpetual (B side usually, or both in FF)
            # Visualize as B side (Yellow)
            exchange_a="", 
            exchange_b=exchange_id, 
            pnl=amount,
            funding_rate=float(rec.get('rate', 0) or 0),
            funding_income_a=0, 
            funding_income_b=amount, # Assign to B
            external_id=rec_id,
            timestamp=ts
        )
        
        profit_store.add_record(new_record)

# Singleton
funding_monitor = FundingMonitor()
