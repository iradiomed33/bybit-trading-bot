# TASK-004: MultiSymbol Per-Symbol Strategy Integration Guide

## 📌 Overview

TASK-004 решает проблему **shared state** в MultiSymbol торговле. Каждый символ теперь получает собственные (не шаренные) экземпляры стратегий.

## 🎯 Quick Start

### 1. Running Multiple Symbols

```python
from bot.multi_symbol_bot import run_multisymbol_bot
import sys

# Run trading bot for 3 symbols simultaneously
sys.exit(run_multisymbol_bot(
    symbols=["BTCUSDT", "ETHUSDT", "XRPUSDT"],
    mode="paper",  # or "live"
    testnet=True,  # Use Bybit testnet
))
```

### 2. Manual Control

```python
from bot.multi_symbol_bot import MultiSymbolBot, MultiSymbolConfig

# Configure for multiple symbols
config = MultiSymbolConfig(
    symbols=["BTCUSDT", "ETHUSDT"],
    mode="paper",
    testnet=True,
    max_concurrent=2,  # Max 2 bots running at same time
    check_interval=30,  # Health check every 30 seconds
)

# Create bot orchestrator
bot = MultiSymbolBot(config)

# Initialize (creates per-symbol strategy instances)
if not bot.initialize():
    print("Failed to initialize")
    exit(1)

# Start all bots in separate threads
if not bot.start():
    print("Failed to start")
    exit(1)

# ... bot is running ...

# Graceful shutdown
try:
    while bot.is_running:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    bot.stop()
```

## 🔧 Integration with Existing Code

### Update `cli.py` (Example)

```python
from bot.multi_symbol_bot import MultiSymbolBot, MultiSymbolConfig

@click.command()
@click.option("--symbols", multiple=True, default=["BTCUSDT"], help="Symbols to trade")
@click.option("--mode", default="paper", help="paper or live")
def multi_symbol_command(symbols, mode):
    """Run trading bot for multiple symbols"""
    
    config = MultiSymbolConfig(
        symbols=list(symbols),
        mode=mode,
        testnet=True,
    )
    
    bot = MultiSymbolBot(config)
    
    if not bot.initialize():
        click.echo("Failed to initialize MultiSymbolBot")
        return 1
    
    if not bot.start():
        click.echo("Failed to start MultiSymbolBot")
        return 1
    
    try:
        while bot.is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        bot.stop()
    
    return 0
```

Usage:
```bash
python cli.py multi-symbol --symbols BTCUSDT --symbols ETHUSDT --symbols XRPUSDT --mode paper
```

### Update `api/app.py` (Example)

```python
from bot.multi_symbol_bot import MultiSymbolBot, MultiSymbolConfig
from fastapi import FastAPI, HTTPException
import asyncio

app = FastAPI()
multisymbol_bot = None

@app.post("/api/multisymbol/start")
async def start_multisymbol_bot(symbols: list[str], mode: str = "paper"):
    """Start MultiSymbol trading bot"""
    global multisymbol_bot
    
    if multisymbol_bot and multisymbol_bot.is_running:
        raise HTTPException(status_code=400, detail="Bot already running")
    
    config = MultiSymbolConfig(symbols=symbols, mode=mode, testnet=True)
    multisymbol_bot = MultiSymbolBot(config)
    
    if not multisymbol_bot.initialize():
        raise HTTPException(status_code=500, detail="Failed to initialize bot")
    
    if not multisymbol_bot.start():
        raise HTTPException(status_code=500, detail="Failed to start bot")
    
    return {"status": "started", "symbols": symbols}

@app.get("/api/multisymbol/status")
async def get_multisymbol_status():
    """Get status of all running bots"""
    if not multisymbol_bot:
        raise HTTPException(status_code=404, detail="Bot not initialized")
    
    return multisymbol_bot.get_report()

@app.post("/api/multisymbol/stop")
async def stop_multisymbol_bot():
    """Stop MultiSymbol trading bot"""
    global multisymbol_bot
    
    if not multisymbol_bot:
        raise HTTPException(status_code=404, detail="Bot not initialized")
    
    multisymbol_bot.stop()
    return {"status": "stopped"}
```

## 🏗️ How It Works

### Architecture Diagram

```
┌─────────────────────────────────────────┐
│      MultiSymbolBot (Main Orchestrator) │
└────────────┬────────────────────────────┘
             │
    ┌────────┼────────┬─────────┐
    │        │        │         │
    ▼        ▼        ▼         ▼
┌───────┐ ┌───────┐ ┌─────┐  ┌─────┐
│ Bot-1 │ │ Bot-2 │ │Bot-3│  │Healt│
│(BTCUSDT)│(ETHUSDT)│(XRP) │ │Check│
└───┬───┘ └───┬───┘ └──┬──┘  └─────┘
    │         │       │
    ▼         ▼       ▼
  Strat-1   Strat-4  Strat-7     ← NEW instances for each symbol!
  Strat-2   Strat-5  Strat-8
  Strat-3   Strat-6  Strat-9
  (unique)  (unique) (unique)
```

### Per-Symbol Strategy Creation

Each time `initialize()` is called for a symbol:

```python
# Inside MultiSymbolBot.initialize():
for symbol in self.config.symbols:
    # IMPORTANT: Create NEW instances for each symbol
    strategies = StrategyFactory.create_strategies()
    
    # Pass to TradingBot
    bot = TradingBot(symbol=symbol, strategies=strategies)
```

**Verification**:
```python
btc_strats = StrategyFactory.create_strategies()
eth_strats = StrategyFactory.create_strategies()

# These are DIFFERENT objects:
assert id(btc_strats[0]) != id(eth_strats[0])  # ✓ True
assert StrategyFactory.verify_per_symbol_instances(btc_strats, eth_strats)  # ✓ True
```

## 💡 Key Benefits

1. **No State Sharing**: Each symbol has isolated strategy state
2. **Thread Safe**: Safe concurrent creation and execution
3. **Scalable**: Works with 1, 3, 10+ symbols
4. **Debuggable**: Can log strategy IDs to verify isolation
5. **Backward Compatible**: Existing single-symbol code still works

## 🧪 Testing

### Run TASK-004 Tests

```bash
# All tests
pytest tests/test_task004_per_symbol_strategies.py -v

# Specific test class
pytest tests/test_task004_per_symbol_strategies.py::TestStrategyFactory -v

# With coverage
pytest tests/test_task004_per_symbol_strategies.py --cov=bot --cov-report=html
```

### Quick Verification

```python
from bot.strategy_factory import StrategyFactory

# Create 5 symbols worth of strategies
all_strategies = []
for i in range(5):
    strats = StrategyFactory.create_strategies()
    all_strategies.append(strats)
    print(f"Symbol {i}: {StrategyFactory.get_strategy_ids(strats)}")

# Verify all are unique
assert StrategyFactory.verify_per_symbol_instances(*all_strategies)
print("✓ All 5 symbols have unique strategies!")
```

## 📊 Monitoring & Logging

### Health Check Output

```python
bot = MultiSymbolBot(config)
bot.initialize()
bot.start()

# ... running ...

# Get status report
report = bot.get_report()
print(report)

# Output:
# {
#   "timestamp": "2024-01-15T10:30:45.123456",
#   "is_running": True,
#   "symbols": {
#     "BTCUSDT": {
#       "is_running": True,
#       "error_count": 0,
#       "errors": []
#     },
#     "ETHUSDT": {
#       "is_running": True,
#       "error_count": 0,
#       "errors": []
#     }
#   }
# }
```

### Strategy ID Logging

```python
from bot.strategy_factory import StrategyFactory

strats = StrategyFactory.create_strategies()
ids = StrategyFactory.get_strategy_ids(strats)

logger.info(f"Creating strategies for BTCUSDT: {ids}")
# Log output:
# [INFO] Creating strategies for BTCUSDT: [140247349, 140247356, 140247363]
```

## 🚀 Production Deployment

### Single Symbol (Original Behavior)

Still works exactly the same:

```python
from bot.trading_bot import TradingBot
from strategy.trend_pullback import TrendPullbackStrategy
from strategy.breakout import BreakoutStrategy
from strategy.mean_reversion import MeanReversionStrategy

strategies = [
    TrendPullbackStrategy(),
    BreakoutStrategy(),
    MeanReversionStrategy(),
]

bot = TradingBot(symbol="BTCUSDT", strategies=strategies, mode="paper")
bot.run()
```

### Multiple Symbols (TASK-004 Recommended)

Use MultiSymbolBot for better isolation:

```python
from bot.multi_symbol_bot import MultiSymbolBot, MultiSymbolConfig

config = MultiSymbolConfig(
    symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
    mode="paper",
    testnet=False,  # Use live testnet
    max_concurrent=3,
)

bot = MultiSymbolBot(config)
bot.initialize()
bot.start()
```

## ⚠️ Important Notes

1. **Instance Count**: Each call to `StrategyFactory.create_strategies()` creates **3 NEW objects** (one for each strategy class)
2. **Uniqueness Guarantee**: Verified through Python's `id()` function (memory address)
3. **Thread Safety**: Safe for concurrent use (built-in locking in factory)
4. **Memory**: Multiple instances means multiple indicator states (necessary for isolation)

## 🔍 Troubleshooting

### "Database is locked" errors
Solution: Ensure `PRAGMA busy_timeout=5000` is set in SQLite (handled by `storage/database.py`)

### Strategies not isolated
Verify with:
```python
from bot.strategy_factory import StrategyFactory

strats1 = StrategyFactory.create_strategies()
strats2 = StrategyFactory.create_strategies()

for s1, s2 in zip(strats1, strats2):
    assert id(s1) != id(s2), "Strategies should be different objects!"
print("✓ Strategies are properly isolated")
```

### Bot not starting
Check logs for:
- Missing strategy classes (ensure `strategy/` folder exists)
- Invalid symbol configuration
- Port/connection issues

## 📚 Related Documentation

- [TASK003_COMPLETION.md](TASK003_COMPLETION.md) - SQLite thread safety (prerequisite)
- [TASK004_COMPLETION.md](TASK004_COMPLETION.md) - Full technical details
- [bot/strategy_factory.py](bot/strategy_factory.py) - Factory implementation
- [bot/multi_symbol_bot.py](bot/multi_symbol_bot.py) - MultiSymbol orchestrator

## ✅ Checklist for Integration

- [ ] Review `bot/strategy_factory.py`
- [ ] Review `bot/multi_symbol_bot.py`
- [ ] Run `tests/test_task004_per_symbol_strategies.py`
- [ ] Verify per-symbol strategy isolation works
- [ ] Update `cli.py` to support multiple symbols (optional)
- [ ] Update `api/app.py` with MultiSymbol endpoints (optional)
- [ ] Test with 3+ symbols simultaneously
- [ ] Verify database performance under multi-symbol load
- [ ] Deploy to testnet
- [ ] Monitor for shared state issues

## 🎓 Learning Resources

### Factory Pattern
- This uses the **Factory Pattern** to create objects
- Each call produces new instances with fresh state
- Prevents the "Singleton Gone Wrong" anti-pattern

### Object Identity vs Equality
- `id(obj)` returns memory address (unique per object)
- `obj1 == obj2` checks value equality
- `obj1 is obj2` checks object identity (uses `id()`)
- TASK-004 uses `id()` for strong isolation guarantee

### Thread Safety
- Python GIL makes some operations atomic
- Multiple threads safe for creating/reading objects
- Avoid shared mutable state between threads

---

**TASK-004 Status**: ✅ COMPLETE AND READY FOR PRODUCTION
