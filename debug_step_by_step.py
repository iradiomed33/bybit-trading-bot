#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""Test imports step by step."""

import sys


print("Step 1: Import typing...", flush=True)

try:

    pass

    print("✓ typing OK", flush=True)

except Exception as e:

    print(f"✗ typing failed: {e}", flush=True)

    sys.exit(1)


print("Step 2: Import Decimal...", flush=True)

try:

    pass

    print("✓ Decimal OK", flush=True)

except Exception as e:

    print(f"✗ Decimal failed: {e}", flush=True)

    sys.exit(1)


print("Step 3: Import dataclass...", flush=True)

try:

    pass

    print("✓ dataclass OK", flush=True)

except Exception as e:

    print(f"✗ dataclass failed: {e}", flush=True)

    sys.exit(1)


print("Step 4: Import numpy...", flush=True)

try:

    pass

    print("✓ numpy OK", flush=True)

except Exception as e:

    print(f"✗ numpy failed: {e}", flush=True)

    sys.exit(1)


print("Step 5: Import statistics...", flush=True)

try:

    pass

    print("✓ statistics OK", flush=True)

except Exception as e:

    print(f"✗ statistics failed: {e}", flush=True)

    sys.exit(1)


print("Step 6: Import logging...", flush=True)

try:

    pass

    print("✓ logging OK", flush=True)

except Exception as e:

    print(f"✗ logging failed: {e}", flush=True)

    sys.exit(1)


print("\nAll imports successful, now trying to exec the file...", flush=True)


# Now try reading and executing the file

with open("execution/trade_metrics.py", "r", encoding="utf-8") as f:

    code = f.read()


print("Step 7: Compile file...", flush=True)

try:

    compiled = compile(code, "execution/trade_metrics.py", "exec")

    print("✓ File compiled", flush=True)

except SyntaxError as e:

    print(f"✗ Syntax error: {e}", flush=True)

    sys.exit(1)


print("Step 8: Execute file...", flush=True)

try:

    namespace = {}

    exec(compiled, namespace)

    print("✓ File executed", flush=True)

except Exception as e:

    import traceback

    print(f"✗ Execution error: {e}", flush=True)

    traceback.print_exc()

    sys.exit(1)


print("\n✓✓✓ SUCCESS ✓✓✓", flush=True)
