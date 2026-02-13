#!/usr/bin/env python3
"""Debug ETHUSDT instrument parameters"""

import sys
sys.path.insert(0, '.')

from exchange.base_client import BybitRestClient
from exchange.instruments import InstrumentsManager

# Initialize client with dummy credentials (only for public endpoint)
client = BybitRestClient('dummy', 'dummy', testnet=True)
mgr = InstrumentsManager(client)

# Get ETHUSDT parameters
mgr.load_instruments(['ETHUSDT'])
instr = mgr.get_instrument('ETHUSDT')

if instr:
    print("\n=== ETHUSDT Instrument Parameters ===")
    for key, value in instr.items():
        print(f"{key:15s}: {value}")
        
    # Test normalization
    test_qty = 0.664047
    normalized = mgr.normalize_qty('ETHUSDT', test_qty)
    print(f"\nTest normalization:")
    print(f"  Input qty:   {test_qty}")
    print(f"  Normalized:  {normalized}")
    print(f"  qtyStep:     {instr['qtyStep']}")
    print(f"  minOrderQty: {instr['minOrderQty']}")
else:
    print("Failed to get ETHUSDT instrument info")
