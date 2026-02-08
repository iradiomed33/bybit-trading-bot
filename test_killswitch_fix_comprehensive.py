"""
Comprehensive test for kill switch check_status() fix.

Tests the fix for the bug where kill switch remained activated after reset.
This test verifies all scenarios mentioned in the problem statement.
"""

import sys
import os
import tempfile
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage.database import Database
from risk.kill_switch import KillSwitch


def test_scenario_1_basic_reset():
    """Test basic scenario: activate -> reset -> check"""
    print("=" * 70)
    print("SCENARIO 1: Basic Reset")
    print("=" * 70)
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        db = Database(db_path=db_path)
        
        # 1. Activate
        print("1. Activating kill switch...")
        ks = KillSwitch(db)
        ks.activate("test")
        assert ks.check_status() == True, "Should be activated"
        print("   ✅ Kill switch activated")
        
        # 2. Reset
        print("2. Resetting kill switch...")
        result = ks.reset("RESET")
        assert result is True, "Reset should succeed"
        print("   ✅ Kill switch reset")
        
        # 3. Check on same instance
        print("3. Checking status on same instance...")
        is_active = ks.check_status()
        assert is_active == False, "Should NOT be activated after reset"
        print(f"   ✅ Status: {is_active} (expected: False)")
        
        # 4. Create new instance (simulating bot restart)
        print("4. Creating new instance (simulating bot restart)...")
        ks2 = KillSwitch(db)
        is_active = ks2.check_status()
        assert is_active == False, "Should NOT be activated in new instance"
        print(f"   ✅ Status: {is_active} (expected: False)")
        
        print("✅ SCENARIO 1 PASSED\n")
        return True
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_scenario_2_old_activation():
    """Test scenario with activation older than 24h"""
    print("=" * 70)
    print("SCENARIO 2: Old Activation (>24h) -> Reset -> Check")
    print("=" * 70)
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        db = Database(db_path=db_path)
        
        # 1. Create old activation (25h ago) directly in DB
        print("1. Creating old activation (25h ago)...")
        cursor = db.conn.cursor()
        cursor.execute("""
            INSERT INTO errors (error_type, message, timestamp, metadata)
            VALUES ('kill_switch_activated', 'Old activation', 
                    strftime('%s', 'now', '-25 hours'), '{}')
        """)
        db.conn.commit()
        print("   ✅ Old activation created")
        
        # 2. Check status - with new logic, it should detect old activations
        print("2. Checking status (activation is >24h old)...")
        ks = KillSwitch(db)
        is_active = ks.check_status()
        print(f"   Status: {is_active}")
        print(f"   Note: Old activations ARE now detected (no time window)")
        assert is_active == True, "Should detect old activation (no time limit)"
        print("   ✅ Old activation detected correctly")
        
        # 3. Reset
        print("3. Resetting kill switch...")
        result = ks.reset("RESET")
        assert result is True
        print("   ✅ Reset successful")
        
        # 4. Check again - should be False now
        print("4. Checking after reset...")
        is_active = ks.check_status()
        assert is_active == False, "Should NOT be activated after reset"
        print(f"   ✅ Status: {is_active} (expected: False)")
        
        # 5. New instance
        print("5. New instance check...")
        ks2 = KillSwitch(db)
        is_active = ks2.check_status()
        assert is_active == False, "Should NOT be activated in new instance"
        print(f"   ✅ Status: {is_active} (expected: False)")
        
        print("✅ SCENARIO 2 PASSED\n")
        return True
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_scenario_3_old_reset():
    """Test scenario with reset older than 24h"""
    print("=" * 70)
    print("SCENARIO 3: Activate -> Reset -> Age Reset >24h -> Check")
    print("=" * 70)
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        db = Database(db_path=db_path)
        
        # 1. Activate
        print("1. Activating kill switch...")
        ks = KillSwitch(db)
        ks.activate("test")
        assert ks.check_status() == True
        print("   ✅ Activated")
        
        # 2. Reset
        print("2. Resetting...")
        ks.reset("RESET")
        assert ks.check_status() == False
        print("   ✅ Reset successful")
        
        # 3. Age the reset record to >24h
        print("3. Aging reset record to 25h ago...")
        cursor = db.conn.cursor()
        cursor.execute("""
            UPDATE errors 
            SET timestamp = strftime('%s', 'now', '-25 hours')
            WHERE error_type = 'kill_switch_reset'
        """)
        db.conn.commit()
        print("   ✅ Reset record aged")
        
        # 4. Check - with new logic (no time window), old reset should still work
        print("4. Checking with old reset...")
        ks2 = KillSwitch(db)
        is_active = ks2.check_status()
        # Since activation was deleted, there are NO activations
        # So should be False
        assert is_active == False, "Should NOT be activated (no activation records)"
        print(f"   ✅ Status: {is_active} (expected: False)")
        print("   Note: Works because reset() DELETES activation records")
        
        print("✅ SCENARIO 3 PASSED\n")
        return True
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_scenario_4_multiple_cycles():
    """Test multiple activation/reset cycles"""
    print("=" * 70)
    print("SCENARIO 4: Multiple Activation/Reset Cycles")
    print("=" * 70)
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        db = Database(db_path=db_path)
        ks = KillSwitch(db)
        
        for i in range(3):
            print(f"\nCycle {i+1}:")
            
            # Activate
            print(f"  {i+1}.1 Activating...")
            ks.activate(f"test {i+1}")
            assert ks.check_status() == True
            print("     ✅ Activated")
            
            # Reset
            print(f"  {i+1}.2 Resetting...")
            ks.reset("RESET")
            assert ks.check_status() == False
            print("     ✅ Reset")
            
            # New instance
            print(f"  {i+1}.3 New instance check...")
            ks_new = KillSwitch(db)
            assert ks_new.check_status() == False
            print("     ✅ Still reset in new instance")
        
        print("\n✅ SCENARIO 4 PASSED (all 3 cycles)\n")
        return True
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_scenario_5_reset_without_activation():
    """Test reset when there was no activation"""
    print("=" * 70)
    print("SCENARIO 5: Reset Without Prior Activation")
    print("=" * 70)
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        db = Database(db_path=db_path)
        
        # 1. Check initial state
        print("1. Checking initial state...")
        ks = KillSwitch(db)
        is_active = ks.check_status()
        assert is_active == False, "Should not be activated initially"
        print(f"   ✅ Status: {is_active} (expected: False)")
        
        # 2. Reset without activation
        print("2. Calling reset without prior activation...")
        result = ks.reset("RESET")
        assert result is True
        print("   ✅ Reset succeeded")
        
        # 3. Check again
        print("3. Checking after reset...")
        is_active = ks.check_status()
        assert is_active == False, "Should still not be activated"
        print(f"   ✅ Status: {is_active} (expected: False)")
        
        print("✅ SCENARIO 5 PASSED\n")
        return True
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_scenario_6_invalid_confirmation():
    """Test that invalid confirmation doesn't reset"""
    print("=" * 70)
    print("SCENARIO 6: Invalid Confirmation Code")
    print("=" * 70)
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        db = Database(db_path=db_path)
        
        # 1. Activate
        print("1. Activating...")
        ks = KillSwitch(db)
        ks.activate("test")
        assert ks.check_status() == True
        print("   ✅ Activated")
        
        # 2. Try reset with wrong code
        print("2. Trying reset with wrong code...")
        result = ks.reset("WRONG")
        assert result is False, "Should fail with wrong code"
        print("   ✅ Reset rejected")
        
        # 3. Check that it's still activated
        print("3. Checking status...")
        is_active = ks.check_status()
        assert is_active == True, "Should still be activated"
        print(f"   ✅ Status: {is_active} (expected: True)")
        
        # 4. Reset with correct code
        print("4. Resetting with correct code...")
        result = ks.reset("RESET")
        assert result is True
        is_active = ks.check_status()
        assert is_active == False
        print("   ✅ Reset successful")
        
        print("✅ SCENARIO 6 PASSED\n")
        return True
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def run_all_tests():
    """Run all test scenarios"""
    print("\n" + "=" * 70)
    print("COMPREHENSIVE KILL SWITCH CHECK_STATUS FIX TEST")
    print("=" * 70 + "\n")
    
    tests = [
        ("Basic Reset", test_scenario_1_basic_reset),
        ("Old Activation", test_scenario_2_old_activation),
        ("Old Reset", test_scenario_3_old_reset),
        ("Multiple Cycles", test_scenario_4_multiple_cycles),
        ("Reset Without Activation", test_scenario_5_reset_without_activation),
        ("Invalid Confirmation", test_scenario_6_invalid_confirmation),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"❌ {name} FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Kill switch fix is working correctly.")
        return True
    else:
        print(f"\n❌ {total - passed} test(s) failed.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
