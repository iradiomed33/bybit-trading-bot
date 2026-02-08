"""
TASK-004 Quick Test Runner
Simplified test to verify per-symbol strategy isolation works
"""

import sys
import os

# Add root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.strategy_factory import StrategyFactory

def test_basic_functionality():
    """Test that factory creates unique instances"""
    print("\n" + "="*70)
    print("TASK-004: Per-Symbol Strategy Isolation Tests")
    print("="*70)
    
    # Test 1: Create strategies twice
    print("\n[Test 1] Creating strategies twice...")
    strats1 = StrategyFactory.create_strategies()
    ids1 = StrategyFactory.get_strategy_ids(strats1)
    print(f"  Call 1: {ids1}")
    
    strats2 = StrategyFactory.create_strategies()
    ids2 = StrategyFactory.get_strategy_ids(strats2)
    print(f"  Call 2: {ids2}")
    
    # Verify they're different
    assert ids1 != ids2, "Strategy IDs should be different!"
    print(f"  ✓ PASS: IDs are unique")
    
    # Test 2: Verify 3-symbol isolation
    print("\n[Test 2] Testing 3-symbol isolation (BTCUSDT, ETHUSDT, XRPUSDT)...")
    btc_strats = StrategyFactory.create_strategies()
    btc_ids = StrategyFactory.get_strategy_ids(btc_strats)
    
    eth_strats = StrategyFactory.create_strategies()
    eth_ids = StrategyFactory.get_strategy_ids(eth_strats)
    
    xrp_strats = StrategyFactory.create_strategies()
    xrp_ids = StrategyFactory.get_strategy_ids(xrp_strats)
    
    print(f"  BTCUSDT: {btc_ids}")
    print(f"  ETHUSDT: {eth_ids}")
    print(f"  XRPUSDT: {xrp_ids}")
    
    # Check isolation
    assert StrategyFactory.verify_per_symbol_instances(btc_strats, eth_strats, xrp_strats), \
        "Strategies should be isolated per symbol!"
    print(f"  ✓ PASS: All symbols have unique strategy instances")
    
    # Test 3: Check no overlaps
    print("\n[Test 3] Verifying no overlapping IDs across symbols...")
    all_ids = set(btc_ids) | set(eth_ids) | set(xrp_ids)
    assert len(all_ids) == 9, f"Expected 9 unique IDs, got {len(all_ids)}"
    
    btc_eth_overlap = set(btc_ids) & set(eth_ids)
    eth_xrp_overlap = set(eth_ids) & set(xrp_ids)
    btc_xrp_overlap = set(btc_ids) & set(xrp_ids)
    
    assert len(btc_eth_overlap) == 0, f"BTC-ETH overlap: {btc_eth_overlap}"
    assert len(eth_xrp_overlap) == 0, f"ETH-XRP overlap: {eth_xrp_overlap}"
    assert len(btc_xrp_overlap) == 0, f"BTC-XRP overlap: {btc_xrp_overlap}"
    
    print(f"  ✓ PASS: No ID overlaps between symbols")
    
    # Test 4: Multiple sequential calls
    print("\n[Test 4] Testing 10 sequential strategy creations...")
    all_created_ids = set()
    
    for i in range(10):
        strategies = StrategyFactory.create_strategies()
        ids = StrategyFactory.get_strategy_ids(strategies)
        
        # Check for duplicates within this call
        assert len(ids) == len(set(ids)), f"Duplicate IDs in call {i}"
        
        # Check for duplicates with previous calls
        overlap = set(ids) & all_created_ids
        assert len(overlap) == 0, f"Overlap with previous calls: {overlap}"
        
        all_created_ids.update(ids)
        print(f"  Call {i+1}: {len(all_created_ids)} total unique IDs so far")
    
    assert len(all_created_ids) == 30, f"Expected 30 unique objects, got {len(all_created_ids)}"
    print(f"  ✓ PASS: All 30 strategy instances are unique")
    
    # Test 5: Concurrent creation simulation
    print("\n[Test 5] Testing concurrent-like creation (sequential, but same pattern)...")
    import threading
    
    concurrent_ids = {}
    errors = []
    
    def create_for_symbol(symbol):
        try:
            strategies = StrategyFactory.create_strategies()
            concurrent_ids[symbol] = StrategyFactory.get_strategy_ids(strategies)
        except Exception as e:
            errors.append(f"{symbol}: {e}")
    
    threads = []
    for symbol in ["BTC", "ETH", "XRP", "ADA", "SOL"]:
        t = threading.Thread(target=create_for_symbol, args=(symbol,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    assert len(errors) == 0, f"Errors during concurrent creation: {errors}"
    
    all_concurrent_ids = []
    for symbol in ["BTC", "ETH", "XRP", "ADA", "SOL"]:
        ids = concurrent_ids[symbol]
        print(f"  {symbol}: {ids}")
        all_concurrent_ids.extend(ids)
    
    # All should be unique
    assert len(all_concurrent_ids) == len(set(all_concurrent_ids)), "Concurrent creation created duplicates!"
    print(f"  ✓ PASS: Concurrent creation maintains uniqueness")
    
    # Summary
    print("\n" + "="*70)
    print("✓ ALL TESTS PASSED!")
    print("="*70)
    print("\nSummary:")
    print("  - Factory creates unique instances on each call")
    print("  - Per-symbol isolation works (3+ symbols tested)")
    print("  - Sequential creation maintains uniqueness (10 calls)")
    print("  - Concurrent creation is thread-safe")
    print("\nTASK-004 Status: ✓ READY FOR INTEGRATION")
    print("="*70 + "\n")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(test_basic_functionality())
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
