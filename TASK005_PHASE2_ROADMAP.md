# TASK-005 Phase 2: Implementation Roadmap

**Goal**: Wire risk_management parameters from config to TradingBot and CLI

**Timeline**: 2-3 hours  
**Complexity**: Low (just parameter passing)  
**Risk**: Very Low (all additive, no breaking changes)

---

## Phase 2 Checklist

### Step 1: Understand Current Risk Parameters
**File**: `bot/trading_bot.py`  
**Task**: Find all hardcoded risk values

```python
# Lines to find:
line 240:  max_leverage = 10              # ← Hardcoded!
line 270:  risk_percent = 1.0             # ← Hardcoded!
line 344:  atr_multiplier = 2.0           # ← Hardcoded!
```

**Deliverable**: Document all hardcoded risk params and their current values

---

### Step 2: Add config Parameter to TradingBot
**File**: `bot/trading_bot.py`  
**Lines**: `__init__` method (around line 100-150)

**Change**:
```python
# Before
def __init__(self, symbol, strategies, mode="paper", ...):
    pass

# After
def __init__(self, symbol, strategies, mode="paper", config=None, ...):
    self.config = config or ConfigManager()
    self.max_leverage = self.config.get("risk_management.max_leverage", 10)
    self.risk_percent = self.config.get("risk_management.position_risk_percent", 1.0)
    self.atr_multiplier = self.config.get("risk_management.atr_multiplier", 2.0)
```

**Validation**: Add logging
```python
logger.info(f"[TradingBot Risk Config] max_leverage={self.max_leverage}, risk_percent={self.risk_percent}")
```

---

### Step 3: Wire Risk Params to PositionSizer
**File**: `bot/trading_bot.py`  
**Find**: Where PositionSizer is created (search for `PositionSizer(`)

**Change**:
```python
# Before
sizer = PositionSizer(risk_percent=1.0, leverage=10)

# After
sizer = PositionSizer(
    risk_percent=self.config.get("risk_management.position_risk_percent", 1.0),
    leverage=self.config.get("risk_management.max_leverage", 10)
)
```

---

### Step 4: Wire Risk Params to VolatilityPositionSizer
**File**: `bot/trading_bot.py`  
**Find**: Where VolatilityPositionSizer is created

**Change**:
```python
# Before
vol_sizer = VolatilityPositionSizer(atr_multiplier=2.0)

# After
vol_sizer = VolatilityPositionSizer(
    atr_multiplier=self.config.get("risk_management.atr_multiplier", 2.0)
)
```

---

### Step 5: Wire Risk Params to RiskLimitsConfig
**File**: `bot/trading_bot.py`  
**Find**: Where RiskLimitsConfig is created

**Change**:
```python
# Before
risk_limits = RiskLimitsConfig(max_leverage=10, ...)

# After
risk_limits = RiskLimitsConfig(
    max_leverage=self.config.get("risk_management.max_leverage", 10),
    max_position_size=self.config.get("risk_management.max_position_size", 100000),
    # ... other risk params
)
```

---

### Step 6: Update CLI Commands (paper_command)
**File**: `cli.py`  
**Lines**: ~1020 (paper_command function)

**Change**:
```python
# Before
def paper_command(...):
    strategies = [
        TrendPullbackStrategy(),
        BreakoutStrategy(),
    ]
    bot = TradingBot(mode="paper", strategies=strategies)

# After
from config.settings import ConfigManager
from bot.strategy_builder import StrategyBuilder

def paper_command(...):
    config = ConfigManager()
    builder = StrategyBuilder(config)
    strategies = builder.build_strategies()  # ← From config!
    
    bot = TradingBot(
        mode="paper",
        strategies=strategies,
        config=config  # ← Pass config for risk params!
    )
```

---

### Step 7: Update CLI Commands (live_command)
**File**: `cli.py`  
**Lines**: ~1143 (live_command function)

**Identical change as Step 6** (but mode="live")

---

### Step 8: Update CLI Commands (backtest_command)
**File**: `cli.py`  
**Lines**: ~1270 (backtest_command function)

**Identical change as Step 6** (but mode="backtest")

---

### Step 9: Update MultiSymbolBot Integration
**File**: `bot/multi_symbol_bot.py`  
**Lines**: ~initialize() method

**Optional Enhancement**:
```python
# Current (TASK-004):
strategies = StrategyFactory.create_strategies()

# Enhanced (TASK-005 P2):
config = ConfigManager()
builder = StrategyBuilder(config)
strategies = builder.build_strategies()

# Even better: pass config to each bot
for symbol in self.config.symbols:
    strategies = builder.build_strategies()
    bot = TradingBot(symbol=symbol, strategies=strategies, config=config)
```

---

## Testing Strategy

### Unit Tests
```bash
# Create test_task005_phase2.py
pytest tests/test_task005_phase2.py -v
```

**Test cases**:
- [ ] TradingBot accepts config parameter
- [ ] max_leverage read from config
- [ ] position_risk_percent read from config
- [ ] atr_multiplier read from config
- [ ] PositionSizer receives correct leverage
- [ ] VolatilityPositionSizer receives correct atr_multiplier
- [ ] RiskLimitsConfig receives all params
- [ ] Defaults used when config missing

### Integration Tests
```bash
# Run existing regression tests
pytest tests/ -k "not e2e" -v
```

**Verify**:
- [ ] All existing tests still pass
- [ ] No breaking changes to TradingBot
- [ ] CLI commands still work
- [ ] Config params logged correctly

### Smoke Tests
```bash
python -c "
from cli import paper_command
from click.testing import CliRunner

runner = CliRunner()
result = runner.invoke(paper_command, ['--mode', 'paper'])
assert result.exit_code == 0
print('✓ CLI integration works')
"
```

---

## Success Criteria

**After Phase 2 is complete**:

- [x] bot_settings.json drives STRATEGY behavior (Phase 1) ✅
- [ ] bot_settings.json drives RISK behavior (Phase 2) ⏳
- [ ] All risk params readable from config
- [ ] All risk params logged when used
- [ ] CLI commands use StrategyBuilder + config
- [ ] No regression in existing tests
- [ ] Config params actually change position sizing (testable)

---

## Files to Modify

| File | Lines | Change | Effort |
|------|-------|--------|--------|
| `bot/trading_bot.py` | ~100-150 | Add config param + wire params | 45 min |
| `bot/trading_bot.py` | ~240, 270, 344 | Replace hardcoded with config.get() | 15 min |
| `cli.py` | 1020 | Add StrategyBuilder to paper_command | 15 min |
| `cli.py` | 1143 | Add StrategyBuilder to live_command | 10 min |
| `cli.py` | 1270 | Add StrategyBuilder to backtest_command | 10 min |
| `tests/test_task005_phase2.py` | New file | Test phase 2 integration | 45 min |

**Total**: ~2.5 hours

---

## Risk Assessment

- **Low Risk** ✅: All changes are additive
- **No Breaking Changes** ✅: Existing code paths unchanged
- **Backward Compatible** ✅: Default values provided everywhere
- **Easy to Revert** ✅: Just remove config param additions

---

## Phase 2 Completion Checklist

- [ ] TradingBot modified to accept config
- [ ] Risk params wired from config to all risk modules
- [ ] CLI commands use StrategyBuilder
- [ ] All risk params logged at startup
- [ ] Unit tests passing (new + existing)
- [ ] Integration tests passing
- [ ] docs/TASK005_PHASE2_COMPLETION.md created
- [ ] Smoke test validates config impact
- [ ] Ready for multi-symbol testing

---

## After Phase 2: Full TASK-005 Achievement

✅ **Strategy Parameters**: Read from config, passed to strategy constructors  
✅ **Risk Parameters**: Read from config, passed to risk modules  
✅ **CLI Integration**: Commands use StrategyBuilder and config  
✅ **Logging**: All params logged for auditability  
✅ **Testing**: 40+ tests covering all config→behavior mappings  
✅ **Multi-Symbol Ready**: Works with TASK-004 MultiSymbolBot  

**Result**: bot_settings.json FULLY drives bot behavior! 🎯

---

## Quick Links
- [TASK005_PLAN.md](TASK005_PLAN.md) - Full requirements
- [TASK005_PROGRESS.md](TASK005_PROGRESS.md) - Phase 1 progress
- [bot/strategy_builder.py](bot/strategy_builder.py) - Phase 1 implementation
- [tests/test_task005_config_impact.py](tests/test_task005_config_impact.py) - Phase 1 tests
