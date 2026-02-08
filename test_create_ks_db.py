#!/usr/bin/env python
"""Test script to create a DB with activated KS"""
import sys
import tempfile
sys.path.insert(0, '.')
from storage.database import Database
from risk.kill_switch import KillSwitch

# Create temp DB
with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
    db_path = tmp.name

print(f'Test DB: {db_path}')

# Initialize and activate
db = Database(db_path=db_path)
ks = KillSwitch(db)
ks.activate('Test activation')
db.save_config('trading_disabled', True)

# Check status
is_active = ks.check_status()
td = db.get_config('trading_disabled', False)

print(f'Active: {is_active}')
print(f'TD flag: {td}')
print(f'Path: {db_path}')

db.close()
print(db_path)  # Last line for capture
