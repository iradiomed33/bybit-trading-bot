## TASK-005 (P1): Config должен РЕАЛЬНО влиять на торговлю

**Problem**: Риск-параметры и параметры стратегий в bot_settings.json существуют но не используютсядействительно. Конфиг — "мёртвые настройки".

**Solution**: Синхронизировать конфиг с реальным поведением модулей.

---

## Текущее состояние ("СЛОМАНО")

### 1️⃣ Risk Management параметры ИГНОРИРУЮТСЯ
```json
{
  "risk_management": {
    "position_risk_percent": 10,      // ← IGNORED!
    "max_leverage": 10,               // ← IGNORED! (всегда 10)
    "stop_loss_percent": 5,           // ← IGNORED! (использует defaults)
    "take_profit_percent": 10         // ← IGNORED!
  }
}
```

**Where hardcoded**:
- `trading_bot.py:240` - `max_leverage=Decimal("10")` ❌
- `trading_bot.py:270` - `max_leverage=10.0` ❌  
- `trading_bot.py:344` - `risk_percent=Decimal("1.0")` ❌
- `trading_bot.py:346` - `atr_multiplier=Decimal("2.0")` ❌
- CLI `cli.py:649` - `max_leverage=10.0, risk_per_trade_percent=2.0` ❌

### 2️⃣ Strategy параметры ИГНОРИРУЮТСЯ
```json
{
  "strategies": {
    "TrendPullback": {
      "confidence_threshold": 0.35,    // ← IGNORED! (пока не используется)
      "min_candles": 15,               // ← IGNORED!
      "lookback": 20                   // ← IGNORED!
    }
  }
}
```

**Where strategies created** (WITHOUT params):
- `cli.py:1020` - `TrendPullbackStrategy()` ❌ (должно быть с params из confi)
- `cli.py:1143` - `BreakoutStrategy()` ❌
- `cli.py:1270` - `MeanReversionStrategy()` ❌

### 3️⃣ Конфиг не передается в TradingBot
```python
# trading_bot.py.__init__
def __init__(
    self,
    mode: str,
    strategies: list,
    symbol: str = "BTCUSDT",
    testnet: bool = True,
    # ❌ NO config parameter!
):
```

---

## Решение: Синхронизировать конфиг

### Архитектура  

```
bot_settings.json
    ↓
ConfigManager.load()
    ↓
TradingBot.__init__(config=config_mgr)
    ├─ PositionSizer(risk_percent=config.get("risk_management.position_risk_percent"))
    ├─ VolatilityPositionSizer(config_from_settings)
    ├─ RiskLimitsConfig(max_leverage=config.get(...))
    ├─ RiskMonitorConfig(from_config)
    └─ strategies created with params from config

cli.py / api.py
    ├─ Load config: config = ConfigManager()
    ├─ Create strategies WITH params:
    │   ├─ TrendPullbackStrategy(
    │   │    confidence_threshold=config.get(...),
    │   │    min_candles=config.get(...),
    │   │    lookback=config.get(...)
    │   ├─ BreakoutStrategy(...)
    │   └─ MeanReversionStrategy(...)
    └─ Pass to TradingBot(config=config, strategies=strategies)
```

---

## Шаги реализации

### Step 1: Модифицировать TradingBot.__init__
```python
def __init__(
    self,
    mode: str,
    strategies: list,
    symbol: str = "BTCUSDT",
    testnet: bool = True,
    config: Optional[ConfigManager] = None,  # ← NEW
):
    self.config = config or ConfigManager()  # Load default if not provided
    
    # Use config params instead of hardcoded:
    risk_config = RiskLimitsConfig(
        max_leverage=Decimal(str(
            self.config.get("risk_management.max_leverage", 10.0)
        ))
    )
```

### Step 2: Создать StrategyBuilder  
```python
class StrategyBuilder:
    def __init__(self, config: ConfigManager):
        self.config = config
    
    def build_strategies(self) -> List:
        strategies = []
        active = self.config.get("trading.active_strategies", [])
        
        if "TrendPullback" in active:
            strategies.append(TrendPullbackStrategy(
                min_adx=self.config.get("strategies.TrendPullback.min_adx"),
                pullback_percent=self.config.get("strategies.TrendPullback.pullback_percent"),
                confidence_threshold=self.config.get("strategies.TrendPullback.confidence_threshold"),
            ))
        
        # Similar for Breakout, MeanReversion
        return strategies
```

### Step 3: Update CLI commands
```python
@click.command()
def paper_command():
    config = ConfigManager()
    builder = StrategyBuilder(config)
    strategies = builder.build_strategies()
    
    bot = TradingBot(
        mode="paper",
        config=config,          # ← PASS CONFIG
        strategies=strategies,
        testnet=config.get("trading.testnet")
    )
    bot.run()
```

### Step 4: Add logging to show config impact
```python
# When risk config changes, log it:
logger.info(f"Risk Config: max_leverage={max_leverage}, position_risk={risk_percent}")

# When strategies created with params:
logger.info(f"TrendPullback: confidence={conf_thresh}, min_adx={min_adx}")
```

### Step 5: Create comprehensive tests
- Change confidence_threshold in JSON → verify bot behavior changes
- Change max_leverage in JSON → verify position sizer respects it
- Change risk_percent → verify sizing changes
- Parametrized tests checking JSON param → actual usage

---

## Files to Modify

| File | Change | Why |
|------|--------|-----|
| `config/settings.py` | Add methods to get nested values easily | Helper methods |
| `bot/trading_bot.py` | Accept ConfigManager, use params | Main entry point |
| `bot/strategy_builder.py` | NEW: Create strategies from config | Factory pattern |
| `cli.py` | Load config, use builder | Wire params |
| `api/app.py` | Load config for API endpoints | Multi-symbol support |
| `tests/test_task005_*.py` | NEW: Config impact tests | Comprehensive coverage |

---

## Реальные примеры изменений

### BEFORE (СЛОМАНО)
```python
# bot/trading_bot.py:240
risk_config = RiskLimitsConfig(
    max_leverage=Decimal("10"),  # ❌ Hardcoded
)

# cli.py:1020
strategies = [
    TrendPullbackStrategy(),  # ❌ No params
    BreakoutStrategy(),
    MeanReversionStrategy(),
]
```

### AFTER (РАБОТАЕТ)
```python
# bot/trading_bot.py:240
max_lev = self.config.get("risk_management.max_leverage", 10.0)
risk_config = RiskLimitsConfig(
    max_leverage=Decimal(str(max_lev)),  # ✓ From config
)

# cli.py (with new builder)
config = ConfigManager()
builder = StrategyBuilder(config)
strategies = builder.build_strategies()  # ✓ Creates WITH params
```

---

## Verification Checklist

- [ ] Change `confidence_threshold: 0.35 → 0.7` in JSON
  - Verify: Bot rejects more signals (stricter filtering)
  - Log: "Confidence threshold: 0.7"

- [ ] Change `max_leverage: 10 → 5` in JSON
  - Verify: Position sizing capped at 5x leverage
  - Test: VolatilityPositionSizer respects limit

- [ ] Change `position_risk_percent: 10 → 3` in JSON
  - Verify: Position size reduced by ~3x
  - Test: Position sizer scales correctly

- [ ] Change `stop_loss_percent: 5 → 10` in JSON
  - Verify: SL placed further away
  - Test: StopLossTakeProfitManager uses new value

- [ ] All 3 strategies get params from JSON
  - TrendPullback: min_adx, pullback_percent
  - Breakout: lookback, breakout_percent
  - MeanReversion: std_dev_threshold, lookback

---

## Estimated Complexity

| Component | Effort | Risk |
|-----------|--------|------|
| Modify TradingBot.__init__ | 30 min | Low |
| Create StrategyBuilder | 45 min | Low |
| Update CLI commands | 30 min | Low |
| Update VolatilityPositionSizer | 20 min | Low |
| Update RiskMonitorConfig | 20 min | Low |
| Create comprehensive tests | 60 min | Medium |
| **Total** | **3 hours** | **Low** |

---

## Success Criteria

✅ **Изменение confidence_threshold в JSON → меняется поведение бота**
✅ **Изменение max_leverage в JSON → respect in VolatilityPositionSizer**
✅ **Изменение position_risk_percent в JSON → меняется размер позиции**
✅ **Все параметры из JSON видны в логах**
✅ **Comprehensive tests покрывают все параметры**
✅ **Regression tests pass (no breaking changes)**

---

## Regression Testing

After TASK-005:
1. Run all existing tests: `pytest tests/` 
2. Verify single-symbol trading still works
3. Verify default config values work correctly
4. Verify no exceptions on missing config values (use fallbacks)

---

## Notes

- ConfigManager already handles nested keys via `get("risk_management.max_leverage")`
- All strategy classes have __init__ params already
- No breaking changes to existing API

---

**Status**: Ready to implement
