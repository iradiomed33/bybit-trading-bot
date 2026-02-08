"""
Тест для проверки исправления бага с pandas rolling _window параметром.
Проверяет что все индикаторы работают корректно после исправления.
"""

import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.indicators import TechnicalIndicators
from data.indicators_fallback import TechnicalIndicators as TechnicalIndicatorsFallback
from data.indicators_new import TechnicalIndicators as TechnicalIndicatorsNew


def create_test_dataframe(rows=100):
    """Создает тестовый датафрейм с OHLCV данными"""
    np.random.seed(42)
    
    dates = pd.date_range(start='2024-01-01', periods=rows, freq='1h')
    
    # Генерируем случайные OHLCV данные
    base_price = 50000
    price_changes = np.random.randn(rows).cumsum() * 100
    closes = base_price + price_changes
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': closes + np.random.randn(rows) * 50,
        'high': closes + abs(np.random.randn(rows)) * 100,
        'low': closes - abs(np.random.randn(rows)) * 100,
        'close': closes,
        'volume': abs(np.random.randn(rows)) * 1000000 + 500000
    })
    
    # Убедимся что high >= close >= low
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    return df


def test_indicators_vwap():
    """Тест расчета VWAP индикатора"""
    print("=" * 70)
    print("Тест VWAP индикатора (indicators.py)")
    print("=" * 70)
    
    df = create_test_dataframe(100)
    
    try:
        # Тестируем TechnicalIndicators.calculate_vwap
        result = TechnicalIndicators.calculate_vwap(df.copy())
        
        # Проверяем что колонки созданы
        assert 'vwap' in result.columns, "vwap колонка должна быть создана"
        assert 'vwap_distance' in result.columns, "vwap_distance колонка должна быть создана"
        
        # Проверяем что нет NaN значений (кроме первых строк из-за rolling)
        assert not result['vwap'].iloc[20:].isna().any(), "vwap не должен содержать NaN после 20 строк"
        assert not result['vwap_distance'].iloc[20:].isna().any(), "vwap_distance не должен содержать NaN"
        
        # Проверяем что значения в разумных пределах
        assert result['vwap'].iloc[20:].min() > 0, "vwap должен быть положительным"
        assert abs(result['vwap_distance'].iloc[20:].mean()) < 100, "vwap_distance должен быть в разумных пределах"
        
        print("✅ VWAP индикатор работает корректно")
        print(f"   - vwap колонка создана, мин значение: {result['vwap'].iloc[20:].min():.2f}")
        print(f"   - vwap_distance колонка создана, среднее: {result['vwap_distance'].iloc[20:].mean():.2f}%")
        return True
        
    except Exception as e:
        print(f"❌ ОШИБКА при расчете VWAP: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_indicators_new_vwap():
    """Тест расчета VWAP индикатора (indicators_new.py)"""
    print()
    print("=" * 70)
    print("Тест VWAP индикатора (indicators_new.py)")
    print("=" * 70)
    
    df = create_test_dataframe(100)
    
    try:
        # Тестируем TechnicalIndicatorsNew.calculate_vwap
        result = TechnicalIndicatorsNew.calculate_vwap(df.copy())
        
        # Проверяем что колонки созданы
        assert 'vwap' in result.columns, "vwap колонка должна быть создана"
        assert 'vwap_distance' in result.columns, "vwap_distance колонка должна быть создана"
        
        # Проверяем что нет NaN значений
        assert not result['vwap'].iloc[20:].isna().any(), "vwap не должен содержать NaN после 20 строк"
        assert not result['vwap_distance'].iloc[20:].isna().any(), "vwap_distance не должен содержать NaN"
        
        print("✅ VWAP индикатор (new) работает корректно")
        print(f"   - vwap колонка создана, мин значение: {result['vwap'].iloc[20:].min():.2f}")
        print(f"   - vwap_distance колонка создана, среднее: {result['vwap_distance'].iloc[20:].mean():.2f}%")
        return True
        
    except Exception as e:
        print(f"❌ ОШИБКА при расчете VWAP (new): {e}")
        import traceback
        traceback.print_exc()
        return False


def test_indicators_fallback_volume():
    """Тест расчета volume индикаторов (indicators_fallback.py)"""
    print()
    print("=" * 70)
    print("Тест Volume индикаторов (indicators_fallback.py)")
    print("=" * 70)
    
    df = create_test_dataframe(100)
    
    try:
        # Тестируем TechnicalIndicatorsFallback.calculate_volume_indicators
        result = TechnicalIndicatorsFallback.calculate_volume_indicators(df.copy(), period=20)
        
        # Проверяем что колонки созданы
        assert 'volume_sma' in result.columns, "volume_sma колонка должна быть создана"
        assert 'volume_zscore' in result.columns, "volume_zscore колонка должна быть создана"
        
        # Проверяем что нет NaN значений (кроме первых строк из-за rolling)
        assert not result['volume_sma'].iloc[20:].isna().any(), "volume_sma не должен содержать NaN после 20 строк"
        assert not result['volume_zscore'].iloc[20:].isna().any(), "volume_zscore не должен содержать NaN"
        
        # Проверяем что значения в разумных пределах
        assert result['volume_sma'].iloc[20:].min() > 0, "volume_sma должен быть положительным"
        # Z-score обычно в пределах -3 до 3 для большинства данных
        assert abs(result['volume_zscore'].iloc[20:].mean()) < 5, "volume_zscore должен быть в разумных пределах"
        
        print("✅ Volume индикаторы работают корректно")
        print(f"   - volume_sma колонка создана, среднее: {result['volume_sma'].iloc[20:].mean():.2f}")
        print(f"   - volume_zscore колонка создана, среднее: {result['volume_zscore'].iloc[20:].mean():.2f}")
        return True
        
    except Exception as e:
        print(f"❌ ОШИБКА при расчете Volume индикаторов: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Запуск всех тестов"""
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "ТЕСТЫ ИСПРАВЛЕНИЯ PANDAS ROLLING BUG" + " " * 16 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    
    tests = [
        ("VWAP Индикатор (indicators.py)", test_indicators_vwap),
        ("VWAP Индикатор (indicators_new.py)", test_indicators_new_vwap),
        ("Volume Индикаторы (indicators_fallback.py)", test_indicators_fallback_volume),
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
    
    # Сводка
    print()
    print("=" * 70)
    print("СВОДКА ТЕСТОВ")
    print("=" * 70)
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nИтого: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ! Баг с pandas rolling исправлен.")
        print("\nТеперь индикаторы не будут вызывать ошибку:")
        print("  'NDFrame.rolling() got an unexpected keyword argument \"_window\"'")
        return True
    else:
        print(f"\n❌ {total - passed} тест(ов) провалились.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
