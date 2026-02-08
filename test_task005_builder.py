#!/usr/bin/env python3
"""Quick test of StrategyBuilder"""

from bot.strategy_builder import StrategyBuilder
from config.settings import ConfigManager

print("\n" + "="*70)
print("TASK-005: StrategyBuilder Test")
print("="*70)

try:
    # Load config
    config = ConfigManager()
    print("\n✓ Config loaded from bot_settings.json")
    
    # Create builder
    builder = StrategyBuilder(config)
    print("✓ StrategyBuilder created")
    
    # Build strategies
    print("\nBuilding strategies from config...\n")
    strategies = builder.build_strategies()
    
    print(f"\n✓ Successfully created {len(strategies)} strategies\n")
    
    # Show params
    print("Strategy Parameters:")
    for strategy in strategies:
        name = strategy.__class__.__name__
        conf_thresh = getattr(strategy, 'confidence_threshold', 'N/A')
        min_candles = getattr(strategy, 'min_candles', 'N/A')
        print(f"\n  {name}:")
        print(f"    confidence_threshold: {conf_thresh}")
        print(f"    min_candles: {min_candles}")
    
    print("\n" + "="*70)
    print("✓ TASK-005: StrategyBuilder works correctly!")
    print("="*70 + "\n")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
