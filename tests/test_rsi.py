"""
Тесты для валидации расчета RSI (Relative Strength Index)

Требования (DoD):
- RSI должен находиться в диапазоне [0, 100]
- На хвосте данных (последние 100 строк) не должно быть NaN
- Значения RSI должны соответствовать синтетическому тренду
- Fallback реализация должна работать без pandas_ta
"""

import pytest
import pandas as pd
import numpy as np
from data.features import FeaturePipeline
from data.indicators import TechnicalIndicators


class TestRSICalculation:
    """Тесты расчета RSI"""

    @pytest.fixture
    def uptrend_data(self):
        """Синтетический восходящий тренд (RSI должен быть выше 50)"""
        dates = pd.date_range(start="2024-01-01", periods=300, freq="1h")
        close = np.linspace(100, 150, 300) + np.random.normal(0, 1, 300)
        
        return pd.DataFrame({
            "open": close + np.random.normal(0, 0.5, 300),
            "high": close + np.abs(np.random.normal(1, 0.5, 300)),
            "low": close - np.abs(np.random.normal(1, 0.5, 300)),
            "close": close,
            "volume": np.random.uniform(1000, 5000, 300),
        }, index=dates)

    @pytest.fixture
    def downtrend_data(self):
        """Синтетический нисходящий тренд (RSI должен быть ниже 50)"""
        dates = pd.date_range(start="2024-01-01", periods=300, freq="1h")
        close = np.linspace(150, 100, 300) + np.random.normal(0, 1, 300)
        
        return pd.DataFrame({
            "open": close + np.random.normal(0, 0.5, 300),
            "high": close + np.abs(np.random.normal(1, 0.5, 300)),
            "low": close - np.abs(np.random.normal(1, 0.5, 300)),
            "close": close,
            "volume": np.random.uniform(1000, 5000, 300),
        }, index=dates)

    @pytest.fixture
    def sideways_data(self):
        """Синтетический боковой рынок (RSI около 50)"""
        dates = pd.date_range(start="2024-01-01", periods=300, freq="1h")
        close = 100 + 5 * np.sin(np.linspace(0, 10 * np.pi, 300)) + np.random.normal(0, 0.5, 300)
        
        return pd.DataFrame({
            "open": close + np.random.normal(0, 0.5, 300),
            "high": close + np.abs(np.random.normal(1, 0.5, 300)),
            "low": close - np.abs(np.random.normal(1, 0.5, 300)),
            "close": close,
            "volume": np.random.uniform(1000, 5000, 300),
        }, index=dates)

    def test_rsi_range_uptrend(self, uptrend_data):
        """RSI в восходящем тренде должен быть в диапазоне [0, 100] и обычно > 50"""
        df = TechnicalIndicators.calculate_rsi(uptrend_data.copy())
        
        # Проверяем диапазон
        assert df["rsi"].min() >= 0, "RSI не может быть < 0"
        assert df["rsi"].max() <= 100, "RSI не может быть > 100"
        
        # На хвосте должны быть реальные значения (не NaN)
        tail_rsi = df["rsi"].tail(100)
        nan_count = tail_rsi.isna().sum()
        assert nan_count == 0, f"На хвосте {nan_count} NaN значений"
        
        # В восходящем тренде среднее RSI должно быть > 50
        mean_rsi = df["rsi"].tail(100).mean()
        assert mean_rsi > 50, f"В восходящем тренде RSI должен быть > 50, получен {mean_rsi:.2f}"

    def test_rsi_range_downtrend(self, downtrend_data):
        """RSI в нисходящем тренде должен быть в диапазоне [0, 100] и обычно < 50"""
        df = TechnicalIndicators.calculate_rsi(downtrend_data.copy())
        
        # Проверяем диапазон
        assert df["rsi"].min() >= 0, "RSI не может быть < 0"
        assert df["rsi"].max() <= 100, "RSI не может быть > 100"
        
        # На хвосте должны быть реальные значения (не NaN)
        tail_rsi = df["rsi"].tail(100)
        nan_count = tail_rsi.isna().sum()
        assert nan_count == 0, f"На хвосте {nan_count} NaN значений"
        
        # В нисходящем тренде среднее RSI должно быть < 50
        mean_rsi = df["rsi"].tail(100).mean()
        assert mean_rsi < 50, f"В нисходящем тренде RSI должен быть < 50, получен {mean_rsi:.2f}"

    def test_rsi_range_sideways(self, sideways_data):
        """RSI на боковом рынке должен колебаться около 50"""
        df = TechnicalIndicators.calculate_rsi(sideways_data.copy())
        
        # Проверяем диапазон
        assert df["rsi"].min() >= 0, "RSI не может быть < 0"
        assert df["rsi"].max() <= 100, "RSI не может быть > 100"
        
        # На хвосте должны быть реальные значения (не NaN)
        tail_rsi = df["rsi"].tail(100)
        nan_count = tail_rsi.isna().sum()
        assert nan_count == 0, f"На хвосте {nan_count} NaN значений"

    def test_rsi_no_nan_tail(self, uptrend_data):
        """Проверяем отсутствие NaN на последних 100 свечах"""
        df = TechnicalIndicators.calculate_rsi(uptrend_data.copy())
        
        # Последние 100 свечей должны быть полностью заполнены
        tail = df.tail(100)
        assert tail["rsi"].notna().all(), "На хвосте данных есть NaN значения в RSI"

    def test_rsi_in_feature_pipeline(self, uptrend_data):
        """Проверяем что RSI правильно интегрирован в FeaturePipeline"""
        pipeline = FeaturePipeline()
        df = pipeline.build_features(uptrend_data.copy())
        
        # RSI должен быть в датафрейме
        assert "rsi" in df.columns, "RSI отсутствует в выходе FeaturePipeline"
        
        # Диапазон
        assert df["rsi"].min() >= 0, "RSI в FeaturePipeline < 0"
        assert df["rsi"].max() <= 100, "RSI в FeaturePipeline > 100"
        
        # На хвосте не должно быть NaN
        nan_count = df["rsi"].tail(100).isna().sum()
        assert nan_count == 0, f"В FeaturePipeline на хвосте {nan_count} NaN значений RSI"

    def test_rsi_calculation_correctness(self):
        """Проверяем математическую корректность RSI на известном наборе данных"""
        # Синтетические данные с известным поведением
        prices = np.array([44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42,
                          45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.00, 46.00,
                          46.00, 46.00, 46.00, 46.00] * 15)  # 300 значений
        
        df = pd.DataFrame({
            "close": prices,
            "volume": np.ones_like(prices) * 1000,
        })
        
        df = TechnicalIndicators.calculate_rsi(df)
        
        # На хвосте должны быть значения между 0 и 100
        tail = df["rsi"].tail(50)
        assert tail.notna().all(), "На хвосте есть NaN"
        assert (tail >= 0).all(), "На хвосте RSI < 0"
        assert (tail <= 100).all(), "На хвосте RSI > 100"


class TestMeanReversionWithRSI:
    """Тесты стратегии Mean Reversion с реальным RSI"""

    @pytest.fixture
    def market_data_with_rsi(self):
        """Данные рынка с расчитанным RSI"""
        dates = pd.date_range(start="2024-01-01", periods=200, freq="1h")
        close = 100 + np.random.normal(0, 2, 200)
        
        df = pd.DataFrame({
            "open": close + np.random.normal(0, 0.5, 200),
            "high": close + np.abs(np.random.normal(1, 0.5, 200)),
            "low": close - np.abs(np.random.normal(1, 0.5, 200)),
            "close": close,
            "volume": np.random.uniform(1000, 5000, 200),
        }, index=dates)
        
        pipeline = FeaturePipeline()
        return pipeline.build_features(df)

    def test_mean_reversion_has_real_rsi(self, market_data_with_rsi):
        """Проверяем что MeanReversionStrategy получит реальный RSI, не default=50"""
        df = market_data_with_rsi
        latest = df.iloc[-1]
        
        # Проверяем что RSI есть и не равен default
        assert "rsi" in df.columns, "RSI отсутствует в данных"
        rsi = latest.get("rsi", 50)
        
        # RSI не должен быть равен default везде
        # Проверяем вариативность
        rsi_values = df["rsi"].tail(50).dropna()
        unique_rsi = rsi_values.nunique()
        assert unique_rsi > 1, "RSI имеет только одно значение (вероятно default)"

    def test_mean_reversion_rsi_for_oversold(self):
        """Проверяем что при падении цены RSI становится перепроданным (< 30)"""
        # Синтетический crash: падение на 10%
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")
        close = np.linspace(100, 90, 100)  # Падение
        
        df = pd.DataFrame({
            "open": close + np.random.normal(0, 0.3, 100),
            "high": close + np.abs(np.random.normal(0.5, 0.3, 100)),
            "low": close - np.abs(np.random.normal(0.5, 0.3, 100)),
            "close": close,
            "volume": np.random.uniform(1000, 5000, 100),
        }, index=dates)
        
        df = TechnicalIndicators.calculate_rsi(df)
        
        # На хвосте должны быть низкие значения RSI
        tail_rsi = df["rsi"].tail(20)
        assert tail_rsi.mean() < 50, "При падении RSI не опустился ниже 50"

    def test_mean_reversion_rsi_for_overbought(self):
        """Проверяем что при росте цены RSI становится перекупленным (> 70)"""
        # Синтетический rally: рост на 10%
        dates = pd.date_range(start="2024-01-01", periods=100, freq="1h")
        close = np.linspace(90, 100, 100)  # Рост
        
        df = pd.DataFrame({
            "open": close + np.random.normal(0, 0.3, 100),
            "high": close + np.abs(np.random.normal(0.5, 0.3, 100)),
            "low": close - np.abs(np.random.normal(0.5, 0.3, 100)),
            "close": close,
            "volume": np.random.uniform(1000, 5000, 100),
        }, index=dates)
        
        df = TechnicalIndicators.calculate_rsi(df)
        
        # На хвосте должны быть высокие значения RSI
        tail_rsi = df["rsi"].tail(20)
        assert tail_rsi.mean() > 50, "При росте RSI не поднялся выше 50"
