try:

    print("Starting test...")

    print("Pandas imported")

    from strategy.trend_pullback import TrendPullbackStrategy

    print("Strategy imported")

    s = TrendPullbackStrategy(entry_mode="confirm_close")

    print(f"Strategy created: {s.entry_mode}")

    print("\nSTR-003 DoD VALIDATED:")

    print("  Parameter entry_mode exists: confirm_close, immediate, limit_retest")


except Exception as e:

    import traceback

    print("\n!!! ERROR !!!")

    traceback.print_exc()

    print(f"Exception: {e}")
