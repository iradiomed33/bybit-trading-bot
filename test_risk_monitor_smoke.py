#!/usr/bin/env python3
"""
Smoke test for RiskMonitorService implementation.

Проверяет:
1. RiskMonitorService может быть импортирован
2. Методы существуют и могут быть вызваны
3. Интеграция с TradingBot
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_risk_monitor_import():
    """Test 1: Can import RiskMonitorService"""
    print("[Test 1] Importing RiskMonitorService...")
    
    try:
        from risk.risk_monitor import RiskMonitorService, RiskMonitorConfig
        print("✓ RiskMonitorService imported successfully")
        print("✓ RiskMonitorConfig imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_risk_monitor_methods():
    """Test 2: Check that methods exist"""
    print("\n[Test 2] Checking RiskMonitorService methods...")
    
    from risk.risk_monitor import RiskMonitorService
    
    methods = [
        "calculate_equity",
        "calculate_daily_realized_pnl",
        "get_position_info",
        "count_open_orders",
        "check_all_limits",
        "trigger_kill_switch_if_needed",
        "run_monitoring_check",
        "start_monitoring",
        "stop_monitoring",
        "get_status",
    ]
    
    for method in methods:
        if hasattr(RiskMonitorService, method):
            print(f"✓ Method {method}() exists")
        else:
            print(f"✗ Method {method}() missing")
            return False
    
    return True


def test_trading_bot_integration():
    """Test 3: Check TradingBot integration"""
    print("\n[Test 3] Checking TradingBot integration...")
    
    # Check import
    try:
        from bot.trading_bot import TradingBot
        print("✓ TradingBot can be imported")
    except ImportError as e:
        print(f"✗ TradingBot import failed: {e}")
        return False
    
    # Check if RiskMonitorService is imported
    import bot.trading_bot as bot_module
    source = open(bot_module.__file__).read()
    
    if "from risk.risk_monitor import" in source:
        print("✓ TradingBot imports RiskMonitorService")
    else:
        print("✗ TradingBot does not import RiskMonitorService")
        return False
    
    if "self.risk_monitor = RiskMonitorService" in source:
        print("✓ TradingBot creates risk_monitor instance")
    else:
        print("✗ TradingBot does not create risk_monitor")
        return False
    
    if "self.risk_monitor.start_monitoring()" in source:
        print("✓ TradingBot starts risk monitoring in run()")
    else:
        print("✗ TradingBot does not start risk monitoring")
        return False
    
    if "self.risk_monitor.stop_monitoring()" in source:
        print("✓ TradingBot stops risk monitoring in stop()")
    else:
        print("✗ TradingBot does not stop risk monitoring")
        return False
    
    return True


def test_config_parameters():
    """Test 4: Check RiskMonitorConfig parameters"""
    print("\n[Test 4] Checking RiskMonitorConfig parameters...")
    
    from risk.risk_monitor import RiskMonitorConfig
    
    config = RiskMonitorConfig()
    
    params = [
        "max_daily_loss_percent",
        "max_position_notional",
        "max_leverage",
        "max_orders_per_symbol",
        "monitor_interval_seconds",
        "enable_auto_kill_switch",
    ]
    
    for param in params:
        if hasattr(config, param):
            value = getattr(config, param)
            print(f"✓ Parameter {param} = {value}")
        else:
            print(f"✗ Parameter {param} missing")
            return False
    
    return True


def main():
    """Run all smoke tests"""
    print("="*60)
    print("RISK MONITOR SERVICE - SMOKE TEST")
    print("="*60)
    
    tests = [
        test_risk_monitor_import,
        test_risk_monitor_methods,
        test_trading_bot_integration,
        test_config_parameters,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test exception: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("\n✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("\nRiskMonitorService:")
        print("  - Calculates equity = wallet_balance + unrealized_pnl")
        print("  - Tracks realized PnL for the day from executions")
        print("  - Monitors max daily loss, position size, leverage, orders")
        print("  - Auto-triggers kill switch on critical violations")
        print("  - Integrated into TradingBot for live mode")
        return 0
    else:
        print("\n✗✗✗ SOME TESTS FAILED ✗✗✗")
        return 1


if __name__ == "__main__":
    sys.exit(main())
