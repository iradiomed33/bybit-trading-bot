#!/usr/bin/env python
"""Test improved error messages"""
import sys
import tempfile
import os
sys.path.insert(0, '.')

from storage.database import Database
from risk.kill_switch import KillSwitch

# Create temp DB with activated KS
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
    test_db_path = tmp.name

print("=" * 70)
print("ТЕСТ: Улучшенные сообщения об ошибке Kill Switch")
print("=" * 70)
print()

db = Database(db_path=test_db_path)
ks = KillSwitch(db)
ks.activate('Test activation for message demo')

print("Активирован kill switch, теперь проверим сообщения...\n")

# Create new instance to trigger the warning
ks2 = KillSwitch(db)
is_active = ks2.check_status()

print()
print(f"check_status() returned: {is_active}")
print()

# Simulate what bot does
if is_active:
    print("=" * 70)
    print("СООБЩЕНИЯ, КОТОРЫЕ УВИДИТ ПОЛЬЗОВАТЕЛЬ:")
    print("=" * 70)
    print("❌ Kill switch is active! Cannot start.")
    print("━" * 70)
    print("To reset kill switch, run ONE of these commands:")
    print("  1) python cli.py reset-kill-switch")
    print("  2) python reset_killswitch.py")
    print("  3) Open UI and click 'Reset Kill Switch' button")
    print("━" * 70)
    print("See СРОЧНО_СБРОС_KILLSWITCH.md for detailed instructions")
    print()

db.close()
os.unlink(test_db_path)

print("✅ Новые сообщения гораздо более информативны!")
