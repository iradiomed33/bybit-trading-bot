#!/usr/bin/env python3
"""Revert incorrect F841 fixes (variables that are actually used)"""

import re
from pathlib import Path

# List of known F841 errors from flake8 that should NOT have been "fixed"
# These are real variables used later, not actually unused
REAL_USAGE = {
    'execution/backtest_runner.py': ['open_price', 'qty', 'take_profit', 'stop_loss'],
    'execution/paper_trading_simulator.py': ['entry_qty', 'entry_price'],
    'execution/position_state_manager.py': ['old_qty', 'old_cost'],
    'execution/stop_loss_tp_manager.py': ['old_qty'],
    'strategy/meta_layer.py': ['depth_imbalance'],
    'tests/test_kill_switch.py': ['result'],
    'tests/test_paper_trading_simulator.py': ['expected_price', 'initial_equity', 'cash_after_buy', 'equity_with_profit'],
    'tests/test_rsi.py': ['rsi'],
    'tests/test_signal_rejection_logging.py': ['signal'],
    'tests/test_slippage_model.py': ['gross_pnl'],
    'tests/test_strategy_filters.py': ['strategy', 'atr_percent_ma'],
    'tests/test_volatility_position_sizer.py': ['target_risk_usd'],
    'tests/test_exe002_position_state.py': ['local_qty', 'local_avg'],
    'tests/test_backtest_runner.py': ['json_str'],
    'tests/test_paper_trading_simulator.py': ['expected_price'],
}

def revert_variable(filepath, var_name):
    """Remove underscore prefix from variable if it was added"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original = content

        # Replace _var = with var = (at line start with indent)
        pattern = rf'^(\s+)_{var_name}(\s*=)'
        replacement = rf'\1{var_name}\2'
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ {filepath}: Reverted _{var_name}")
            return True
    except Exception as e:
        print(f"✗ {filepath}: Error reverting {var_name}: {e}")

    return False

# Main
print("Reverting incorrect F841 fixes...\n")

total_reverted = 0

for filepath_rel, variables in REAL_USAGE.items():
    filepath = Path(filepath_rel)
    if not filepath.exists():
        print(f"✗ {filepath_rel}: File not found")
        continue

    for var_name in variables:
        if revert_variable(filepath, var_name):
            total_reverted += 1

print(f"\n✓ Total variables reverted: {total_reverted}")
print("Done!")
