# STR-005: Mean Reversion Time-Based Exits & Emergency Stop

**Priority:** P0  
**Status:** ✅ IMPLEMENTED  
**Feature:** Time limits and emergency exits for Mean Reversion strategy  

---

## Overview

STR-005 adds mandatory exit conditions to Mean Reversion strategy to prevent positions from hanging indefinitely. Every MR trade now has:
- **Time limit**: Max bars or minutes before forced exit
- **Hard stop loss**: k * ATR distance from entry
- **Take profit**: Automatic exit when price returns to mean (VWAP)

This ensures **no MR trade hangs forever** and all exits are logged with clear reasons.

---

## Exit Conditions (Priority Order)

### 1. Time Stop
**Triggers when**: Position held beyond time limit

**Parameters:**
- `max_hold_bars`: Maximum number of bars (default: 20)
- `max_hold_minutes`: Optional maximum minutes (if set, overrides bars)

**Example:**
```python
strategy = MeanReversionStrategy(
    max_hold_bars=20,  # Exit after 20 bars
    max_hold_minutes=60  # OR exit after 60 minutes
)
```

**Log output:**
```
[STR-005] MeanReversion TIME_STOP: bars_held=20 >= max=20 | Symbol=BTCUSDT | PnL=1.05%
[STR-005] MeanReversion EXIT: TIME_STOP | Symbol=BTCUSDT | Side=long | Entry=95.00 | Exit=96.00 | Bars=20 | PnL=1.05%
```

---

### 2. Stop Loss (Hard Stop)
**Triggers when**: Price moves against position by k * ATR

**Formula:**
- **LONG**: `stop_price = entry_price - (k * ATR)`
- **SHORT**: `stop_price = entry_price + (k * ATR)`

**Parameter:**
- `stop_loss_atr_multiplier`: ATR multiplier (default: 1.0)

**Example:**
```python
strategy = MeanReversionStrategy(
    stop_loss_atr_multiplier=1.5  # Stop at 1.5x ATR distance
)

# Entry: LONG at 100, ATR=2.0
# Stop = 100 - (1.5 * 2.0) = 97.0
```

**Log output:**
```
[STR-005] MeanReversion STOP_LOSS: price=93.00 hit stop=93.00 | Side=long | Symbol=BTCUSDT | PnL=-2.11%
[STR-005] MeanReversion EXIT: STOP_LOSS | Symbol=BTCUSDT | Side=long | Entry=95.00 | Exit=93.00 | Bars=1 | PnL=-2.11%
```

---

### 3. Take Profit (Mean Reversion)
**Triggers when**: Price returns to mean (VWAP)

**Logic:**
- **LONG**: Entered below VWAP → Exit when `price >= VWAP * 0.999` (0.1% tolerance)
- **SHORT**: Entered above VWAP → Exit when `price <= VWAP * 1.001`

**Tolerance**: 0.1% to avoid whipsaws around exact VWAP level

**Example:**
```
Entry: LONG at 95 (VWAP=100)
Target: Exit at 99.9 or above (100 * 0.999)
```

**Log output:**
```
[STR-005] MeanReversion TAKE_PROFIT: price=100.00 reached mean=100.00 | Side=long | Symbol=BTCUSDT | PnL=5.26%
[STR-005] MeanReversion EXIT: TAKE_PROFIT | Symbol=BTCUSDT | Side=long | Entry=95.00 | Exit=100.00 | Bars=1 | PnL=5.26%
```

---

## Position Tracking

STR-005 maintains internal state for each active position:

```python
self._active_position = {
    "side": "long",           # or "short"
    "entry_price": 95.0,
    "entry_bar_index": 123,
    "entry_timestamp": datetime(...),
    "atr": 2.0,               # ATR at entry
    "mean_target": 100.0      # VWAP target
}
```

**State management:**
- Created on entry (LONG/SHORT signal)
- Checked every bar in `generate_signal()`
- Cleared on exit (any reason)
- Allows new entry after exit

---

## Configuration Examples

### Conservative (Tight Stops)
```python
strategy = MeanReversionStrategy(
    max_hold_bars=10,              # Quick exit
    stop_loss_atr_multiplier=0.75, # Tight stop
    require_range_regime=True,     # STR-004: only range
    enable_anti_knife=True         # STR-004: spike protection
)
```

### Aggressive (Wide Stops)
```python
strategy = MeanReversionStrategy(
    max_hold_bars=30,              # More patience
    stop_loss_atr_multiplier=2.0,  # Wide stop
    max_hold_minutes=120,          # 2 hours max
)
```

### Time-Based Only
```python
strategy = MeanReversionStrategy(
    max_hold_bars=50,
    max_hold_minutes=None,         # Disable minutes check
    stop_loss_atr_multiplier=3.0   # Very wide stop (emergency only)
)
```

---

## Exit Flow Diagram

```
generate_signal() called
    │
    ├─> Active position exists?
    │   │
    │   YES → Check exit conditions (priority order):
    │         ├─> Time limit exceeded? → EXIT (time_stop)
    │         ├─> Stop loss hit? → EXIT (stop_loss)
    │         └─> Take profit hit? → EXIT (take_profit)
    │
    NO → Check entry conditions (STR-004 filters + MR logic)
         └─> Entry signal? → Track position + return LONG/SHORT
```

---

## Logging & Observability

### Exit Reason Tags
All exits logged with `[STR-005]` tag and `exit_reason`:

```python
exit_reasons = [
    "time_stop",    # Time limit exceeded
    "stop_loss",    # Hard stop hit
    "take_profit"   # Mean reversion achieved
]
```

### Log Structure
```
[STR-005] MeanReversion {ACTION}: {details} | Symbol={symbol} | PnL={pnl}%

{ACTION} examples:
  - TIME_STOP: bars_held=20 >= max=20
  - STOP_LOSS: price=93.00 hit stop=93.00
  - TAKE_PROFIT: price=100.00 reached mean=100.00
```

### Detailed Signal Log
```json
{
  "stage": "GENERATED",
  "strategy": "MeanReversion",
  "symbol": "BTCUSDT",
  "direction": "CLOSE_LONG",
  "confidence": 1.0,
  "reasons": ["time_stop", "bars_held=20", "pnl=1.05%"],
  "values": {
    "exit_reason": "time_stop",
    "side": "long",
    "entry_price": 95.0,
    "exit_price": 96.0,
    "bars_held": 20,
    "pnl_pct": 1.05
  }
}
```

---

## Test Results

All 7 validation tests **PASSED** ✅:

| Test | Description | Result |
|------|-------------|--------|
| 1 | Time stop after `max_hold_bars` | ✅ Exit at bar 10 |
| 2 | Stop loss LONG (adverse move) | ✅ Exit at 93.0, PnL=-2.11% |
| 3 | Stop loss SHORT (adverse move) | ✅ Exit at 107.0, PnL=-1.90% |
| 4 | Take profit LONG (mean reversion) | ✅ Exit at 100.0, PnL=5.26% |
| 5 | Take profit SHORT (mean reversion) | ✅ Exit at 100.0, PnL=4.76% |
| 6 | No infinite holds guarantee | ✅ Time stop at bar 20 |
| 7 | Position state reset | ✅ New entry after exit |

Run tests:
```bash
python test_str005.py
```

---

## DoD Validation

### ✅ Requirement 1: No MR trade hangs forever
**Status:** PASSED

**Evidence:**
- `max_hold_bars` enforced in all tests
- Test 6 validates forced exit even when price doesn't hit stop/target
- Time stop triggers at exact bar limit (bars_held >= max_hold_bars)

**Example from logs:**
```
bars_held=20 >= max=20 → TIME_STOP triggered
```

---

### ✅ Requirement 2: Logs show exit_reason
**Status:** PASSED

**Evidence:**
All exit logs include `exit_reason` field:
```
[STR-005] MeanReversion EXIT: {TIME_STOP|STOP_LOSS|TAKE_PROFIT}
```

Structured logs include:
- `exit_reason` in values dict
- `bars_held` duration
- `pnl_pct` profit/loss
- Entry and exit prices

**Example:**
```json
"values": {
  "exit_reason": "time_stop",
  "bars_held": 20,
  "pnl_pct": 1.05,
  "entry_price": 95.0,
  "exit_price": 96.0
}
```

---

## Integration with STR-004

STR-005 works seamlessly with STR-004 (range-only mode):

```python
strategy = MeanReversionStrategy(
    # STR-004: Entry filters
    require_range_regime=True,       # Only enter in range
    enable_anti_knife=True,          # Block ADX/ATR spikes
    
    # STR-005: Exit rules
    max_hold_bars=20,                # Force exit after 20 bars
    stop_loss_atr_multiplier=1.0,    # Hard stop at 1xATR
)
```

**Flow:**
1. STR-004 filters ensure entry only in safe range conditions
2. Position tracked on entry
3. STR-005 monitors exits on every bar
4. Time stop guarantees no infinite holds

---

## Performance Metrics

### Expected Behavior

**Win Rate Impact:**
- Stop loss may reduce win rate (cuts losses early)
- Take profit should improve win rate (secures mean reversion profits)
- Time stop prevents rare "stuck" trades

**Risk Metrics:**
- Max drawdown reduced (hard stop limits losses)
- Sharpe ratio likely improved (lower tail risk)
- Average hold time capped at `max_hold_bars`

**Trade Count:**
- May increase (faster turnover from time stops)
- Avoids capital tied up in stagnant positions

### Recommended Monitoring

```python
# Track exit reason distribution
grep "exit_reason" logs/signals_*.log | cut -d'=' -f2 | sort | uniq -c

# Average hold duration
grep "\[STR-005\].*EXIT" logs/signals_*.log | grep -oP 'Bars=\K\d+' | awk '{sum+=$1; n++} END {print sum/n}'

# PnL by exit reason
grep "time_stop" logs/signals_*.log | grep -oP 'PnL=\K[-\d.]+' | awk '{sum+=$1; n++} END {print sum/n}'
```

---

## Migration Guide

### From Old MeanReversion (No Exits)

**Before:**
```python
strategy = MeanReversionStrategy(
    vwap_distance_threshold=2.0,
    rsi_oversold=30.0
)
# Positions could hang indefinitely
```

**After (STR-005):**
```python
strategy = MeanReversionStrategy(
    vwap_distance_threshold=2.0,
    rsi_oversold=30.0,
    max_hold_bars=20,              # NEW: Time limit
    stop_loss_atr_multiplier=1.0   # NEW: Hard stop
)
# All positions guaranteed to exit
```

**Breaking Changes:**
- None! STR-005 adds optional parameters with sensible defaults
- Existing code continues to work with default `max_hold_bars=20`

**Recommended Steps:**
1. Start with default parameters (`max_hold_bars=20`, `stop_loss_atr_multiplier=1.0`)
2. Monitor exit reason distribution for 1 week
3. Tune parameters based on:
   - If >80% time stops → increase `max_hold_bars`
   - If >50% stop losses → widen `stop_loss_atr_multiplier`
   - If frequent false signals → enable STR-004 (`require_range_regime=True`)

---

## Code Implementation

### Key Methods

#### `_check_exit_conditions(df, features) -> Optional[Dict]`
Called at start of `generate_signal()`. Returns exit signal if condition met.

**Checks (in order):**
1. Time limit (bars)
2. Time limit (minutes) if configured
3. Hard stop loss
4. Take profit (mean reversion)

#### `_create_exit_signal(...) -> Dict`
Creates exit signal dict and resets position tracking.

**Returns:**
```python
{
    "signal": "exit",
    "side": "long" | "short",
    "exit_reason": "time_stop" | "stop_loss" | "take_profit",
    "exit_price": 96.0,
    "bars_held": 20,
    "pnl_pct": 1.05,
    "confidence": 1.0
}
```

### Position Tracking State

```python
self._active_position: Optional[Dict[str, Any]] = None

# On entry:
self._active_position = {
    "side": "long" | "short",
    "entry_price": float,
    "entry_bar_index": int,
    "entry_timestamp": datetime | None,
    "atr": float,
    "mean_target": float  # VWAP
}

# On exit:
self._active_position = None  # Reset
```

---

## FAQ

### Q: What if price gaps through stop loss?
**A:** Stop loss checks `<=` / `>=` (not exact price). Gap will still trigger exit on next bar.

### Q: Can I disable time stops?
**A:** Set `max_hold_bars=9999` for very long limit. But **not recommended** - DoD requires time limits.

### Q: What if I want minutes instead of bars?
**A:** Set `max_hold_minutes=60`. If both set, minutes takes priority (checks first).

### Q: Does take profit use limit orders?
**A:** No, take profit is market exit when condition met. For limit orders, see STR-003 (TrendPullback).

### Q: Can I have multiple positions?
**A:** No, STR-005 tracks single position per strategy instance. For multi-symbol, use separate strategy instances.

### Q: What happens to existing positions after restart?
**A:** Position state is in-memory (`self._active_position`). On restart, state is lost. Consider persisting to disk for production.

---

## Files Modified

- ✅ `strategy/mean_reversion.py` - Exit logic, position tracking
- ✅ `test_str005.py` - 7 validation tests
- ✅ `STR005_IMPLEMENTATION.md` - This documentation

---

## Related Features

- **STR-004**: Range-only mode (entry filter)
- **STR-003**: Entry confirmation for TrendPullback
- **Future**: STR-006 could add trailing stops or dynamic exits

---

## Summary

STR-005 ensures **every Mean Reversion trade has a defined exit** via:
1. **Time stop**: Max bars/minutes (default 20 bars)
2. **Hard stop**: k * ATR from entry (default 1.0x)
3. **Take profit**: Return to VWAP

**DoD Requirements:** ✅ VALIDATED
- No infinite holds (time stop enforced)
- All exits logged with exit_reason

**Production Ready:** Yes, all tests passing, comprehensive logging in place.

---

**Implementation Date:** 2026-02-05  
**Tested:** ✅ All 7 tests passed  
**DoD Status:** ✅ COMPLETE
