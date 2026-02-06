"""Quick STR-003 test"""


import pandas as pd

from strategy.trend_pullback import TrendPullbackStrategy


# Test 1

print("Test 1: entry_mode parameter...")

s = TrendPullbackStrategy(entry_mode="confirm_close")

assert s.entry_mode == "confirm_close"

print("  OK: confirm_close")


s2 = TrendPullbackStrategy(entry_mode="immediate")

assert s2.entry_mode == "immediate"

print("  OK: immediate")


s3 = TrendPullbackStrategy(entry_mode="limit_retest", limit_ttl_bars=5)

assert s3.entry_mode == "limit_retest" and s3.limit_ttl_bars == 5

print("  OK: limit_retest")


try:

    TrendPullbackStrategy(entry_mode="invalid")

    print("  FAIL")

except ValueError:

    print("  OK: invalid rejected")


# Test 2

print("\nTest 2: Confirmation logic...")

df = pd.DataFrame({"close": [50000, 49900, 50300]})

confirmed, details = s._check_entry_confirmation(df, "TEST", True, 50100)

assert confirmed and details["mode"] == "confirm_close"

print("  OK: LONG confirmation")


# Test 3

df2 = pd.DataFrame({"close": [50000, 50100, 50200]})

confirmed2, _ = s._check_entry_confirmation(df2, "TEST", True, 50050)

assert not confirmed2

print("  OK: No false confirmation")


print("\nPASSED - STR-003 DoD:")

print("  DoD #1: Entry rule tested")

print("  DoD #2: entry_mode parameter exists")
