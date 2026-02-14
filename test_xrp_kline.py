#!/usr/bin/env python3
"""Quick test of XRPUSDT kline data"""
import requests
import json

url = "https://api-testnet.bybit.com/v5/market/kline"
params = {
    "category": "linear",
    "symbol": "XRPUSDT",
    "interval": "60",
    "limit": 10
}

print("=" * 70)
print("Testing XRPUSDT Kline Data on Bybit Testnet")
print("=" * 70)
print(f"\nRequest: {url}")
print(f"Params: {json.dumps(params, indent=2)}\n")

response = requests.get(url, params=params)
data = response.json()

print(f"Response Code: {data.get('retCode')} - {data.get('retMsg')}")
candles = data.get("result", {}).get("list", [])
print(f"Candles received: {len(candles)}\n")

if candles:
    print("Recent candles:")
    print(f"{'Timestamp':<20} {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10} {'Volume':<15}")
    print("-" * 80)
    for i, candle in enumerate(candles[:10]):
        timestamp = candle[0]
        open_price = candle[1]
        high = candle[2]
        low = candle[3]
        close = candle[4]
        volume = candle[5]
        print(f"{timestamp:<20} {open_price:<10} {high:<10} {low:<10} {close:<10} {volume:<15}")
    
    # Check if all prices are the same (frozen data)
    closes = [float(c[4]) for c in candles]
    highs = [float(c[2]) for c in candles]
    lows = [float(c[3]) for c in candles]
    
    print(f"\n{'='*70}")
    print("Analysis:")
    print(f"  Close prices: min={min(closes):.4f}, max={max(closes):.4f}")
    print(f"  High prices:  min={min(highs):.4f}, max={max(highs):.4f}")
    print(f"  Low prices:   min={min(lows):.4f}, max={max(lows):.4f}")
    
    # Check for frozen/stuck data
    if len(set(closes)) == 1:
        print(f"\n  ⚠️ WARNING: All close prices are identical ({closes[0]:.4f})")
        print("  This suggests frozen/invalid data")
    elif max(closes) - min(closes) < 0.001:
        print(f"\n  ⚠️ WARNING: Very low price variance ({max(closes) - min(closes):.6f})")
        print("  Data may be frozen or invalid")
    else:
        print(f"\n  ✅ OK: Price variance detected ({max(closes) - min(closes):.4f})")
        print("  Data appears valid")
else:
    print("❌ No candles received!")

print(f"\n{'='*70}\n")
