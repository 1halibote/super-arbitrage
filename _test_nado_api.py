import requests, json

# 查 Archive API
archive_url = "https://archive.prod.nado.xyz/v1"

# 测试几个可能的端点
endpoints = [
    f"/products/2/snapshots",
    f"/products/2/funding-rates",
    f"/products/2/candles",
    f"/products",
    f"/tickers",
    f"/ticker?product_id=2",
    f"/stats",
    f"/market-summaries",
]

for ep in endpoints:
    try:
        r = requests.get(f"{archive_url}{ep}", timeout=3)
        text = r.text[:200] if r.text else "empty"
        print(f"GET {ep}: {r.status_code} -> {text}")
    except Exception as e:
        print(f"GET {ep}: ERROR {e}")

# 也查 v2 的
archive_v2 = "https://archive.prod.nado.xyz/v2"
for ep in ["/tickers", "/products", "/candles?product_id=2&granularity=3600&limit=1"]:
    try:
        r = requests.get(f"{archive_v2}{ep}", timeout=3)
        text = r.text[:200] if r.text else "empty"
        print(f"V2 GET {ep}: {r.status_code} -> {text}")
    except Exception as e:
        print(f"V2 GET {ep}: ERROR {e}")
