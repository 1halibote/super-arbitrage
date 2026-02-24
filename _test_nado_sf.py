import requests, json

r = requests.get("http://localhost:8000/api/prices")
d = r.json()
cols = d["cols"]
rows = d["rows"]

nado_f_idx = cols.index("nado_future")

nado_with = [(r[0], r[nado_f_idx]) for r in rows if r[nado_f_idx]["bid"] > 0]
print(f"Nado future data in {len(nado_with)} symbols:")
for s, v in nado_with[:10]:
    print(f"  {s}: {v}")

# Check SF calc
# The snapshot should have nado_linear entries
# Let's check the raw snapshot via the broadcast WS data
import websocket
import threading

ws_data = {}
def on_message(ws, message):
    data = json.loads(message)
    if data.get("type") == "update":
        sf = data["data"].get("sf", {})
        ff = data["data"].get("ff", {})
        sf_rows = sf.get("rows", [])
        ff_rows = ff.get("rows", [])
        nado_sf = [r for r in sf_rows if "nado" in str(r)]
        nado_ff = [r for r in ff_rows if "nado" in str(r)]
        print(f"\nSF total: {len(sf_rows)}, nado in SF: {len(nado_sf)}")
        print(f"FF total: {len(ff_rows)}, nado in FF: {len(nado_ff)}")
        if nado_sf:
            print("SF nado samples:", nado_sf[:2])
        if nado_ff:
            print("FF nado samples:", nado_ff[:2])
        ws.close()

ws = websocket.WebSocketApp("ws://localhost:8000/ws/monitor", on_message=on_message)
t = threading.Thread(target=ws.run_forever)
t.start()
t.join(timeout=5)
