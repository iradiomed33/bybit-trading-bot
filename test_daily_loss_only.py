#!/usr/bin/env python
"""
Тест новой конфигурации Kill Switch - только Daily Loss.

Проверяем что:
1. Kill switch НЕ активируется при превышении leverage
2. Kill switch НЕ активируется при превышении notional
3. Kill switch НЕ активируется при превышении drawdown
4. Kill switch АКТИВИРУЕТСЯ только при превышении daily loss
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decimal import Decimal
from storage.database import Database
from risk.advanced_risk_limits import AdvancedRiskLimits, RiskLimitsConfig, RiskDecision
import tempfile

print("=" * 70)
print("ТЕСТ: Kill Switch активируется ТОЛЬКО при Daily Loss")
print("=" * 70)
print()

# Create temp DB
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
    db_path = tmp.name

db = Database(db_path=db_path)

# Создаем конфигурацию как в боте - только daily_loss check
risk_config = RiskLimitsConfig(
    max_leverage=Decimal("10"),
    max_notional=Decimal("50000"),
    daily_loss_limit_percent=Decimal("5"),
    max_drawdown_percent=Decimal("10"),
    enable_leverage_check=False,  # ОТКЛЮЧЕНО
    enable_notional_check=False,  # ОТКЛЮЧЕНО
    enable_daily_loss_check=True,  # АКТИВНО
    enable_drawdown_check=False,  # ОТКЛЮЧЕНО
)

risk_limits = AdvancedRiskLimits(db, risk_config)
risk_limits.set_session_start_equity(Decimal("10000"))

print("Конфигурация:")
print(f"  ✓ Daily Loss Check: ENABLED (limit: {risk_config.daily_loss_limit_percent}%)")
print(f"  ✗ Leverage Check: DISABLED")
print(f"  ✗ Notional Check: DISABLED")
print(f"  ✗ Drawdown Check: DISABLED")
print()

# Тест 1: Превышение leverage - должно быть ALLOW
print("ТЕСТ 1: Превышение leverage (20x > 10x limit)")
print("-" * 70)
state1 = {
    "account_balance": 10000,
    "current_equity": 10000,
    "realized_pnl_today": 0,
    "open_position_notional": 100000,
    "position_leverage": 20,  # ПРЕВЫШАЕТ ЛИМИТ 10x
    "new_position_notional": 0,
}
decision1, details1 = risk_limits.evaluate(state1)
print(f"  Leverage: 20x (limit: 10x)")
print(f"  Decision: {decision1.value}")
assert decision1 == RiskDecision.ALLOW, "Должен быть ALLOW т.к. leverage check отключен"
print(f"  ✅ PASS: Не блокирует при превышении leverage")
print()

# Тест 2: Превышение notional - должно быть ALLOW
print("ТЕСТ 2: Превышение notional ($100k > $50k limit)")
print("-" * 70)
state2 = {
    "account_balance": 10000,
    "current_equity": 10000,
    "realized_pnl_today": 0,
    "open_position_notional": 100000,  # ПРЕВЫШАЕТ ЛИМИТ $50k
    "position_leverage": 5,
    "new_position_notional": 0,
}
decision2, details2 = risk_limits.evaluate(state2)
print(f"  Notional: $100k (limit: $50k)")
print(f"  Decision: {decision2.value}")
assert decision2 == RiskDecision.ALLOW, "Должен быть ALLOW т.к. notional check отключен"
print(f"  ✅ PASS: Не блокирует при превышении notional")
print()

# Тест 3: Превышение drawdown - должно быть ALLOW
print("ТЕСТ 3: Превышение drawdown (15% > 10% limit)")
print("-" * 70)
state3 = {
    "account_balance": 10000,
    "current_equity": 8500,  # 15% drawdown от 10000
    "realized_pnl_today": 0,
    "open_position_notional": 10000,
    "position_leverage": 5,
    "new_position_notional": 0,
}
decision3, details3 = risk_limits.evaluate(state3)
print(f"  Equity: $8500 (start: $10000, drawdown: 15%)")
print(f"  Decision: {decision3.value}")
assert decision3 == RiskDecision.ALLOW, "Должен быть ALLOW т.к. drawdown check отключен"
print(f"  ✅ PASS: Не блокирует при превышении drawdown")
print()

# Тест 4: Превышение daily loss - должно быть STOP
print("ТЕСТ 4: Превышение daily loss (6% > 5% limit)")
print("-" * 70)
state4 = {
    "account_balance": 10000,
    "current_equity": 9400,
    "realized_pnl_today": -600,  # -6% от баланса (ПРЕВЫШАЕТ ЛИМИТ 5%)
    "open_position_notional": 10000,
    "position_leverage": 5,
    "new_position_notional": 0,
}
decision4, details4 = risk_limits.evaluate(state4)
print(f"  Daily Loss: -$600 (-6% от $10000)")
print(f"  Decision: {decision4.value}")
assert decision4 == RiskDecision.STOP, "Должен быть STOP т.к. daily loss превышен"
print(f"  ✅ PASS: Блокирует при превышении daily loss (активирует kill switch)")
print()

# Тест 5: Daily loss в пределах нормы - должно быть ALLOW
print("ТЕСТ 5: Daily loss в пределах нормы (3% < 5% limit)")
print("-" * 70)
state5 = {
    "account_balance": 10000,
    "current_equity": 9700,
    "realized_pnl_today": -300,  # -3% (В ПРЕДЕЛАХ ЛИМИТА)
    "open_position_notional": 10000,
    "position_leverage": 5,
    "new_position_notional": 0,
}
decision5, details5 = risk_limits.evaluate(state5)
print(f"  Daily Loss: -$300 (-3% от $10000)")
print(f"  Decision: {decision5.value}")
assert decision5 == RiskDecision.ALLOW, "Должен быть ALLOW т.к. daily loss в норме"
print(f"  ✅ PASS: Разрешает торговлю при нормальном daily loss")
print()

# Cleanup
db.close()
os.unlink(db_path)

print("=" * 70)
print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
print("=" * 70)
print()
print("Итоги:")
print("  ✓ Kill Switch НЕ срабатывает при превышении leverage")
print("  ✓ Kill Switch НЕ срабатывает при превышении notional")
print("  ✓ Kill Switch НЕ срабатывает при превышении drawdown")
print("  ✓ Kill Switch СРАБАТЫВАЕТ только при превышении daily loss > 5%")
print()
print("Новая конфигурация работает корректно!")
