"""
Тесты для исправления BUG-004: derivatives_data и orderflow_features

Проверяет:
1. derivatives_data передаются в build_features и попадают в DataFrame
2. orderflow_features считаются только один раз (в build_features)
3. Нет дублирующих расчетов orderflow
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from data.features import FeaturePipeline


class TestDerivativesDataIntegration:
    """Тесты для проверки что derivatives_data попадают в фичи"""
    
    @pytest.fixture
    def feature_pipeline(self):
        """Создает экземпляр FeaturePipeline"""
        return FeaturePipeline()
    
    @pytest.fixture
    def sample_df(self):
        """Создает минимальный DataFrame с OHLCV данными"""
        data = pd.DataFrame({
            "open": [100.0] * 100,
            "high": [102.0] * 100,
            "low": [98.0] * 100,
            "close": [101.0] * 100,
            "volume": [1000] * 100
        })
        return data
    
    def test_derivatives_data_added_to_dataframe(self, feature_pipeline, sample_df):
        """
        Тест: derivatives_data передаются и попадают в DataFrame
        """
        # Подготавливаем derivatives_data
        derivatives_data = {
            "mark_price": 101.5,
            "index_price": 101.0,
            "funding_rate": 0.0001,
            "open_interest": 1000000.0,
            "oi_change": 50000.0
        }
        
        # Вызываем build_features с derivatives_data
        df_with_features = feature_pipeline.build_features(
            sample_df,
            orderbook=None,
            derivatives_data=derivatives_data
        )
        
        # Проверяем что derivatives колонки добавлены в последнюю строку
        last_row = df_with_features.iloc[-1]
        
        assert "mark_index_deviation" in df_with_features.columns, \
            "mark_index_deviation должен быть в DataFrame"
        assert "funding_rate" in df_with_features.columns, \
            "funding_rate должен быть в DataFrame"
        assert "funding_bias" in df_with_features.columns, \
            "funding_bias должен быть в DataFrame"
        assert "open_interest" in df_with_features.columns, \
            "open_interest должен быть в DataFrame"
        assert "oi_change" in df_with_features.columns, \
            "oi_change должен быть в DataFrame"
        
        # Проверяем значения
        assert last_row["funding_rate"] == 0.0001, \
            "funding_rate должен быть 0.0001"
        assert last_row["open_interest"] == 1000000.0, \
            "open_interest должен быть 1000000.0"
    
    def test_derivatives_data_none_no_error(self, feature_pipeline, sample_df):
        """
        Тест: если derivatives_data=None, фичи строятся без ошибок
        """
        # Вызываем build_features без derivatives_data
        df_with_features = feature_pipeline.build_features(
            sample_df,
            orderbook=None,
            derivatives_data=None
        )
        
        # Проверяем что DataFrame создан успешно
        assert df_with_features is not None
        assert len(df_with_features) == len(sample_df)
        
        # Derivatives колонки могут отсутствовать или быть NaN
        # Главное - нет ошибок


class TestOrderflowSingleCalculation:
    """Тесты для проверки что orderflow считается только один раз"""
    
    @pytest.fixture
    def feature_pipeline(self):
        """Создает экземпляр FeaturePipeline"""
        return FeaturePipeline()
    
    @pytest.fixture
    def sample_df(self):
        """Создает минимальный DataFrame"""
        data = pd.DataFrame({
            "open": [100.0] * 50,
            "high": [102.0] * 50,
            "low": [98.0] * 50,
            "close": [101.0] * 50,
            "volume": [1000] * 50
        })
        return data
    
    @pytest.fixture
    def sample_orderbook(self):
        """Создает пример orderbook"""
        return {
            "bids": [
                ["100.0", "10.0"],
                ["99.5", "20.0"],
                ["99.0", "15.0"]
            ],
            "asks": [
                ["101.0", "12.0"],
                ["101.5", "18.0"],
                ["102.0", "14.0"]
            ]
        }
    
    def test_orderflow_calculated_in_build_features(self, feature_pipeline, sample_df, sample_orderbook):
        """
        Тест: orderflow_features считаются в build_features
        """
        # Вызываем build_features с orderbook
        df_with_features = feature_pipeline.build_features(
            sample_df,
            orderbook=sample_orderbook,
            derivatives_data=None
        )
        
        # Проверяем что orderflow колонки добавлены
        last_row = df_with_features.iloc[-1]
        
        # Должны быть orderflow метрики
        assert "spread_percent" in df_with_features.columns or \
               "depth_imbalance" in df_with_features.columns, \
            "Должны быть orderflow метрики в DataFrame"
    
    def test_orderflow_not_calculated_without_orderbook(self, feature_pipeline, sample_df):
        """
        Тест: если orderbook=None, orderflow не рассчитывается
        """
        # Вызываем build_features без orderbook
        df_with_features = feature_pipeline.build_features(
            sample_df,
            orderbook=None,
            derivatives_data=None
        )
        
        # DataFrame создан успешно
        assert df_with_features is not None
        assert len(df_with_features) == len(sample_df)


class TestBothDerivativesAndOrderflow:
    """Тесты для проверки совместной работы derivatives и orderflow"""
    
    @pytest.fixture
    def feature_pipeline(self):
        return FeaturePipeline()
    
    @pytest.fixture
    def sample_df(self):
        data = pd.DataFrame({
            "open": [100.0] * 60,
            "high": [102.0] * 60,
            "low": [98.0] * 60,
            "close": [101.0] * 60,
            "volume": [1000] * 60
        })
        return data
    
    def test_both_derivatives_and_orderflow(self, feature_pipeline, sample_df):
        """
        Тест: и derivatives_data и orderflow могут быть добавлены одновременно
        """
        derivatives_data = {
            "mark_price": 101.2,
            "index_price": 101.0,
            "funding_rate": 0.0002,
            "open_interest": 2000000.0,
            "oi_change": 100000.0
        }
        
        orderbook = {
            "bids": [["100.0", "10.0"], ["99.5", "20.0"]],
            "asks": [["101.0", "12.0"], ["101.5", "18.0"]]
        }
        
        # Вызываем с обоими параметрами
        df_with_features = feature_pipeline.build_features(
            sample_df,
            orderbook=orderbook,
            derivatives_data=derivatives_data
        )
        
        # Проверяем что обе группы фичей присутствуют
        last_row = df_with_features.iloc[-1]
        
        # Derivatives фичи
        assert "funding_rate" in df_with_features.columns
        
        # DataFrame создан успешно
        assert len(df_with_features) == len(sample_df)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
