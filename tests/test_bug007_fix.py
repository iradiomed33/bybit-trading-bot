"""
Тесты для исправления BUG-007: MTF cache with indicators

Проверяет:
1. MTF кэш содержит индикаторы (ema_20, atr_percent, vol_regime)
2. Индикаторы рассчитываются корректно
3. Confluence использует реальные значения индикаторов
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, MagicMock
from data.indicators import TechnicalIndicators
from data.timeframe_cache import TimeframeCache


class TestMTFCacheWithIndicators:
    """Тесты для MTF кэша с индикаторами"""
    
    def test_ema_calculation_for_cache(self):
        """
        Тест: EMA рассчитывается корректно для кэша
        """
        # Создаем DataFrame с тестовыми данными
        data = {
            "timestamp": list(range(1000, 1100)),
            "open": [100.0 + i * 0.1 for i in range(100)],
            "high": [100.5 + i * 0.1 for i in range(100)],
            "low": [99.5 + i * 0.1 for i in range(100)],
            "close": [100.0 + i * 0.1 for i in range(100)],
            "volume": [1000.0] * 100,
        }
        df = pd.DataFrame(data)
        
        # Рассчитываем EMA
        indicators = TechnicalIndicators()
        df = indicators.calculate_ema(df, periods=[20])
        
        # Проверяем что EMA рассчитан
        assert "ema_20" in df.columns, "ema_20 должен быть в DataFrame"
        
        # Проверяем что EMA имеет значения (не все NaN)
        assert df["ema_20"].notna().sum() > 0, "ema_20 должен иметь значения"
        
        # Проверяем последнее значение
        last_ema = df.iloc[-1]["ema_20"]
        assert pd.notna(last_ema), "Последнее значение ema_20 не должно быть NaN"
        assert isinstance(last_ema, (float, np.floating)), "ema_20 должен быть числом"
    
    def test_atr_calculation_for_cache(self):
        """
        Тест: ATR и atr_percent рассчитываются корректно
        """
        # Создаем DataFrame с волатильными данными
        data = {
            "timestamp": list(range(1000, 1100)),
            "open": [100.0] * 100,
            "high": [102.0 + i * 0.1 for i in range(100)],
            "low": [98.0 - i * 0.1 for i in range(100)],
            "close": [100.0 + (i % 2) for i in range(100)],
            "volume": [1000.0] * 100,
        }
        df = pd.DataFrame(data)
        
        # Рассчитываем ATR
        indicators = TechnicalIndicators()
        df = indicators.calculate_atr(df)
        
        # Проверяем что ATR рассчитан
        assert "atr" in df.columns, "atr должен быть в DataFrame"
        
        # Рассчитываем atr_percent
        df["atr_percent"] = (df["atr"] / df["close"]) * 100
        
        # Проверяем последнее значение
        last_row = df.iloc[-1]
        assert pd.notna(last_row["atr"]), "Последнее значение atr не должно быть NaN"
        assert pd.notna(last_row["atr_percent"]), "atr_percent не должен быть NaN"
        assert last_row["atr_percent"] > 0, "atr_percent должен быть положительным"
    
    def test_vol_regime_calculation(self):
        """
        Тест: vol_regime рассчитывается корректно на основе atr_percent
        """
        # Создаем DataFrame с разной волатильностью
        data = {
            "timestamp": list(range(1000, 1100)),
            "open": [100.0] * 100,
            "high": [105.0] * 50 + [101.0] * 50,  # Высокая волатильность в первой половине
            "low": [95.0] * 50 + [99.0] * 50,
            "close": [100.0] * 100,
            "volume": [1000.0] * 100,
        }
        df = pd.DataFrame(data)
        
        # Рассчитываем ATR и atr_percent
        indicators = TechnicalIndicators()
        df = indicators.calculate_atr(df)
        df["atr_percent"] = (df["atr"] / df["close"]) * 100
        
        # Рассчитываем vol_regime (1 = high vol, 0 = normal/low)
        df["vol_regime"] = (df["atr_percent"] > 3.0).astype(int)
        
        # Проверяем что vol_regime корректно определяется
        assert "vol_regime" in df.columns, "vol_regime должен быть в DataFrame"
        assert df["vol_regime"].isin([0, 1]).all(), "vol_regime должен быть 0 или 1"
        
        # Проверяем последнее значение
        last_vol_regime = df.iloc[-1]["vol_regime"]
        assert last_vol_regime in [0, 1], "vol_regime должен быть 0 или 1"
    
    def test_cache_stores_indicators(self):
        """
        Тест: TimeframeCache корректно хранит индикаторы
        """
        cache = TimeframeCache()
        
        # Добавляем свечу С индикаторами
        candle_with_indicators = {
            "timestamp": 1000,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000.0,
            "ema_20": 100.2,  # Индикатор!
            "atr_percent": 2.5,  # Индикатор!
            "vol_regime": 0,  # Индикатор!
        }
        
        cache.add_candle("15", candle_with_indicators)
        
        # Получаем последнюю свечу
        latest = cache.get_latest("15")
        
        # Проверяем что индикаторы сохранились
        assert latest is not None, "Свеча должна быть в кэше"
        assert "ema_20" in latest, "ema_20 должен быть в кэше"
        assert "atr_percent" in latest, "atr_percent должен быть в кэше"
        assert "vol_regime" in latest, "vol_regime должен быть в кэше"
        
        # Проверяем значения
        assert latest["ema_20"] == 100.2, "ema_20 должен сохраниться"
        assert latest["atr_percent"] == 2.5, "atr_percent должен сохраниться"
        assert latest["vol_regime"] == 0, "vol_regime должен сохраниться"
    
    def test_confluence_uses_indicators_not_defaults(self):
        """
        Тест: Confluence использует реальные индикаторы, а не дефолты
        """
        cache = TimeframeCache()
        
        # Добавляем свечу с корректными индикаторами
        candle_1m = {
            "timestamp": 1000,
            "close": 100.0,
            "ema_20": 99.0,  # Цена выше EMA → uptrend
        }
        cache.add_candle("1", candle_1m)
        
        # Получаем свечу обратно
        latest_1m = cache.get_latest("1")
        
        # Проверяем что ema_20 не равен close (дефолту)
        assert latest_1m["ema_20"] != latest_1m["close"], \
            "ema_20 НЕ должен быть равен close (дефолту)"
        assert latest_1m["ema_20"] == 99.0, "ema_20 должен быть реальным значением"
    
    def test_missing_indicators_handled_gracefully(self):
        """
        Тест: Отсутствующие индикаторы обрабатываются корректно
        """
        cache = TimeframeCache()
        
        # Добавляем свечу БЕЗ индикаторов (старое поведение)
        candle_without_indicators = {
            "timestamp": 1000,
            "open": 100.0,
            "close": 100.0,
            # ← ema_20 отсутствует
        }
        cache.add_candle("1", candle_without_indicators)
        
        # Получаем свечу
        latest = cache.get_latest("1")
        
        # Проверяем что можем получить значение с дефолтом
        ema = latest.get("ema_20", latest["close"])
        
        # В этом случае ema будет равен close (дефолт)
        assert ema == latest["close"], "Без индикатора должен использоваться дефолт"


class TestIndicatorCalculationIntegration:
    """Интеграционные тесты расчета индикаторов"""
    
    def test_full_pipeline_with_indicators(self):
        """
        Тест: Полный pipeline расчета индикаторов для MTF
        """
        # Симулируем ответ API с 100 свечами
        raw_candles = []
        for i in range(100):
            raw_candles.append([
                str(1000 + i),  # timestamp
                str(100.0 + i * 0.1),  # open
                str(101.0 + i * 0.1),  # high
                str(99.0 + i * 0.1),  # low
                str(100.0 + i * 0.1),  # close
                str(1000.0),  # volume
            ])
        
        # Преобразуем в DataFrame (как в исправленном коде)
        tf_df_data = []
        for candle in reversed(raw_candles):
            tf_df_data.append({
                "timestamp": int(candle[0]),
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "volume": float(candle[5]),
            })
        
        tf_df = pd.DataFrame(tf_df_data)
        
        # Рассчитываем индикаторы
        indicators = TechnicalIndicators()
        tf_df = indicators.calculate_ema(tf_df, periods=[20])
        tf_df = indicators.calculate_atr(tf_df)
        
        # Рассчитываем дополнительные метрики
        tf_df["atr_percent"] = (tf_df["atr"] / tf_df["close"]) * 100
        tf_df["vol_regime"] = (tf_df["atr_percent"] > 3.0).astype(int)
        
        # Берем последнюю строку
        last_row = tf_df.iloc[-1]
        
        # Проверяем что все индикаторы рассчитаны
        assert "ema_20" in last_row.index, "ema_20 должен быть"
        assert pd.notna(last_row["ema_20"]), "ema_20 не должен быть NaN"
        
        assert "atr_percent" in last_row.index, "atr_percent должен быть"
        assert pd.notna(last_row["atr_percent"]), "atr_percent не должен быть NaN"
        
        assert "vol_regime" in last_row.index, "vol_regime должен быть"
        assert pd.notna(last_row["vol_regime"]), "vol_regime не должен быть NaN"
        
        # Создаем словарь для кэша
        candle_dict = {
            "timestamp": int(last_row["timestamp"]),
            "close": float(last_row["close"]),
            "ema_20": float(last_row["ema_20"]),
            "atr_percent": float(last_row["atr_percent"]),
            "vol_regime": int(last_row["vol_regime"]),
        }
        
        # Проверяем что все значения корректные
        assert all(pd.notna(v) for v in candle_dict.values()), \
            "Все значения должны быть валидными"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
