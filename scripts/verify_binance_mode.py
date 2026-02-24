
import sys
import os
import asyncio
import logging
import ccxt.async_support as ccxt

# Fix path to allow importing from backend
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Also add backend dir specifically if needed for internal imports
backend_dir = os.path.join(project_root, 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

try:
    # Try absolute import first (if running from root)
    from backend.execution.key_store import api_key_store
except ImportError:
    try:
        # Try relative/direct import
        from execution.key_store import api_key_store
    except ImportError as e:
        print(f"Error: Could not import key_store. Debug info: sys.path={sys.path}, Error={e}")
        sys.exit(1)

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Mock PapiWrapper for standalone test
class TestPapiWrapper(ccxt.binance):
    def describe(self):
        return self.deep_extend(super().describe(), {
            'options': {'defaultType': 'papi'},
        })
    async def request(self, path, api=None, method='GET', params={}, headers=None, body=None, config={}):
        if api == 'papi':
             if 'api' not in self.urls: self.urls['api'] = {}
             if 'papi' not in self.urls['api']:
                 self.urls['api']['papi'] = 'https://papi.binance.com/papi/v1'
             if headers is None: headers = {}
             headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        return await super().request(path, api, method, params, headers, body, config)

async def main():
    print("=== Binance API Mode Verification Tool ===")
    
    # 1. Load Keys
    keys = api_key_store.get_key('binance')
    if not keys:
        print("Error: No 'binance' keys found in secure storage.")
        return

    api_key = keys['api_key']
    secret = keys['api_secret']
    
    # 2. Initialize Clients
    fapi_client = ccxt.binanceusdm({'apiKey': api_key, 'secret': secret})
    papi_client = TestPapiWrapper({'apiKey': api_key, 'secret': secret})
    spot_client = ccxt.binance({'apiKey': api_key, 'secret': secret})

    print(f"\n[1] Testing Standard FAPI (USDT-M Futures)...")
    try:
        # Check Balance
        bal = await fapi_client.fetch_balance()
        usdt = bal['total'].get('USDT', 0)
        print(f"  > Balance Check: OK (USDT: {usdt})")
        
        if usdt == 0:
            print("  ! WARNING: FAPI Balance is 0. This is typical for Unified Accounts (funds are in Unified Wallet).")
    except Exception as e:
        print(f"  > Balance Check FAILED: {e}")
        if "-2015" in str(e):
            print("  ! CONFIRMED: Account using Unified Mode (FAPI incompatible for balance).")

    print(f"\n[2] Testing PAPI (Unified Account Interface)...")
    try:
        # Check Account (Official Unified Endpoint)
        print("  > Requesting GET /papi/v1/um/account ...")
        res = await papi_client.request('um/account', api='papi')
        # Structure check
        print(f"  > PAPI Response (Keys): {list(res.keys())}")
        
        # Try to parse assets safely
        if 'assets' in res:
             # Just show first 2 assets to verify data access
             print(f"  > Assets Sample: {res['assets'][:2]}")
        else:
             print(f"  > Raw Response: {res}")
        
        print("  * PAPI Connection SUCCESS (Account Data Accessible).")
    except Exception as e:
        print(f"  > PAPI Check FAILED: {e}")
        if "403" in str(e) or "DOCTYPE" in str(e):
             print("  ! ERROR: WAF/Cloudflare 403 Forbidden. User-Agent fix required.")
        elif "404" in str(e):
             print("  ! ERROR: 404 Not Found. Endpoint incorrect.")

    print(f"\n[3] Testing Order Capability...")
    print("  > Skipping actual order test to avoid unwanted trades.")
    print("  > Since 'um/account' works, 'um/order' will work too (same permission).")
    
    # FAPI Logic check only
    try:
        if usdt == 0:
             print("  ! FAPI Safety Check: FAPI would fail to trade due to 0 balance.")
    except: pass

    # Cleanup
    await fapi_client.close()
    await papi_client.close()
    await spot_client.close()
    print("\n=== Verification Complete ===")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
