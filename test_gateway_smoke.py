#!/usr/bin/env python3
"""
Smoke test для проверки Execution Gateway паттерна.
"""

import sys
import os

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("Execution Gateway Smoke Test")
print("=" * 60)

# Test 1: Импорт gateway классов
print("\n[Test 1] Gateway imports...")
try:
    from execution.gateway import IExecutionGateway
    from execution.live_gateway import BybitLiveGateway
    from execution.paper_gateway import PaperGateway
    from execution.backtest_gateway import BacktestGateway
    from execution.order_result import OrderResult
    print("✓ All gateway classes imported successfully")
except Exception as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Test 2: Проверка интерфейса
print("\n[Test 2] IExecutionGateway interface...")
try:
    required_methods = [
        'place_order',
        'cancel_order',
        'cancel_all_orders',
        'get_position',
        'get_positions',
        'get_open_orders',
        'set_trading_stop',
        'cancel_trading_stop',
        'get_account_balance',
        'get_executions',
    ]
    
    for method in required_methods:
        if not hasattr(IExecutionGateway, method):
            print(f"❌ Missing method: {method}")
            sys.exit(1)
        print(f"  ✓ {method}() exists")
    
    print("✓ All required methods in IExecutionGateway")
except Exception as e:
    print(f"❌ Interface check failed: {e}")
    sys.exit(1)

# Test 3: BacktestGateway базовые операции
print("\n[Test 3] BacktestGateway operations...")
try:
    gateway = BacktestGateway(initial_balance=10000)
    
    # Place market order
    result = gateway.place_order(
        category="linear",
        symbol="BTCUSDT",
        side="Buy",
        order_type="Market",
        qty=0.001,
        price=50000.0
    )
    
    if not result.success:
        print(f"❌ Failed to place order: {result.error}")
        sys.exit(1)
    print(f"  ✓ Market order placed: {result.order_id}")
    
    # Get position
    position = gateway.get_position("linear", "BTCUSDT")
    if position is None:
        print("❌ Position not found after order")
        sys.exit(1)
    print(f"  ✓ Position created: size={position['size']}")
    
    # Get account balance
    balance = gateway.get_account_balance()
    if 'balance' not in balance:
        print("❌ Balance not returned")
        sys.exit(1)
    print(f"  ✓ Account balance: {balance['balance']}")
    
    print("✓ BacktestGateway works")
except Exception as e:
    print(f"❌ BacktestGateway test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Проверка что gateway возвращает OrderResult
print("\n[Test 4] OrderResult returns...")
try:
    gateway = BacktestGateway()
    
    # Place order
    result = gateway.place_order(
        category="linear",
        symbol="ETHUSDT",
        side="Buy",
        order_type="Market",
        qty=0.01,
    )
    
    if not isinstance(result, OrderResult):
        print(f"❌ Expected OrderResult, got {type(result)}")
        sys.exit(1)
    
    if not hasattr(result, 'success'):
        print("❌ OrderResult missing 'success' attribute")
        sys.exit(1)
    
    if not hasattr(result, 'order_id'):
        print("❌ OrderResult missing 'order_id' attribute")
        sys.exit(1)
    
    print(f"  ✓ Returns OrderResult with success={result.success}")
    print(f"  ✓ Order ID: {result.order_id}")
    
    # Cancel order
    cancel_result = gateway.cancel_order(
        category="linear",
        symbol="ETHUSDT",
        order_id="invalid_id"
    )
    
    if not isinstance(cancel_result, OrderResult):
        print(f"❌ Cancel should return OrderResult")
        sys.exit(1)
    
    print("✓ All methods return OrderResult")
except Exception as e:
    print(f"❌ OrderResult test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: execution/__init__.py экспорт
print("\n[Test 5] Module exports...")
try:
    import execution
    
    if not hasattr(execution, 'IExecutionGateway'):
        print("❌ IExecutionGateway not exported")
        sys.exit(1)
    
    if not hasattr(execution, 'BybitLiveGateway'):
        print("❌ BybitLiveGateway not exported")
        sys.exit(1)
    
    if not hasattr(execution, 'PaperGateway'):
        print("❌ PaperGateway not exported")
        sys.exit(1)
    
    if not hasattr(execution, 'BacktestGateway'):
        print("❌ BacktestGateway not exported")
        sys.exit(1)
    
    print("✓ All gateway classes exported from execution module")
except Exception as e:
    print(f"❌ Export test failed: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ ALL SMOKE TESTS PASSED")
print("=" * 60)
print("\nNext: Refactor TradingBot to use gateway instead of if-mode checks")
