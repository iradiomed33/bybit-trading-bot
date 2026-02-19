#!/usr/bin/env python3
"""
Проверяет соответствие bot_settings.json с параметрами, которые реально читает StrategyBuilder.
"""
import json
import sys

CONFIG_PATH = "config/bot_settings.json"

# Параметры, которые РЕАЛЬНО читает StrategyBuilder
EXPECTED_PARAMS = {
    "TrendPullback": {
        "required": [
            "min_adx",
            "pullback_percent",
            "enable_liquidation_filter",
            "liquidation_cooldown_bars",
            "liquidation_atr_multiplier",
            "liquidation_wick_ratio",
            "liquidation_volume_pctl",
            "entry_mode",
            "limit_ttl_bars",
            "entry_zone_atr_low",
            "entry_zone_atr_high",
            "volume_z_threshold",
        ],
        "meta": ["confidence_threshold", "min_candles", "lookback"],
        "ignored": []
    },
    "Breakout": {
        "required": [
            "bb_width_threshold",
            "min_volume_zscore",
            "min_atr_percent_expansion",
            "breakout_entry",
            "retest_ttl_bars",
            "require_squeeze",
            "require_expansion",
            "require_volume",
        ],
        "meta": ["confidence_threshold", "min_candles"],
        "ignored": ["lookback", "breakout_percent"]  # ← НЕ ИСПОЛЬЗУЮТСЯ!
    },
    "MeanReversion": {
        "required": [
            "vwap_distance_threshold",
            "rsi_oversold",
            "rsi_overbought",
            "max_adx_for_entry",
            "require_range_regime",
            "enable_anti_knife",
            "adx_spike_threshold",
            "atr_spike_threshold",
            "max_hold_bars",
            "stop_loss_atr_multiplier",
        ],
        "meta": ["confidence_threshold", "min_candles"],
        "ignored": ["lookback", "std_dev_threshold"]  # ← НЕ ИСПОЛЬЗУЮТСЯ!
    },
    "GridTrading": {
        "required": [
            "range_mode",
            "range_lookback",
            "grid_levels",
            "grid_spacing_percent",
            "require_ranging_market",
            "max_adx_for_range",
            "min_bb_width",
            "max_bb_width",
            "enable_breakout_protection",
            "breakout_volume_threshold",
            "stop_loss_atr_multiplier",
            "profit_per_grid",
            "max_grid_positions",
            "rebalance_on_drift",
            "drift_threshold_percent",
        ],
        "meta": ["confidence_threshold"],
        "ignored": []
    }
}

def check_config():
    """Проверяет корректность конфига"""
    
    print("🔍 Проверка конфигурации strategy параметров\n")
    print("="*70)
    
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"❌ Файл не найден: {CONFIG_PATH}")
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON: {e}")
        return 1
    
    strategies_config = config.get("strategies", {})
    
    total_issues = 0
    
    for strategy_name, expected in EXPECTED_PARAMS.items():
        print(f"\n📊 {strategy_name}")
        print("-"*70)
        
        if strategy_name not in strategies_config:
            print(f"  ⚠️  Стратегия отсутствует в конфиге!")
            total_issues += 1
            continue
        
        strategy_config = strategies_config[strategy_name]
        config_keys = set(strategy_config.keys()) - {"enabled", "comment", "_comment", "_removed"}
        
        required_keys = set(expected["required"])
        meta_keys = set(expected["meta"])
        ignored_keys = set(expected["ignored"])
        
        # Проверяем обязательные параметры
        missing_required = required_keys - config_keys
        if missing_required:
            print(f"  ❌ ОТСУТСТВУЮТ обязательные параметры ({len(missing_required)}):")
            for key in sorted(missing_required):
                print(f"     • {key}")
            total_issues += len(missing_required)
        
        # Проверяем мета параметры
        missing_meta = meta_keys - config_keys
        if missing_meta:
            print(f"  ⚠️  ОТСУТСТВУЮТ мета параметры ({len(missing_meta)}):")
            for key in sorted(missing_meta):
                print(f"     • {key}")
            total_issues += len(missing_meta)
        
        # Проверяем игнорируемые параметры (есть, но не используются)
        present_ignored = ignored_keys & config_keys
        if present_ignored:
            print(f"  ⚠️  ИГНОРИРУЕМЫЕ параметры (не читаются!) ({len(present_ignored)}):")
            for key in sorted(present_ignored):
                value = strategy_config.get(key)
                print(f"     • {key}: {value}  ← НЕ ИСПОЛЬЗУЕТСЯ!")
            total_issues += len(present_ignored)
        
        # Проверяем лишние параметры
        all_expected = required_keys | meta_keys | ignored_keys
        extra_keys = config_keys - all_expected
        if extra_keys:
            print(f"  ℹ️  Дополнительные параметры ({len(extra_keys)}):")
            for key in sorted(extra_keys):
                print(f"     • {key}")
        
        # Итог по стратегии
        if not (missing_required or missing_meta or present_ignored):
            print(f"  ✅ Конфиг корректный!")
    
    print("\n" + "="*70)
    
    if total_issues == 0:
        print("✅ Конфигурация КОРРЕКТНА! Все параметры на месте.")
        return 0
    else:
        print(f"❌ Найдено {total_issues} проблем в конфигурации!")
        print("\n💡 РЕШЕНИЕ:")
        print("   1. Используй config/bot_settings_CORRECT.json")
        print("   2. Или добавь недостающие параметры из CONFIG_CRITICAL_FIX.md")
        return 1

if __name__ == "__main__":
    sys.exit(check_config())
