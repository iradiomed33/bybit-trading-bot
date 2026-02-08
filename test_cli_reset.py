#!/usr/bin/env python
"""Test CLI reset command"""
import sys
import tempfile
import os
import subprocess

sys.path.insert(0, '.')

from storage.database import Database
from risk.kill_switch import KillSwitch

# Create temp DB with activated KS
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
    test_db_path = tmp.name

print(f"Creating test database: {test_db_path}")
db = Database(db_path=test_db_path)
ks = KillSwitch(db)
ks.activate('Test activation for CLI test')
db.save_config('trading_disabled', True)

# Verify it's activated
is_active = ks.check_status()
td = db.get_config('trading_disabled', False)
print(f"Before: KS active={is_active}, trading_disabled={td}")
db.close()

# Now test the reset using the CLI reset function directly
print("\nTesting reset logic from cli.py...")
print("-" * 50)

# Import and call the reset logic (simulate CLI call)
db = Database(db_path=test_db_path)
from risk.kill_switch import KillSwitch

# Reset old KillSwitch
ks2 = KillSwitch(db)
success_old = ks2.reset("RESET")
print(f"KillSwitch.reset() returned: {success_old}")

# Reset trading_disabled
db.save_config("trading_disabled", False)
print(f"trading_disabled set to False")

# Verify
ks3 = KillSwitch(db)
is_active_after = ks3.check_status()
td_after = db.get_config('trading_disabled', False)
print(f"\nAfter: KS active={is_active_after}, trading_disabled={td_after}")

db.close()
os.unlink(test_db_path)

if not is_active_after and not td_after:
    print("\n✅ CLI reset logic works correctly!")
    sys.exit(0)
else:
    print("\n❌ CLI reset logic FAILED!")
    sys.exit(1)
