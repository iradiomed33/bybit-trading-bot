#!/usr/bin/env python3
"""Test real API instruments response"""

import sys
import json
sys.path.insert(0, '.')

from exchange.base_client import BybitRestClient

# Initialize client (public endpoint doesn't need valid keys)
client = BybitRestClient('dummy', 'dummy', testnet=True)

# Get raw API response
response = client.get(
    "/v5/market/instruments-info",
    params={"category": "linear", "symbol": "ETHUSDT"},
    signed=False
)

print("=== RAW API RESPONSE ===")
print(json.dumps(response, indent=2))

if response.get("retCode") == 0:
    instruments = response.get("result", {}).get("list", [])
    if instruments:
        eth = instruments[0]
        print("\n=== ETHUSDT lotSizeFilter ===")
        lot_filter = eth.get("lotSizeFilter", {})
        print(json.dumps(lot_filter, indent=2))
        
        print("\n=== ETHUSDT parsed values ===")
        print(f"qtyStep (raw):     {lot_filter.get('qtyStep')}")
        print(f"minOrderQty (raw): {lot_filter.get('minOrderQty')}")
        print(f"maxOrderQty (raw): {lot_filter.get('maxOrderQty')}")
