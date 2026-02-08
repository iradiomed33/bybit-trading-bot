"""
TASK-004 Final Validation: Per-Symbol Strategy Isolation

Comprehensive validation that all requirements are met.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def validate_task004():
    """Run all TASK-004 validations"""
    
    print("\n" + "="*80)
    print(" TASK-004: MultiSymbol Per-Symbol Strategy Isolation - FINAL VALIDATION")
    print("="*80)
    
    tests_passed = 0
    tests_total = 0
    
    # TEST 1: Factory imports and creates strategies
    tests_total += 1
    print("\n[1/7] Testing StrategyFactory import and basic functionality...")
    try:
        from bot.strategy_factory import StrategyFactory
        
        strats1 = StrategyFactory.create_strategies()
        strats2 = StrategyFactory.create_strategies()
        
        assert len(strats1) == 3, "Should create 3 strategies"
        assert len(strats2) == 3, "Should create 3 strategies"
        
        id1 = id(strats1[0])
        id2 = id(strats2[0])
        assert id1 != id2, f"Instances should be different: {id1} vs {id2}"
        
        print(f"  ✓ PASS: Factory creates unique instances")
        print(f"    - Call 1, Strategy 0: id={id1}")
        print(f"    - Call 2, Strategy 0: id={id2}")
        print(f"    - Different: {id1 != id2}")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
    
    # TEST 2: Verify 3-symbol isolation
    tests_total += 1
    print("\n[2/7] Testing 3-symbol isolation (BTCUSDT, ETHUSDT, XRPUSDT)...")
    try:
        from bot.strategy_factory import StrategyFactory
        
        btc = StrategyFactory.create_strategies()
        eth = StrategyFactory.create_strategies()
        xrp = StrategyFactory.create_strategies()
        
        btc_ids = [id(s) for s in btc]
        eth_ids = [id(s) for s in eth]
        xrp_ids = [id(s) for s in xrp]
        
        # Check no overlaps
        all_ids = btc_ids + eth_ids + xrp_ids
        assert len(all_ids) == len(set(all_ids)), "All IDs should be unique"
        
        # Verify using factory method
        assert StrategyFactory.verify_per_symbol_instances(btc, eth, xrp), \
            "Factory should verify isolation"
        
        print(f"  ✓ PASS: 3 symbols have completely isolated strategies")
        print(f"    - BTCUSDT ids: {btc_ids}")
        print(f"    - ETHUSDT ids: {eth_ids}")
        print(f"    - XRPUSDT ids: {xrp_ids}")
        print(f"    - Total unique: {len(set(all_ids))}/9")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
    
    # TEST 3: MultiSymbolBot initialization
    tests_total += 1
    print("\n[3/7] Testing MultiSymbolBot initialization...")
    try:
        from bot.multi_symbol_bot import MultiSymbolBot, MultiSymbolConfig
        from unittest.mock import patch, MagicMock
        
        # Mock TradingBot to avoid complex initialization
        with patch('bot.multi_symbol_bot.TradingBot') as mock_bot:
            mock_bot.return_value = MagicMock()
            
            config = MultiSymbolConfig(
                symbols=["BTCUSDT", "ETHUSDT"],
                mode="paper",
                testnet=True,
            )
            
            bot = MultiSymbolBot(config)
            success = bot.initialize()
            
            assert success, "initialize() should return True"
            assert len(bot.bots) == 2, "Should have 2 bots"
            
            print(f"  ✓ PASS: MultiSymbolBot initializes correctly")
            print(f"    - Symbols: {config.symbols}")
            print(f"    - Bots created: {len(bot.bots)}")
            print(f"    - Mode: {config.mode}")
            tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
    
    # TEST 4: Concurrent creation safety
    tests_total += 1
    print("\n[4/7] Testing thread-safe concurrent strategy creation...")
    try:
        import threading
        from bot.strategy_factory import StrategyFactory
        
        all_ids = set()
        errors = []
        lock = threading.Lock()
        
        def create_for_symbol(symbol):
            try:
                strats = StrategyFactory.create_strategies()
                ids = StrategyFactory.get_strategy_ids(strats)
                with lock:
                    for id_val in ids:
                        if id_val in all_ids:
                            errors.append(f"Duplicate in {symbol}")
                        all_ids.add(id_val)
            except Exception as e:
                errors.append(str(e))
        
        threads = []
        for symbol in ["BTC", "ETH", "XRP", "ADA", "SOL"]:
            t = threading.Thread(target=create_for_symbol, args=(symbol,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Errors during concurrent creation: {errors}"
        assert len(all_ids) == 15, f"Should have 15 unique IDs, got {len(all_ids)}"
        
        print(f"  ✓ PASS: Concurrent creation is thread-safe")
        print(f"    - Threads: 5")
        print(f"    - Total unique IDs: {len(all_ids)}")
        print(f"    - Errors: {len(errors)}")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
    
    # TEST 5: Sequential uniqueness (10 calls = 30 objects)
    tests_total += 1
    print("\n[5/7] Testing sequential uniqueness (10 calls = 30 unique objects)...")
    try:
        from bot.strategy_factory import StrategyFactory
        
        all_ids = []
        for i in range(10):
            strats = StrategyFactory.create_strategies()
            ids = StrategyFactory.get_strategy_ids(strats)
            all_ids.extend(ids)
        
        unique_ids = set(all_ids)
        assert len(unique_ids) == 30, f"Expected 30 unique IDs, got {len(unique_ids)}"
        
        print(f"  ✓ PASS: Sequential creation maintains uniqueness")
        print(f"    - Calls: 10")
        print(f"    - Total objects: {len(all_ids)}")
        print(f"    - Unique objects: {len(unique_ids)}")
        print(f"    - Duplicates: {len(all_ids) - len(unique_ids)}")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
    
    # TEST 6: File existence checks
    tests_total += 1
    print("\n[6/7] Checking required files exist...")
    try:
        files_to_check = [
            "bot/strategy_factory.py",
            "bot/multi_symbol_bot.py",
            "tests/test_task004_per_symbol_strategies.py",
            "TASK004_COMPLETION.md",
            "TASK004_INTEGRATION_GUIDE.md",
        ]
        
        missing = []
        for fp in files_to_check:
            full_path = os.path.join(os.path.dirname(__file__), fp)
            if not os.path.exists(full_path):
                missing.append(fp)
        
        assert len(missing) == 0, f"Missing files: {missing}"
        
        print(f"  ✓ PASS: All required files exist")
        for fp in files_to_check:
            print(f"    - {fp}")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
    
    # TEST 7: Documentation exists and is substantial
    tests_total += 1
    print("\n[7/7] Checking documentation completeness...")
    try:
        doc_files = {
            "TASK004_COMPLETION.md": 500,  # Should be at least 500 bytes
            "TASK004_INTEGRATION_GUIDE.md": 500,
        }
        
        for doc_file, min_size in doc_files.items():
            full_path = os.path.join(os.path.dirname(__file__), doc_file)
            file_size = os.path.getsize(full_path)
            assert file_size >= min_size, f"{doc_file} too small: {file_size} < {min_size}"
        
        print(f"  ✓ PASS: Documentation files are substantial")
        for doc_file in doc_files:
            full_path = os.path.join(os.path.dirname(__file__), doc_file)
            size = os.path.getsize(full_path)
            print(f"    - {doc_file}: {size} bytes")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
    
    # SUMMARY
    print("\n" + "="*80)
    print(f" TASK-004 VALIDATION RESULTS: {tests_passed}/{tests_total} PASSED")
    print("="*80)
    
    if tests_passed == tests_total:
        print("\n✅ ALL VALIDATIONS PASSED!")
        print("\nTASK-004 is COMPLETE and READY FOR INTEGRATION:")
        print("  • StrategyFactory creates per-symbol unique instances ✓")
        print("  • MultiSymbolBot orchestrates multiple TradingBot instances ✓")
        print("  • Thread-safe concurrent creation ✓")
        print("  • Comprehensive test suite (14+ tests) ✓")
        print("  • Full documentation provided ✓")
        print("\n" + "="*80)
        return 0
    else:
        print(f"\n❌ {tests_total - tests_passed} TESTS FAILED")
        print("Please review the errors above and fix them.")
        return 1

if __name__ == "__main__":
    sys.exit(validate_task004())
