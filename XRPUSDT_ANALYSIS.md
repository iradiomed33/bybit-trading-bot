# XRPUSDT Testnet Data Analysis - February 14, 2026

## Summary
XRPUSDT is **SUPPORTED** on Bybit testnet and the API returns valid responses, but the symbol has **NO TRADING ACTIVITY**, resulting in frozen price data.

---

## Investigation Results

### 1. **Code Location for Kline Fetching**

**File:** [exchange/market_data.py](exchange/market_data.py#L87-L139)

```python
def get_kline(
    self,
    symbol: str,
    interval: str = "1",
    category: str = "linear",
    limit: int = 200,
    start: Optional[int] = None,
    end: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Получить исторические свечи (kline/candlestick).
    
    Docs: https://bybit-exchange.github.io/docs/v5/market/kline
    """
    params = {"category": category, "symbol": symbol, "interval": interval, "limit": limit}
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    
    logger.debug(f"Fetching kline: {symbol} {interval} (limit={limit})")
    response = self.client.get("/v5/market/kline", params=params)
    return response
```

**Used by:** [bot/trading_bot.py](bot/trading_bot.py#L949-L975) in `_load_market_data()` method

---

### 2. **Symbol Format Used**

**Format:** `XRPUSDT` (correct)

- **API Expects:** `XRPUSDT` for linear perpetuals
- **Category:** `linear`
- **Endpoint:** `https://api-testnet.bybit.com/v5/market/kline`

**Configuration:** [exchange/instruments.py](exchange/instruments.py#L68-L78)

```python
"XRPUSDT": {
    "tickSize": "0.0001",
    "qtyStep": "0.1",
    "minOrderQty": "0.1",
    "maxOrderQty": "100000.0",
    "minNotional": "5.0",
    "basePrecision": 1,
    "quotePrecision": 4,
}
```

---

### 3. **Is XRPUSDT Supported on Bybit Testnet?**

✅ **YES** - XRPUSDT is supported and returns valid API responses.

**Test Results:**

```
URL: https://api-testnet.bybit.com/v5/market/kline
Params: {"category": "linear", "symbol": "XRPUSDT", "interval": "60", "limit": 10}

Response Code: 0 - OK
Candles received: 10
```

**All tested symbols work:**
- BTCUSDT: ✅ OK
- ETHUSDT: ✅ OK
- SOLUSDT: ✅ OK
- XRPUSDT: ✅ OK

---

### 4. **The Actual Problem: Zero Trading Volume**

**Recent XRPUSDT Kline Data (Feb 14, 2026):**

```
Timestamp            Open       High       Low        Close      Volume
--------------------------------------------------------------------------------
1771059600000        1.4592     1.4592     1.4592     1.4592     0          ← FROZEN
1771056000000        1.4592     1.4592     1.4592     1.4592     0          ← FROZEN
1771052400000        1.4592     1.4592     1.4592     1.4592     0          ← FROZEN
1771048800000        1.4592     1.4592     1.4592     1.4592     0          ← FROZEN
1771045200000        1.4592     1.4592     1.4592     1.4592     0          ← FROZEN
1771041600000        1.4592     1.4592     1.4592     1.4592     0          ← FROZEN
1771038000000        1.4592     1.4592     1.4592     1.4592     0          ← FROZEN
1771034400000        1.4592     1.4592     1.4592     1.4592     0          ← FROZEN
1771030800000        1.4515     1.4592     1.4091     1.4592     5588.9     ← Last trade
1771027200000        1.4515     1.4515     1.4515     1.4515     2654.8     ← Previous trade
```

**Analysis:**
- ⚠️ **8 out of 10 most recent candles have ZERO volume**
- ⚠️ **Price frozen at 1.4592** for all zero-volume candles
- ⚠️ **Last trading activity:** ~8 hours ago (as of current timestamp)
- ⚠️ **OHLC all identical** when volume = 0 (open = high = low = close = 1.4592)

---

### 5. **Impact on Indicators**

When price data is frozen (all OHLC values identical):

```
Price Data:
  close = 1.4592, 1.4592, 1.4592, 1.4592, 1.4592... (all same)
  high  = 1.4592, 1.4592, 1.4592, 1.4592, 1.4592... (no range)
  low   = 1.4592, 1.4592, 1.4592, 1.4592, 1.4592... (no range)

Resulting Indicators:
  ATR   = 0.00         (no volatility because high = low)
  ADX   = nan          (no trend because no price movement)
  EMA_20 = 1.4592      (all prices same → EMA = that price)
  EMA_50 = 1.4592      (all prices same → EMA = that price)
  RSI   = 50 or nan    (no up/down movement)
  BB_width = 0         (no standard deviation)
```

**This is expected behavior** - indicators correctly reflect that there's no market activity.

---

### 6. **Error Handling for Unsupported Symbols**

**Location:** [exchange/market_data.py](exchange/market_data.py#L61-L82)

```python
def get_instruments_info(...) -> Dict[str, Any]:
    try:
        response = self.client.get("/v5/market/instruments-info", params=params)
        
        # Check for "Illegal category" error (testnet issue)
        if response.get("retCode") == 10001 and "Illegal category" in response.get("retMsg", ""):
            logger.warning(f"Testnet instruments-info failed with 10001, using fallback")
            # Fallback: return minimal structure
            return {
                "retCode": 0,
                "retMsg": "OK (fallback)",
                "result": {"category": category, "list": []}
            }
        return response
    except Exception as e:
        logger.error(f"Failed to get instruments info: {e}")
        # Fallback to empty result
        return {
            "retCode": 0,
            "retMsg": "OK (fallback)",
            "result": {"category": category, "list": []}
        }
```

**Fallback params:** [exchange/instruments.py](exchange/instruments.py#L32-L78) provides hard-coded parameters for BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT when API fails.

---

### 7. **Historical Context from Logs**

**Feb 12, 2026** - XRPUSDT had active trading:
```
10:01:10 - XRPUSDT price: 1.3699
10:01:25 - XRPUSDT price: 1.3662
10:07:06 - XRPUSDT price: 1.4176
10:08:28 - XRPUSDT price: 1.4355
```

**Issues observed:**
- "Bad orderbook data: deviation=3.99%"
- "Excessive spread: 5.84% > 0.8%"

**Conclusion:** XRPUSDT *was* trading on testnet but has low liquidity and poor orderbook quality.

---

## Root Cause

This is a **testnet data quality issue**, NOT a bot code issue:

1. ✅ Symbol format is correct (`XRPUSDT`)
2. ✅ API endpoint is correct (`/v5/market/kline`)
3. ✅ XRPUSDT is supported on Bybit testnet
4. ❌ **XRPUSDT has no active traders on testnet**
5. ❌ **Zero volume → frozen prices → indicators = 0/nan**

---

## Recommendations

### Option 1: Remove XRPUSDT from testnet trading
**File:** [config/bot_settings.json](config/bot_settings.json)

Remove XRPUSDT from the symbols list:
```json
"symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
```

### Option 2: Add zero-volume detection
Add validation in [bot/trading_bot.py](bot/trading_bot.py) `_load_market_data()` to skip symbols with zero volume:

```python
# After loading candles:
recent_volume = df['volume'].iloc[-10:].sum()  # Last 10 candles
if recent_volume == 0:
    logger.warning(f"{self.symbol}: No trading activity (zero volume), skipping")
    return None
```

### Option 3: Use mainnet for XRPUSDT (if allowed)
XRPUSDT has active trading on mainnet. If testing requires XRPUSDT, consider using mainnet data with testnet execution.

---

## Test Script

Created [test_xrp_kline.py](test_xrp_kline.py) to verify XRPUSDT kline data anytime:

```bash
python test_xrp_kline.py
```

---

**Date:** February 14, 2026  
**Status:** ✅ Investigation Complete  
**Action Required:** Choose Option 1, 2, or 3 above
