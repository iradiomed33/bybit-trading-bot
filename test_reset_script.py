#!/usr/bin/env python
"""Test the reset script with a test database"""
import sys
import tempfile
import os
sys.path.insert(0, '.')

from storage.database import Database
from risk.kill_switch import KillSwitch

# Create temp DB with activated KS
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
    test_db_path = tmp.name

print(f"Creating test database: {test_db_path}")
db = Database(db_path=test_db_path)
ks = KillSwitch(db)
ks.activate('Test activation')
db.save_config('trading_disabled', True)
db.close()

print(f"KS activated in test DB: {test_db_path}")
print()

# Now test the reset logic
print("=" * 70)
print("ТЕСТИРОВАНИЕ СБРОСА KILL SWITCH")
print("=" * 70)
print()

db = Database(db_path=test_db_path)
print(f"✓ База данных: {test_db_path}")
print()

# Check initial status
print("1️⃣  Проверка статуса ДО сброса...")
ks_check = KillSwitch(db)
is_active_before = ks_check.check_status()
td_before = db.get_config("trading_disabled", False)

print(f"   KillSwitch активирован: {is_active_before}")
print(f"   trading_disabled флаг: {td_before}")
print()

# Reset
print("2️⃣  Выполнение сброса...")
success_old = ks_check.reset("RESET")
db.save_config("trading_disabled", False)
print(f"   KillSwitch.reset(): {success_old}")
print(f"   trading_disabled очищен: True")
print()

# Check after reset
print("3️⃣  Проверка статуса ПОСЛЕ сброса...")
ks_verify = KillSwitch(db)
is_active_after = ks_verify.check_status()
td_after = db.get_config("trading_disabled", False)

print(f"   KillSwitch активирован: {is_active_after}")
print(f"   trading_disabled флаг: {td_after}")
print()

# Result
if not is_active_after and not td_after:
    print("✅ ТЕСТ ПРОЙДЕН: Сброс работает корректно!")
    result = 0
else:
    print("❌ ТЕСТ ПРОВАЛЕН: Сброс не сработал!")
    result = 1

db.close()
os.unlink(test_db_path)

sys.exit(result)
