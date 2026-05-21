import json
import os
import sys

# Load local files
with open("bot_trades.json", "r", encoding="utf-8") as f:
    local_trades = json.load(f)

with open("bot_avoided_trades.json", "r", encoding="utf-8") as f:
    local_avoided = json.load(f)

# Load cloud files (from the downloaded cloud_trades_debug.json)
cloud_debug_path = r"C:\Users\berke\.gemini\antigravity\brain\5b07afe2-4582-4f9b-a7c9-43a20e01a4a4\scratch\cloud_trades_debug.json"
with open(cloud_debug_path, "r", encoding="utf-8") as f:
    cloud_data = json.load(f)
    cloud_trades = cloud_data.get("trades", [])
    cloud_avoided = cloud_data.get("avoided", [])

# Clean lists
def is_valid_trade(t):
    if not isinstance(t, dict):
        return False
    if "coin" not in t or "id" not in t:
        return False
    if t["id"] in ("render_avax_live", "avoid_btc"):
        return False
    if "durum" not in t:
        return False
    return True

def is_valid_avoided(t):
    if not isinstance(t, dict):
        return False
    if "coin" not in t or "id" not in t:
        return False
    if t["id"] in ("render_avax_live", "avoid_btc"):
        return False
    return True

# Merge trades using a dictionary keyed by ID
trade_map = {}
for t in local_trades:
    if is_valid_trade(t):
        trade_map[str(t["id"])] = t

for t in cloud_trades:
    if is_valid_trade(t):
        tid = str(t["id"])
        if tid in trade_map:
            local_t = trade_map[tid]
            if t.get("durum") == "KAPALI" and local_t.get("durum") != "KAPALI":
                trade_map[tid] = t
            elif t.get("pnl_usdt", 0) != 0 and local_t.get("pnl_usdt", 0) == 0:
                trade_map[tid] = t
        else:
            trade_map[tid] = t

merged_trades = list(trade_map.values())
try:
    merged_trades.sort(key=lambda x: x.get("tarih", ""), reverse=True)
except:
    pass

# Merge avoided trades
avoided_map = {}
for a in local_avoided:
    if is_valid_avoided(a):
        avoided_map[str(a["id"]) + "_" + a["coin"]] = a

for a in cloud_avoided:
    if is_valid_avoided(a):
        key = str(a["id"]) + "_" + a["coin"]
        avoided_map[key] = a

merged_avoided = list(avoided_map.values())
try:
    merged_avoided.sort(key=lambda x: x.get("tarih", ""), reverse=True)
except:
    pass

# Save merged clean databases back to workspace files
with open("bot_trades.json", "w", encoding="utf-8") as f:
    json.dump(merged_trades, f, indent=4, ensure_ascii=False)

with open("bot_avoided_trades.json", "w", encoding="utf-8") as f:
    json.dump(merged_avoided, f, indent=4, ensure_ascii=False)

print(f"Successfully merged databases locally!")
print(f"Total trades: {len(merged_trades)}")
print(f"Total avoided: {len(merged_avoided)}")

# Force import and push to cloud using db_manager
from db_manager import db_manager
import time
db_manager.push_to_cloud()
print("Triggered Telegram cloud sync push! Sleeping 5s to allow upload thread to complete...")
time.sleep(5)
print("Finished cloud push!")
