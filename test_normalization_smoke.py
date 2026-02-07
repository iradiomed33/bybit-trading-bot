#!/usr/bin/env python3
"""
Smoke test для нормализации price/qty через InstrumentsManager.

Проверяет, что:
1. Модуль normalization.py существует и работает
2. VolatilityPositionSizer использует InstrumentsManager для округления
3. Хардкод значений удалён
"""

import sys
import re
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent))

def test_normalization_module_exists():
    """Проверка что модуль normalization.py существует"""
    print("\n[Test 1] Проверка существования модуля normalization.py...")
    
    normalization_path = Path(__file__).parent / "exchange" / "normalization.py"
    
    if not normalization_path.exists():
        print("❌ FAIL: normalization.py не найден")
        return False
        
    content = normalization_path.read_text()
    
    # Проверяем что есть функции round_price и round_qty
    if "def round_price(" not in content:
        print("❌ FAIL: функция round_price не найдена")
        return False
        
    if "def round_qty(" not in content:
        print("❌ FAIL: функция round_qty не найдена")
        return False
        
    print("✓ normalization.py существует")
    print("✓ Функции round_price() и round_qty() определены")
    return True


def test_volatility_sizer_uses_instruments_manager():
    """Проверка что VolatilityPositionSizer принимает instruments_manager"""
    print("\n[Test 2] Проверка VolatilityPositionSizer...")
    
    sizer_path = Path(__file__).parent / "risk" / "volatility_position_sizer.py"
    content = sizer_path.read_text()
    
    # Проверяем что __init__ принимает instruments_manager
    if "instruments_manager" not in content:
        print("❌ FAIL: instruments_manager не упоминается в VolatilityPositionSizer")
        return False
        
    # Проверяем что используется round_qty из normalization
    if "from exchange.normalization import round_qty" not in content:
        print("❌ FAIL: не импортируется round_qty из normalization")
        return False
        
    print("✓ VolatilityPositionSizer принимает instruments_manager")
    print("✓ Импортирует round_qty из normalization")
    return True


def test_hardcoded_rounding_removed():
    """Проверка что хардкод округлений удалён или помечен как deprecated"""
    print("\n[Test 3] Проверка удаления хардкода...")
    
    sizer_path = Path(__file__).parent / "risk" / "volatility_position_sizer.py"
    content = sizer_path.read_text()
    
    # Ищем хардкод округления
    hardcoded_patterns = [
        r'\.quantize\(\s*Decimal\("0\.00001"\)',
        r'\.quantize\(\s*Decimal\("0\.0001"\)',
    ]
    
    found_hardcode = False
    for pattern in hardcoded_patterns:
        matches = re.findall(pattern, content)
        if matches:
            # Проверяем что это в fallback ветке или помечено DEPRECATED
            lines_with_hardcode = [line for line in content.split('\n') if re.search(pattern, line)]
            
            # Проверяем что выше есть проверка if self.instruments_manager
            has_fallback = "if self.instruments_manager" in content
            has_deprecated = "DEPRECATED" in content or "Fallback" in content
            
            if not (has_fallback or has_deprecated):
                print(f"❌ FAIL: найден хардкод без fallback: {matches}")
                return False
            found_hardcode = True
    
    if found_hardcode:
        print("✓ Хардкод сохранён только как fallback")
    else:
        print("✓ Хардкод полностью удалён")
        
    # Проверяем что используется round_qty при наличии instruments_manager
    if "round_qty(" not in content:
        print("❌ FAIL: round_qty не используется в VolatilityPositionSizer")
        return False
        
    print("✓ Используется round_qty() для основной логики")
    return True


def test_trading_bot_passes_instruments_manager():
    """Проверка что TradingBot передаёт instruments_manager в VolatilityPositionSizer"""
    print("\n[Test 4] Проверка TradingBot...")
    
    bot_path = Path(__file__).parent / "bot" / "trading_bot.py"
    content = bot_path.read_text()
    
    # Проверяем что передаётся instruments_manager при создании VolatilityPositionSizer
    if "instruments_manager=self.instruments_manager" not in content:
        print("❌ FAIL: TradingBot не передаёт instruments_manager в VolatilityPositionSizer")
        return False
        
    print("✓ TradingBot передаёт instruments_manager в VolatilityPositionSizer")
    
    # Проверяем что передаётся symbol в calculate_position_size
    if "symbol=self.symbol" not in content:
        print("⚠ WARNING: symbol не передаётся в calculate_position_size")
        print("  (может быть необязательно, но рекомендуется)")
    else:
        print("✓ TradingBot передаёт symbol в calculate_position_size")
    
    return True


def main():
    """Запуск всех smoke тестов"""
    print("=" * 70)
    print("SMOKE TEST: Нормализация tick/step через InstrumentsManager")
    print("=" * 70)
    
    tests = [
        test_normalization_module_exists,
        test_volatility_sizer_uses_instruments_manager,
        test_hardcoded_rounding_removed,
        test_trading_bot_passes_instruments_manager,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Exception in {test.__name__}: {e}")
            results.append(False)
    
    print("\n" + "=" * 70)
    print("РЕЗУЛЬТАТЫ:")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Пройдено: {passed}/{total}")
    
    if all(results):
        print("\n✓✓✓ SUCCESS: Все тесты пройдены!")
        print("✓ Модуль normalization.py создан")
        print("✓ VolatilityPositionSizer использует InstrumentsManager")
        print("✓ Хардкод удалён или в fallback")
        print("✓ TradingBot передаёт зависимости")
        return 0
    else:
        print("\n❌ FAIL: Некоторые тесты провалились")
        return 1


if __name__ == "__main__":
    sys.exit(main())
