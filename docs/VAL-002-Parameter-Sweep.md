# VAL-002: Parameter Sweep with Stability Analysis

**Status**: ✅ Production Ready | **Tests**: 20/20 passing | **Integration**: ✅ With VAL-001

---

## Overview

VAL-002 prevents overfitting through robust parameter selection by:
- Performing grid search across parameter ranges
- Analyzing stability between train/test periods
- Identifying **range of stable parameters**, not just single "best"
- Detecting **overfitting warning signs** automatically

**Core Principle**: "Don't trust single best" — stable parameters across periods are more likely to work on live data.

---

## Architecture

### Parameter Space Definition

```python
# Define ranges for parameters
config = ParameterConfig()
config.add_parameter(ParameterRange(
    name="atr_period",
    param_type=ParameterType.INTEGER,
    min_value=10,
    max_value=50,
    step=5,  # 10, 15, 20, 25, 30, 35, 40, 45, 50 = 9 values
))

# Total combinations = product of all ranges
# 6 params × average 5 values each = ~15,625 combinations
```

### Grid Search Workflow

```
Parameter Ranges
     ↓
Generate All Combinations (Cartesian product)
     ↓
For Each Combination:
  ├─ Create Strategy with params
  ├─ Run on TRAIN data → train_metrics
  ├─ Run on TEST data  → test_metrics
  ├─ Calculate Stability Score
  └─ Store ParameterResult
     ↓
Sort by Stability Score
     ↓
Select Top 10 Stable Combinations
     ↓
ParameterReport with recommendations
```

### Stability Analysis

```
Train Metrics vs Test Metrics
     ↓
Calculate Degradation:
  • PnL degradation % = (test_pnl - train_pnl) / train_pnl * 100
  • Win rate change % = test_wr - train_wr
  • Profit factor change % = (test_pf - train_pf) / train_pf * 100
  • Drawdown increase % = test_dd - train_dd
  • Trade ratio = test_trades / train_trades
     ↓
Detect Overfitting Signals:
  • PnL degradation > 30% → Warning
  • Win rate drop > 20% → Warning
  • PF drop > 30% → Warning
  • DD increase > 10% → Warning
  • Fewer trades on test → Warning
     ↓
Calculate Stability Score (0-100):
  score = 100
  score -= |pnl_degradation| × 0.3
  score -= max(0, -win_rate_change) × 0.2
  score -= max(0, -pf_change) × 0.2
  score -= dd_increase × 0.1
  score -= |expectancy_consistency - 1| × 20
  score = clamp(score, 0, 100)
```

---

## Key Components

### 1. ParameterRange

Defines single parameter's range:

```python
param = ParameterRange(
    name="atr_period",
    param_type=ParameterType.INTEGER,  # INTEGER, FLOAT, DECIMAL
    min_value=10,
    max_value=50,
    step=5,
    description="ATR lookback period",
)

values = param.generate_values()  # [10, 15, 20, 25, 30, 35, 40, 45, 50]
```

### 2. ParameterConfig

Configures all parameters for sweep:

```python
config = ParameterConfig.default_circuitbreaker_config()
# Includes: atr_period, volatility_multiplier, loss_threshold_percent, etc.

config.add_parameter(custom_param)
total = config.get_total_combinations()  # Total parameter combinations
```

### 3. StabilityMetrics

Analyzes train vs test degradation:

```python
stability = StabilityMetrics(
    pnl_degradation_pct=-15.0,      # -15% PnL degradation
    win_rate_change_pct=-5.0,        # -5% win rate drop
    pf_change_pct=-10.0,             # -10% profit factor drop
    dd_increase_pct=2.0,             # +2% drawdown increase
    expectancy_consistency=0.95,     # test_exp / train_exp
    trades_ratio=0.85,               # test_trades / train_trades
)

score = stability.calculate_score()  # 0-100, higher is more stable
```

### 4. ParameterSweep

Executes grid search:

```python
sweep = ParameterSweep(
    strategy_func=my_strategy_factory,
    strategy_name="MyStrategy",
    parameter_config=config,
)

report = sweep.run_sweep(
    df=ohlcv_data,
    validation_engine=engine,
    test_size_percent=30,
)
```

### 5. ParameterReport

Contains sweep results:

```python
report.get_top_stable(n=10)  # Top 10 stable parameter sets

min_score, max_score = report.get_stability_range()

json_output = report.export_json()  # Export for analysis
```

---

## Stability Score Calculation

$$\text{Score} = 100 - \text{penalties}$$

| Factor | Penalty Multiplier | Impact |
|--------|-------------------|--------|
| PnL degradation | 0.3 | Large penalties for performance loss |
| Win rate drop | 0.2 | Moderate penalty for fewer wins |
| Profit factor drop | 0.2 | Moderate penalty for efficiency loss |
| Drawdown increase | 0.1 | Small penalty for risk increase |
| Expectancy inconsistency | 20.0 | Large penalty for inconsistent avg trade |

**Interpretation**:
- **Score > 80**: Excellent stability, recommend for live
- **Score 60-80**: Good stability, acceptable variance
- **Score 40-60**: Moderate stability, monitor on forward test
- **Score < 40**: Poor stability, likely overfitted

---

## Overfitting Detection

Automatic warnings for:

1. **PnL Degradation > 30%**
   - Test period loses >30% of train profit
   - Sign: Parameters tuned to specific market regime

2. **Win Rate Drop > 20%**
   - Test win rate 20% lower than train
   - Sign: Signals too specific, don't generalize

3. **Profit Factor Drop > 30%**
   - Test PF significantly lower
   - Sign: Risk/reward ratios change on new data

4. **Drawdown Increase > 10%**
   - Test max drawdown 10% higher
   - Sign: Risk management parameters too optimistic

5. **Fewer Test Trades (Ratio < 0.8)**
   - 20% fewer trades on test data
   - Sign: Signals too strict, missing opportunities

---

## Usage Patterns

### Pattern 1: Basic Grid Search

```python
from validation.parameter_sweep import ParameterConfig, ParameterSweep

# Define ranges
config = ParameterConfig()
config.add_parameter(ParameterRange(
    name="ma_period",
    param_type=ParameterType.INTEGER,
    min_value=10,
    max_value=30,
    step=5,
))

# Run sweep
sweep = ParameterSweep(
    strategy_func=my_strategy,
    parameter_config=config,
)

report = sweep.run_sweep(df, engine, test_size_percent=30)

# Get top stable
for result in report.get_top_stable(n=10):
    print(f"Params: {result.param_set.to_dict()}")
    print(f"Stability: {result.stability_score}")
```

### Pattern 2: Identify Robust Range

```python
# Find parameters that work across conditions
stable_params = [
    r for r in report.results 
    if r.stability_score > Decimal("70")
]

# Extract parameter values
ma_periods = [
    r.param_set.to_dict()["ma_period"] 
    for r in stable_params
]

robust_range = (min(ma_periods), max(ma_periods))
print(f"Robust MA range: {robust_range}")
```

### Pattern 3: Sensitivity Analysis

```python
# Group results by parameter
by_param = {}
for result in report.results:
    param_val = result.param_set.to_dict()["threshold"]
    if param_val not in by_param:
        by_param[param_val] = []
    by_param[param_val].append(result.stability_score)

# Identify "sweet spot"
for param_val in sorted(by_param.keys()):
    avg_score = sum(by_param[param_val]) / len(by_param[param_val])
    print(f"Threshold {param_val}: Avg Stability = {avg_score:.1f}")
```

### Pattern 4: Forward Testing Selection

```python
# Select top stable config for forward test
best = report.get_top_stable(n=1)[0]

# Run on forward data
forward_metrics = engine.validate_on_data(
    forward_df,
    period_type="forward",
)

# Compare with train/test from sweep
if forward_metrics.profit_factor > best.test_metrics.profit_factor:
    print("Forward performance better than expected!")
```

---

## Default CircuitBreaker Parameters

VAL-002 includes ready-to-use CircuitBreaker parameter ranges:

```python
config = ParameterConfig.default_circuitbreaker_config()

# Defines:
# • atr_period: 10-50 (step 5) = 9 values
# • volatility_multiplier: 1.5-3.0 (step 0.25) = 7 values  
# • volatility_threshold_percent: 2.0-5.0 (step 0.5) = 7 values
# • loss_threshold_percent: 2.0-5.0 (step 0.5) = 7 values
# • loss_window_candles: 20-100 (step 20) = 5 values
# • cooldown_minutes: 5-30 (step 5) = 6 values
#
# Total combinations: 9×7×7×7×5×6 = 126,126 combinations
```

---

## Performance Considerations

| Factor | Impact | Mitigation |
|--------|--------|-----------|
| Large parameter space | Exponential combinations | Reduce ranges or steps |
| Many parameters | Slow sweep | Use coarser steps, run in parallel |
| Many candles | Per-combination overhead | Use fewer test candles first |
| Strategy complexity | Evaluation time | Optimize strategy code |

**Typical Times**:
- 100 combinations: ~10-30 seconds
- 1,000 combinations: ~2-5 minutes
- 10,000 combinations: ~20-50 minutes

---

## Test Coverage

**20 Unit Tests** covering:

- ✅ ParameterRange generation (integer, float)
- ✅ ParameterConfig creation and combinations
- ✅ ParameterSet creation and hashing
- ✅ StabilityMetrics calculation
- ✅ Perfect stability (0% degradation)
- ✅ Mild degradation detection
- ✅ Severe overfitting detection
- ✅ Overfitting signal generation
- ✅ ParameterResult creation
- ✅ ParameterReport management
- ✅ Top-stable parameter selection
- ✅ Stability range calculation
- ✅ ParameterSweep initialization
- ✅ Parameter set generation
- ✅ Stability analysis (good performance)
- ✅ Stability analysis (overfitting)

---

## Integration with VAL-001

```python
from validation.validation_engine import ValidationEngine
from validation.parameter_sweep import ParameterSweep

# VAL-001: Single parameter validation
engine = ValidationEngine(strategy, "Strategy")
metrics = engine.validate_on_data(df, "test")

# VAL-002: Multi-parameter stability
sweep = ParameterSweep(strategy_factory, "Strategy", config)
report = sweep.run_sweep(df, engine, test_size_percent=30)

# Combines:
# • UnifiedPipeline (VAL-001) ensures same logic
# • ParameterSweep (VAL-002) finds robust ranges
# → Maximize robustness, minimize overfitting risk
```

---

## Common Pitfalls

| Issue | Cause | Solution |
|-------|-------|----------|
| Too many combinations | Coarse parameter steps | Reduce ranges or use fewer parameters |
| All configs have low score | Strategy fundamentally unstable | Review strategy logic, not parameters |
| Single peak, no plateau | Overfitting to test data | Increase test period size, add validation |
| Top-10 all very similar | Parameter space too narrow | Expand ranges |
| Long sweep time | Large combination count | Use coarser steps or parallel processing |

---

## Workflow: From Strategy to Live

```
1. Strategy Development
   └─ Define core logic

2. Single-Period Test (VAL-001)
   └─ Validate on train + test
   └─ Check metrics are reasonable

3. Parameter Sweep (VAL-002)
   └─ Grid search ranges
   └─ Identify stable parameters
   └─ Get top-10 recommendations

4. Forward Testing
   └─ Run top-3 configs on new data
   └─ Compare with train/test baseline

5. Live Deployment
   └─ Deploy best forward performer
   └─ Monitor vs backtest expectations
   └─ Use VAL-001 for ongoing validation
```

---

## References

- **Implementation**: [validation/parameter_sweep.py](../validation/parameter_sweep.py)
- **Tests**: [tests/test_parameter_sweep.py](../tests/test_parameter_sweep.py)
- **Example**: [examples/parameter_sweep_demo.py](../examples/parameter_sweep_demo.py)
- **VAL-001**: [docs/VAL-001-Unified-Validation.md](VAL-001-Unified-Validation.md)

---

**Last Updated**: 2024-Q1 | **Version**: 1.0 (Production)
