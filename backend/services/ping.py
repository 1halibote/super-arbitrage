
import asyncio
import time
import logging
import json
import aiohttp

class PingMonitor:
    def __init__(self):
        self.latencies = {
            "binance": 0,
            "bybit": 0
        }
        self.running = False

    async def start(self):
        self.running = True
        asyncio.create_task(self._ping_binance())
        asyncio.create_task(self._ping_bybit())

    async def stop(self):
        self.running = False

    def _get_proxy(self):
        # Auto-detect common local proxies if env vars are missing
        # This helps on Windows where Python might miss system proxy
        import socket
        common_ports = [7890, 7897, 10809, 1080, 51837]
        for port in common_ports:
            try:
                # Quick check if port is open
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.1)
                    if s.connect_ex(('127.0.0.1', port)) == 0:
                        p = f"http://127.0.0.1:{port}"
                        # logging.info(f"PingMonitor: Auto-detected local proxy at {p}")
                        return p
            except:
                pass
        return None

    async def _ping_binance(self):
        # Measure HTTP RTT to Binance API
        while self.running:
            try:
                t0 = time.time()
                # [Revert] Remove explicit proxy, stick to trust_env=True
                async with aiohttp.ClientSession(trust_env=True) as session:
                    async with session.get("https://api.binance.com/api/v3/ping", timeout=5) as resp:
                        await resp.text()
                rtt = (time.time() - t0) * 1000
                self.latencies["binance"] = rtt
            except Exception:
                self.latencies["binance"] = 999
            await asyncio.sleep(5)

    async def _ping_bybit(self):
        # Measure HTTP RTT to Bybit API
        while self.running:
            try:
                t0 = time.time()
                # [Revert] Remove explicit proxy, stick to trust_env=True
                async with aiohttp.ClientSession(trust_env=True) as session:
                    async with session.get("https://api.bybit.com/v5/market/time", timeout=5) as resp:
                        await resp.text()
                rtt = (time.time() - t0) * 1000
                self.latencies["bybit"] = rtt
            except Exception:
                self.latencies["bybit"] = 999
            await asyncio.sleep(5)

    def get_latencies(self):
        return self.latencies
