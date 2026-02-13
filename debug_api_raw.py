#!/usr/bin/env python3
"""Debug raw API response from Bybit"""

import sys
import json
sys.path.insert(0, '.')

from exchange.base_client import BybitRestClient

# Initialize client
client = BybitRestClient('dummy', 'dummy', testnet=True)

# Get raw instruments info
response = client.get(
    "/v5/market/instruments-info",
    params={
        "category": "linear",
        "symbol": "ETHUSDT",
    },
    signed=False,
)

print("\n=== RAW API Response for ETHUSDT ===")
print(json.dumps(response, indent=2))

if response.get("retCode") == 0:
    instruments = response.get("result", {}).get("list", [])
    if instruments:
        eth_data = instruments[0]
        print("\n=== ETHUSDT lotSizeFilter ===")
        print(json.dumps(eth_data.get("lotSizeFilter", {}), indent=2))
        
        print("\n=== ETHUSDT priceFilter ===")
        print(json.dumps(eth_data.get("priceFilter", {}), indent=2))
        
        print("\n=== Key fields ===")
        print(f"qtyStep from lotSizeFilter: {eth_data.get('lotSizeFilter', {}).get('qtyStep')}")
        print(f"minOrderQty from lotSizeFilter: {eth_data.get('lotSizeFilter', {}).get('minOrderQty')}")
        print(f"tickSize from priceFilter: {eth_data.get('priceFilter', {}).get('tickSize')}")
