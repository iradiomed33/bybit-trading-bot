#!/usr/bin/env python3
"""Test all symbols after fix"""

import sys
sys.path.insert(0, '.')

from exchange.base_client import BybitRestClient
from exchange.instruments import InstrumentsManager

client = BybitRestClient('dummy', 'dummy', testnet=True)
mgr = InstrumentsManager(client)

# Load all instruments
symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT']
mgr.load_instruments(symbols)

print("=" * 70)
print("INSTRUMENTS AFTER FIX (using real API data)")
print("=" * 70)

for symbol in symbols:
    instr = mgr.get_instrument(symbol)
    if instr:
        print(f"\n{symbol}:")
        print(f"  tickSize:    {instr['tickSize']}")
        print(f"  qtyStep:     {instr['qtyStep']}")
        print(f"  minOrderQty: {instr['minOrderQty']}")
        print(f"  maxOrderQty: {instr['maxOrderQty']}")
        print(f"  minNotional: {instr['minNotional']}")
        
        # Test normalization with example qty
        test_qty = 0.664047
        normalized = mgr.normalize_qty(symbol, test_qty)
        print(f"  Test: {test_qty} → {normalized}")
