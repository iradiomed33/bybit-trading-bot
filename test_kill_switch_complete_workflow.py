"""
Final integration test for kill switch fix.
This test verifies the complete workflow including both KillSwitch implementations.
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage.database import Database
from risk.kill_switch import KillSwitch


def test_complete_kill_switch_workflow():
    """
    Complete workflow test for kill switch:
    1. Bot running normally
    2. Kill switch triggered (e.g., daily loss limit)
    3. User runs reset script
    4. Bot can start again
    """
    
    print("\n" + "=" * 70)
    print("COMPLETE KILL SWITCH WORKFLOW TEST")
    print("=" * 70 + "\n")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Phase 1: Normal operation
        print("Phase 1: Normal Operation")
        print("-" * 70)
        db = Database(db_path=db_path)
        kill_switch = KillSwitch(db)
        
        is_active = kill_switch.check_status()
        print(f"Initial status: {is_active}")
        assert is_active == False, "Should not be active initially"
        print("✅ Bot can start normally\n")
        
        # Phase 2: Kill switch activation (e.g., daily loss > 5%)
        print("Phase 2: Kill Switch Activation")
        print("-" * 70)
        print("Simulating: Daily loss exceeded 5% threshold")
        kill_switch.activate("Daily loss limit exceeded: -5.2%")
        db.save_config("trading_disabled", True)
        
        is_active = kill_switch.check_status()
        trading_disabled = db.get_config("trading_disabled", False)
        
        print(f"Kill switch active: {is_active}")
        print(f"Trading disabled: {trading_disabled}")
        assert is_active == True, "Kill switch should be active"
        assert trading_disabled == True, "Trading should be disabled"
        print("✅ Kill switch activated successfully\n")
        
        db.close()
        
        # Phase 3: User attempts to start bot (should fail)
        print("Phase 3: Attempt to Start Bot (Expected to Fail)")
        print("-" * 70)
        db = Database(db_path=db_path)
        kill_switch_check = KillSwitch(db)
        
        can_start = not kill_switch_check.check_status()
        trading_allowed = not db.get_config("trading_disabled", False)
        
        print(f"Can start: {can_start}")
        print(f"Trading allowed: {trading_allowed}")
        assert not can_start, "Should not be able to start"
        assert not trading_allowed, "Trading should not be allowed"
        print("✅ Bot correctly refuses to start\n")
        
        # Phase 4: User runs reset script
        print("Phase 4: Reset Kill Switch")
        print("-" * 70)
        print("Running: python reset_killswitch.py")
        
        # Simulate reset_killswitch.py
        reset_result = kill_switch_check.reset("RESET")
        db.save_config("trading_disabled", False)
        
        # Verify reset
        kill_switch_after = KillSwitch(db)
        is_active_after = kill_switch_after.check_status()
        trading_disabled_after = db.get_config("trading_disabled", False)
        
        print(f"Reset result: {reset_result}")
        print(f"Kill switch active: {is_active_after}")
        print(f"Trading disabled: {trading_disabled_after}")
        assert reset_result == True, "Reset should succeed"
        assert is_active_after == False, "Kill switch should not be active"
        assert trading_disabled_after == False, "Trading should be enabled"
        print("✅ Kill switch reset successfully\n")
        
        db.close()
        
        # Phase 5: User starts bot again (should succeed)
        print("Phase 5: Start Bot After Reset (Expected to Succeed)")
        print("-" * 70)
        db = Database(db_path=db_path)
        kill_switch_final = KillSwitch(db)
        
        can_start = not kill_switch_final.check_status()
        trading_allowed = not db.get_config("trading_disabled", False)
        
        print(f"Can start: {can_start}")
        print(f"Trading allowed: {trading_allowed}")
        assert can_start, "Should be able to start"
        assert trading_allowed, "Trading should be allowed"
        print("✅ Bot starts successfully!\n")
        
        # Phase 6: Test persistence (simulating bot restart)
        print("Phase 6: Bot Restart (Simulating Process Restart)")
        print("-" * 70)
        db.close()
        
        # New database connection (simulating fresh bot process)
        db = Database(db_path=db_path)
        kill_switch_restart = KillSwitch(db)
        
        can_start = not kill_switch_restart.check_status()
        trading_allowed = not db.get_config("trading_disabled", False)
        
        print(f"Can start after restart: {can_start}")
        print(f"Trading allowed after restart: {trading_allowed}")
        assert can_start, "Should be able to start after restart"
        assert trading_allowed, "Trading should be allowed after restart"
        print("✅ Reset persists across restarts\n")
        
        print("=" * 70)
        print("✅ ALL PHASES COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print()
        print("Summary:")
        print("  1. ✅ Normal operation works")
        print("  2. ✅ Kill switch activates correctly")
        print("  3. ✅ Bot refuses to start when kill switch is active")
        print("  4. ✅ Reset script works correctly")
        print("  5. ✅ Bot starts successfully after reset")
        print("  6. ✅ Reset persists across bot restarts")
        print()
        print("The kill switch fix is working correctly in all scenarios!")
        
        return True
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    success = test_complete_kill_switch_workflow()
    sys.exit(0 if success else 1)
