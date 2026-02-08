"""
Test that simulates bot startup after kill switch reset.
This verifies the exact scenario described in the problem statement.
"""

import sys
import os
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage.database import Database
from risk.kill_switch import KillSwitch


def test_bot_startup_scenario():
    """
    Simulates the exact scenario from the problem statement:
    1. python reset_killswitch.py (successful)
    2. python cli.py live (should work, not show "Kill switch is active")
    """
    
    print("=" * 70)
    print("SIMULATING BOT STARTUP AFTER KILL SWITCH RESET")
    print("=" * 70)
    print()
    
    # Use a temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Step 1: Initial state - activate kill switch and trading_disabled
        print("Step 1: Simulating previous kill switch activation...")
        db = Database(db_path=db_path)
        ks = KillSwitch(db)
        ks.activate("Daily loss limit exceeded")
        db.save_config("trading_disabled", True)
        
        # Verify it's active
        assert ks.check_status() == True, "Kill switch should be active"
        assert db.get_config("trading_disabled", False) == True
        print("✅ Kill switch activated")
        print("✅ Флаг trading_disabled установлен")
        print()
        
        db.close()
        
        # Step 2: Run reset_killswitch.py (simulated)
        print("Step 2: Simulating 'python reset_killswitch.py'...")
        db = Database(db_path=db_path)
        
        # Check status before reset
        ks_before = KillSwitch(db)
        is_active_before = ks_before.check_status()
        trading_disabled_before = db.get_config("trading_disabled", False)
        
        print(f"Before reset:")
        print(f"  - Kill switch active: {is_active_before}")
        print(f"  - trading_disabled: {trading_disabled_before}")
        
        # Perform reset (what reset_killswitch.py does)
        success_old = ks_before.reset("RESET")
        db.save_config("trading_disabled", False)
        
        # Verify reset
        ks_after = KillSwitch(db)
        is_active_after = ks_after.check_status()
        trading_disabled_after = db.get_config("trading_disabled", False)
        
        print(f"After reset:")
        print(f"  - Kill switch active: {is_active_after}")
        print(f"  - trading_disabled: {trading_disabled_after}")
        print()
        
        if success_old and not is_active_after and not trading_disabled_after:
            print("✅ KillSwitch успешно сброшен")
            print("✅ Флаг trading_disabled очищен")
            print("✅ Kill switch не активирован после проверки")
        else:
            print("❌ Reset failed!")
            return False
        
        print()
        db.close()
        
        # Step 3: Simulate bot startup (python cli.py live)
        print("Step 3: Simulating 'python cli.py live' (bot startup)...")
        db = Database(db_path=db_path)
        
        # This is what happens in TradingBot.run()
        # Check 1: Old KillSwitch (errors table)
        kill_switch = KillSwitch(db)
        if kill_switch.check_status():
            print("❌ Kill switch is active! Cannot start.")
            print("WARNING | Kill switch was previously activated (found in DB)")
            print()
            print("This is the BUG described in the problem statement!")
            return False
        
        print("✅ Kill switch check passed (not active)")
        
        # Check 2: trading_disabled flag
        trading_disabled = db.get_config("trading_disabled", False)
        if trading_disabled:
            print("❌ Trading is disabled! Cannot start.")
            return False
        
        print("✅ trading_disabled check passed")
        print()
        
        print("=" * 70)
        print("✅ BOT STARTUP SUCCESSFUL!")
        print("=" * 70)
        print()
        print("The bot would start normally without errors.")
        print("Fix is working correctly!")
        
        return True
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    success = test_bot_startup_scenario()
    sys.exit(0 if success else 1)
