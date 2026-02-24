
import sys
sys.path.insert(0, ".")
from backend.main import bitget_linear
if bitget_linear:
    limits = bitget_linear.funding_limits.get("AZTECUSDT")
    print(f"funding_limits AZTECUSDT: {limits}")
    print(f"Total limits cached: {len(bitget_linear.funding_limits)}")
