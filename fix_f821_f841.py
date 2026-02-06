#!/usr/bin/env python3
"""
Fix F821/F841 errors caused by aggressive _var renaming.
Pattern: Find cases where _var is assigned but var is used (undefined).
Solution: Remove underscore prefix from the assignment.
"""

import os
import re
from pathlib import Path

# List of known corrupted files and their specific fixes
FIXES = {
    'validate_str001.py': [
        (r'(\s+)_signal_passed = ', r'\1signal_passed = '),
        (r'(\s+)_details_passed = ', r'\1details_passed = '),
        (r'(\s+)_all_passed = ', r'\1all_passed = '),
    ],
    'backtest/engine.py': [
        (r'(\s+)_fill_price = ', r'\1fill_price = '),
        (r'(\s+)_exit_reason = ', r'\1exit_reason = '),
        (r'(\s+)_should_exit = ', r'\1should_exit = '),
    ],
    'api/app.py': [
        (r'(\s+)_token = ', r'\1token = '),
    ],
    'bot/trading_bot.py': [
        (r'(\s+)_orderbook = ', r'\1orderbook = '),
        (r'(\s+)_qty = ', r'\1qty = '),
        (r'(\s+)_sl_tp_levels = ', r'\1sl_tp_levels = '),
    ],
    'cli.py': [
        (r'(\s+)_orderbook = ', r'\1orderbook = '),
    ],
    'data/features.py': [
        (r'(\s+)body = ', r'\1body = '),  # Already used, just verify
    ],
    'data/indicators.py': [
        # USE_PANDAS_TA is undefined, needs import check
    ],
    'data/indicators_new.py': [
        # USE_PANDAS_TA is undefined, needs import check
    ],
    'data/timeframe_cache.py': [
        (r'(\s+)_trend_5m = ', r'\1trend_5m = '),
        (r'(\s+)_vol_regime = ', r'\1vol_regime = '),
        (r'(\s+)_atr_percent = ', r'\1atr_percent = '),
    ],
    'backtest/diagnostics.py': [
        (r'(\s+)_rate = ', r'\1rate = '),
    ],
    'execution/backtest_runner.py': [
        (r'(\s+)_trades_count = ', r'\1trades_count = '),
    ],
    'execution/kill_switch.py': [
        (r'(\s+)_cancelled_count = ', r'\1cancelled_count = '),
        (r'(\s+)_closed_count = ', r'\1closed_count = '),
    ],
    'execution/paper_trading_simulator.py': [
        (r'(\s+)_slippage = ', r'\1slippage = '),
    ],
    'execution/position_manager.py': [
        (r'(\s+)_new_stop = ', r'\1new_stop = '),
    ],
    'execution/position_state_manager.py': [
        (r'(\s+)_order = ', r'\1order = '),
    ],
    'execution/stop_loss_tp_manager.py': [
        (r'(\s+)_sl_distance = ', r'\1sl_distance = '),
        (r'(\s+)_tp_distance = ', r'\1tp_distance = '),
        (r'(\s+)_sl_order_id = ', r'\1sl_order_id = '),
        (r'(\s+)_tp_order_id = ', r'\1tp_order_id = '),
    ],
    'execution/trade_metrics.py': [
        (r'(\s+)_peak = ', r'\1peak = '),
        (r'(\s+)_max_dd = ', r'\1max_dd = '),
    ],
    'risk/limits.py': [
        (r'(\s+)_total_exposure = ', r'\1total_exposure = '),
    ],
    'risk/volatility_position_sizer.py': [
        (r'(\s+)_position_qty_constrained = ', r'\1position_qty_constrained = '),
        (r'(\s+)_constraint_applied = ', r'\1constraint_applied = '),
    ],
    'storage/position_state.py': [
        (r'(\s+)_exchange_position = ', r'\1exchange_position = '),
    ],
    'storage/state_recovery.py': [
        (r'(\s+)_liq_price = ', r'\1liq_price = '),
    ],
    'strategy/breakout.py': [
        (r'(\s+)_bb_width_pctl = ', r'\1bb_width_pctl = '),
        (r'(\s+)_atr_pctl = ', r'\1atr_pctl = '),
        (r'(\s+)_bb_expansion = ', r'\1bb_expansion = '),
        (r'(\s+)_atr_expansion = ', r'\1atr_expansion = '),
        (r'(\s+)_volume_pctl = ', r'\1volume_pctl = '),
        (r'(\s+)_volume_ratio = ', r'\1volume_ratio = '),
        (r'(\s+)_squeeze_ok = ', r'\1squeeze_ok = '),
        (r'(\s+)_expansion_ok = ', r'\1expansion_ok = '),
        (r'(\s+)_volume_ok = ', r'\1volume_ok = '),
    ],
    'strategy/meta_layer.py': [
        # depth_imbalance is assigned but never used (line 410) - remove assignment
    ],
    'strategy/mean_reversion.py': [
        (r'(\s+)_take_profit = ', r'\1take_profit = '),
    ],
    'validation/validation_engine.py': [
        (r'(\s+)_peak_cumulative = ', r'\1peak_cumulative = '),
        (r'(\s+)_max_dd = ', r'\1max_dd = '),
    ],
    'tests/test_rsi.py': [
        (r'(\s+)_df = ', r'\1df = '),
    ],
    'tests/test_signal_rejection_logging.py': [
        # undefined 'l' - likely loop variable corruption
    ],
    'tests/test_slippage_integration.py': [
        (r'(\s+)_base_price = ', r'\1base_price = '),
    ],
    'test_e2_integration.py': [
        (r'(\s+)_passed = ', r'\1passed = '),
        (r'(\s+)_failed = ', r'\1failed = '),
    ],
    'test_str003.py': [
        (r'(\s+)_all_passed = ', r'\1all_passed = '),
    ],
    'test_str004.py': [
        (r'(\s+)_adx_spike = ', r'\1adx_spike = '),
        (r'(\s+)_all_passed = ', r'\1all_passed = '),
    ],
    'test_str005.py': [
        (r'(\s+)_exit_triggered = ', r'\1exit_triggered = '),
    ],
    'test_str001.py': [
        (r'(\s+)_passed = ', r'\1passed = '),
    ],
    'utils/retry.py': [
        (r'(\s+)_delay = ', r'\1delay = '),
        (r'(\s+)_last_error = ', r'\1_last_error = '),  # This one should stay unused
    ],
    'validate_str001.py': [
        (r'(\s+)_passed = ', r'\1passed = '),
    ],
    'examples/parameter_sweep_demo.py': [
        (r'(\s+)_position_open = ', r'\1position_open = '),
    ],
    'examples/validate_sample_strategy.py': [
        (r'(\s+)_position_open = ', r'\1position_open = '),
        (r'(\s+)_current_price = ', r'\1current_price = '),
        (r'(\s+)_close_price = ', r'\1close_price = '),
    ],
}

def fix_file(filepath):
    """Apply fixes to a single file."""
    if not os.path.exists(filepath):
        print(f"SKIP: {filepath} (not found)")
        return False
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        
        # Apply each regex replacement
        for pattern, replacement in FIXES.get(filepath, []):
            content = re.sub(pattern, replacement, content)
        
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"FIXED: {filepath}")
            return True
        else:
            print(f"SKIP: {filepath} (no changes)")
            return False
    except Exception as e:
        print(f"ERROR: {filepath} - {e}")
        return False

if __name__ == '__main__':
    os.chdir('c:\\bybit-trading-bot')
    fixed_count = 0
    
    for filepath in FIXES.keys():
        if fix_file(filepath):
            fixed_count += 1
    
    print(f"\nTotal files fixed: {fixed_count}")
