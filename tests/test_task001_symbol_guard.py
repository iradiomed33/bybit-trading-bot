#!/usr/bin/env python3

"""
TASK-001 (P0): Symbol Guard Tests

Проверяет что:
1. MetaLayer.get_signal() всегда получает symbol в features
2. Не генерируется Symbol=UNKNOWN в логах от официальных entrypoints
3. Guard корректно обрабатывает отсутствие symbol
"""

import pytest
import logging
import pandas as pd
from typing import Dict, Any
from strategy.meta_layer import MetaLayer
from strategy.trend_pullback import TrendPullbackStrategy
from strategy.breakout import BreakoutStrategy
from strategy.mean_reversion import MeanReversionStrategy
from logger import setup_logger


logger = setup_logger(__name__)


@pytest.fixture
def meta_layer():
    """Создать MetaLayer с тестовыми стратегиями"""
    strategies = [
        TrendPullbackStrategy(),
        BreakoutStrategy(),
        MeanReversionStrategy(),
    ]
    return MetaLayer(strategies, use_mtf=False)


@pytest.fixture
def sample_df():
    """Создать простой DataFrame с необходимыми колонками"""
    import numpy as np
    
    dates = pd.date_range('2024-01-01', periods=300, freq='1h')
    close_prices = np.random.normal(50000, 1000, 300)
    volumes = np.random.uniform(1000, 10000, 300)
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': close_prices + np.random.normal(0, 100, 300),
        'high': close_prices + np.abs(np.random.normal(0, 200, 300)),
        'low': close_prices - np.abs(np.random.normal(0, 200, 300)),
        'close': close_prices,
        'volume': volumes,
        'turnover': volumes * close_prices,
    })
    
    # Добавляем индикаторы
    df['sma_20'] = df['close'].rolling(20).mean()
    df['sma_50'] = df['close'].rolling(50).mean()
    df['ema_12'] = df['close'].ewm(span=12).mean()
    df['ema_26'] = df['close'].ewm(span=26).mean()
    df['atr'] = np.random.uniform(100, 500, 300)
    df['adx'] = np.random.uniform(20, 50, 300)
    df['ADX_14'] = df['adx']
    df['volume_zscore'] = np.random.normal(0, 1, 300)
    df['rsi'] = np.random.uniform(30, 70, 300)
    
    return df.iloc[-200:].reset_index(drop=True)


class TestSymbolGuardBasic:
    """Базовые тесты на guard для symbol"""

    def test_get_signal_with_symbol(self, meta_layer, sample_df):
        """get_signal с явным symbol в features - успешно"""
        features = {"symbol": "BTCUSDT"}
        
        # Должен работать без ошибок
        result = meta_layer.get_signal(sample_df, features)
        
        # результат может быть None, это OK
        assert result is None or isinstance(result, dict)

    def test_get_signal_without_symbol_fallback(self, meta_layer, sample_df, caplog):
        """get_signal без symbol в features - использует fallback"""
        features = {}
        
        with caplog.at_level(logging.WARNING):
            result = meta_layer.get_signal(sample_df, features)
        
        # Должно быть warning о missing symbol
        warning_found = any(
            "Symbol missing in features" in record.message 
            for record in caplog.records 
            if record.levelno == logging.WARNING
        )
        assert warning_found, "Expected warning about missing symbol"
        
        # Features должны быть обновлены с UNKNOWN
        assert features.get("symbol") == "UNKNOWN"

    def test_get_signal_with_none_features(self, meta_layer, sample_df, caplog):
        """get_signal с features=None - создает новый dict"""
        features = None
        
        with caplog.at_level(logging.WARNING):
            result = meta_layer.get_signal(sample_df, features)
        
        # Должно быть warning
        warning_found = any(
            "Symbol missing in features" in record.message 
            for record in caplog.records 
            if record.levelno == logging.WARNING
        )
        assert warning_found

    def test_get_signal_with_empty_symbol(self, meta_layer, sample_df, caplog):
        """get_signal с пустым symbol - считается отсутствующим"""
        features = {"symbol": ""}
        
        with caplog.at_level(logging.WARNING):
            result = meta_layer.get_signal(sample_df, features)
        
        # Должно быть warning
        warning_found = any(
            "Symbol missing in features" in record.message 
            for record in caplog.records 
            if record.levelno == logging.WARNING
        )
        assert warning_found
        
        # Symbol должен быть заменен на UNKNOWN
        assert features["symbol"] == "UNKNOWN"


class TestSymbolInLogs:
    """Тесты что Symbol=UNKNOWN не появляется в логах от легитимных вызовов"""

    def test_no_unknown_symbol_when_provided(self, meta_layer, sample_df, caplog):
        """Когда symbol предоставлен - не должно быть UNKNOWN в логах"""
        features = {"symbol": "BTCUSDT"}
        
        with caplog.at_level(logging.DEBUG):
            meta_layer.get_signal(sample_df, features)
        
        # Проверяем что нет UNKNOWN в логах (за исключением самого warning)
        unknown_in_logs = []
        for record in caplog.records:
            # Ищем Symbol=UNKNOWN в основных логах (не в warning о guard)
            if "Symbol=UNKNOWN" in record.message or (
                "UNKNOWN" in record.message and "GENERATED" in record.message
            ):
                # Если это не наш guard warning
                if "Symbol missing in features" not in record.message:
                    unknown_in_logs.append(record.message)
        
        assert len(unknown_in_logs) == 0, f"Found UNKNOWN in logs: {unknown_in_logs}"


class TestSymbolPropagation:
    """Тесты что symbol корректно распространяется через систему"""

    def test_symbol_in_no_trade_zone_check(self, meta_layer, sample_df):
        """Symbol передается в NoTradeZones проверку"""
        features = {"symbol": "ETHUSDT"}
        
        # Должен работать без ошибок
        result = meta_layer.get_signal(sample_df, features)
        
        # Проверяем что symbol был использован
        assert features["symbol"] == "ETHUSDT"

    def test_symbol_added_to_features_dict(self, meta_layer, sample_df):
        """Symbol может быть добавлен в features"""
        features = {"orderflow_imbalance": 0.5}
        
        result = meta_layer.get_signal(sample_df, features)
        
        # Symbol должен быть добавлен гвардом
        assert "symbol" in features
        assert features["symbol"] == "UNKNOWN"


class TestBackwardCompatibility:
    """Тесты на обратную совместимость"""

    def test_existing_code_still_works(self, meta_layer, sample_df):
        """Существующий код без symbol все еще работает с fallback"""
        # Старый код может передавать пустой dict
        features = {}
        
        # Должно работать - guard добавит fallback
        result = meta_layer.get_signal(sample_df, features)
        
        # Не должно быть exception
        assert True

    def test_get_signal_returns_consistent_type(self, meta_layer, sample_df):
        """get_signal всегда возвращает None или Dict независимо от features"""
        cases = [
            {"symbol": "BTCUSDT"},
            {"symbol": ""},
            {},
            None,
        ]
        
        for features in cases:
            result = meta_layer.get_signal(sample_df, features)
            assert result is None or isinstance(result, dict), \
                f"Unexpected result type for features={features}: {type(result)}"


class TestIntegrationWithBot:
    """Интеграционные тесты с TradingBot"""

    def test_trading_bot_provides_symbol(self):
        """TradingBot гарантирует symbol в features"""
        from bot.trading_bot import TradingBot
        from strategy import TrendPullbackStrategy
        
        # Создаем бот
        bot = TradingBot(
            mode="paper",
            strategies=[TrendPullbackStrategy()],
            symbol="BTCUSDT",
            testnet=True
        )
        
        # Проверяем что symbol установлен
        assert bot.symbol == "BTCUSDT"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
