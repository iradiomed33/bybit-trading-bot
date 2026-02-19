#!/usr/bin/env python3
"""
Переключает Grid Trading в тестовый режим с расслабленными фильтрами.
Использовать для проверки работоспособности стратегии.

ИСПОЛЬЗОВАНИЕ:
  python enable_grid_test_mode.py           # Включить тестовый режим
  python enable_grid_test_mode.py --restore # Вернуть строгий режим
"""
import json

CONFIG_PATH = "config/bot_settings.json"

def enable_grid_test_mode():
    """Включает Grid Trading в мягком режиме для тестирования"""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    print("📊 Текущие настройки Grid Trading:")
    grid_cfg = config["strategies"]["GridTrading"]
    print(f"  require_ranging_market: {grid_cfg['require_ranging_market']}")
    print(f"  max_adx_for_range: {grid_cfg['max_adx_for_range']}")
    print(f"  enable_breakout_protection: {grid_cfg['enable_breakout_protection']}")
    print(f"  min_bb_width: {grid_cfg['min_bb_width']}")
    print(f"  max_bb_width: {grid_cfg['max_bb_width']}")
    
    # Расслабленные настройки для тестирования
    config["strategies"]["GridTrading"].update({
        "require_ranging_market": False,       # ← Отключаем проверку range
        "max_adx_for_range": 40.0,             # ← Увеличиваем порог ADX
        "enable_breakout_protection": False,   # ← Отключаем защиту от пробоя
        "min_bb_width": 0.01,                  # ← Снижаем минимум BB
        "max_bb_width": 0.10,                  # ← Увеличиваем максимум BB
        "grid_spacing_percent": 2.0            # ← Больше шаг между уровнями
    })
    
    # Увеличиваем веса Grid Trading для всех режимов
    meta_weights = config["meta_layer"]["strategy_weights"]["GridTrading"]
    meta_weights["base_weight"] = 1.5
    meta_weights["regime_multipliers"]["trend_up"] = 0.8
    meta_weights["regime_multipliers"]["trend_down"] = 0.8
    
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print("\n✅ Grid Trading переключена в ТЕСТОВЫЙ РЕЖИМ:")
    print("  ✓ require_ranging_market = False")
    print("  ✓ enable_breakout_protection = False")
    print("  ✓ max_adx_for_range = 40.0")
    print("  ✓ Веса увеличены для всех режимов")
    print("\n⚠️  ВНИМАНИЕ: Это для тестирования!")
    print("   После проверки верните строгие фильтры командой:")
    print("   python restore_grid_strict_mode.py")

def restore_strict_mode():
    """Возвращает строгие фильтры для live торговли"""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Строгие настройки для live
    config["strategies"]["GridTrading"].update({
        "require_ranging_market": True,
        "max_adx_for_range": 25.0,
        "enable_breakout_protection": True,
        "min_bb_width": 0.015,
        "max_bb_width": 0.05,
        "grid_spacing_percent": 1.5
    })
    
    # Восстанавливаем оригинальные веса
    meta_weights = config["meta_layer"]["strategy_weights"]["GridTrading"]
    meta_weights["base_weight"] = 1.0
    meta_weights["regime_multipliers"]["trend_up"] = 0.2
    meta_weights["regime_multipliers"]["trend_down"] = 0.2
    
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print("✅ Grid Trading вернулась в СТРОГИЙ РЕЖИМ (для live торговли)")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--restore":
        restore_strict_mode()
    else:
        enable_grid_test_mode()
