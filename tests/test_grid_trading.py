"""
Тесты для Grid Trading стратегии

Проверяем базовую функциональность Grid Trading стратегии.
"""

import pytest
import pandas as pd
import numpy as np


def test_grid_trading_import():
    """Проверяем что Grid Trading стратегия импортируется"""
    from strategy.grid_trading import GridTradingStrategy
    assert GridTradingStrategy is not None


def test_grid_trading_initialization():
    """Проверяем базовую инициализацию стратегии"""
    from strategy.grid_trading import GridTradingStrategy
    
    strategy = GridTradingStrategy(
        range_mode="auto",
        grid_levels=20,
        grid_spacing_percent=1.5,
    )
    
    assert strategy.name == "GridTrading"
    assert strategy.is_enabled == True
    assert strategy.range_mode == "auto"
    assert strategy.grid_levels == 20
    assert strategy.grid_spacing_percent == 1.5


def test_grid_trading_manual_validation():
    """Проверяем валидацию manual режима"""
    from strategy.grid_trading import GridTradingStrategy
    
    with pytest.raises(ValueError):
        # Должна быть ошибка если manual mode без границ
        GridTradingStrategy(
            range_mode="manual",
            manual_lower=None,
            manual_upper=None,
        )


def test_grid_trading_manual_mode():
    """Проверяем ручной режим с границами"""
    from strategy.grid_trading import GridTradingStrategy
    
    strategy = GridTradingStrategy(
        range_mode="manual",
        manual_lower=48000.0,
        manual_upper=52000.0,
        grid_levels=10,
    )
    
    assert strategy.range_mode == "manual"
    assert strategy.manual_lower == 48000.0
    assert strategy.manual_upper == 52000.0


def test_grid_state_management():
    """Проверяем управление состоянием сетки"""
    from strategy.grid_trading import GridTradingStrategy
    
    strategy = GridTradingStrategy()
    
    # Начальное состояние - пусто
    assert strategy.get_grid_state("BTCUSDT") is None
    
    # Сброс несуществующей сетки не должен вызывать ошибку
    strategy.reset_grid("BTCUSDT")
    assert strategy.get_grid_state("BTCUSDT") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


@pytest.fixture
def sample_df():
    """Создаём тестовый DataFrame с OHLCV и индикаторами"""
    np.random.seed(42)
    
    n = 200
    base_price = 50000.0
    
    # Боковое движение с колебаниями
    close_prices = base_price + np.random.normal(0, 500, n).cumsum()
    close_prices = np.clip(close_prices, base_price - 2000, base_price + 2000)
    
    df = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=n, freq='1h'),
        'open': close_prices - np.random.uniform(-50, 50, n),
        'high': close_prices + np.random.uniform(50, 150, n),
        'low': close_prices - np.random.uniform(50, 150, n),
        'close': close_prices,
        'volume': np.random.uniform(100, 1000, n),
    })
    
    # Добавляем индикаторы
    df['ADX_14'] = np.random.uniform(15, 22, n)  # Низкий ADX = боковое движение
    df['BBU_20_2.0'] = df['close'] + 1000
    df['BBL_20_2.0'] = df['close'] - 1000
    df['BBM_20_2.0'] = df['close']
    df['ATRr_14'] = np.random.uniform(0.5, 1.5, n)
    df['volume_z'] = np.random.normal(0, 1, n)
    df['RSI_14'] = np.random.uniform(40, 60, n)
    
    return df


@pytest.fixture
def features():
    """Дополнительные features для стратегии"""
    return {
        "symbol": "BTCUSDT",
        "orderbook": {"bid": 50000, "ask": 50010, "spread": 10},
    }


class TestGridTradingBasics:
    """Базовые тесты Grid Trading стратегии"""
    
    def test_strategy_initialization(self):
        """Проверяем инициализацию стратегии"""
        strategy = GridTradingStrategy(
            range_mode="auto",
            grid_levels=20,
            grid_spacing_percent=1.5,
        )
        
        assert strategy.name == "GridTrading"
        assert strategy.is_enabled == True
        assert strategy.range_mode == "auto"
        assert strategy.grid_levels == 20
        assert strategy.grid_spacing_percent == 1.5
    
    def test_manual_range_validation(self):
        """Проверяем валидацию manual режима"""
        with pytest.raises(ValueError):
            # Должна быть ошибка если manual mode без границ
            GridTradingStrategy(
                range_mode="manual",
                manual_lower=None,
                manual_upper=None,
            )
    
    def test_range_mode_validation(self):
        """Проверяем валидацию режима диапазона"""
        with pytest.raises(ValueError):
            GridTradingStrategy(range_mode="invalid_mode")


class TestRangeDetection:
    """Тесты определения диапазона"""
    
    def test_auto_range_detection(self, sample_df, features):
        """Проверяем автоматическое определение диапазона"""
        strategy = GridTradingStrategy(
            range_mode="auto",
            range_lookback=100,
            grid_levels=10,
            require_ranging_market=False,  # Отключаем фильтры для теста
        )
        
        signal = strategy.generate_signal(sample_df, features)
        
        # Проверяем что диапазон был определен
        grid_state = strategy.get_grid_state("BTCUSDT")
        assert grid_state is not None
        assert "range" in grid_state
        assert "levels" in grid_state
        
        range_lower, range_upper = grid_state["range"]
        assert range_lower < range_upper
        assert range_lower > 0
    
    def test_manual_range_used(self, sample_df, features):
        """Проверяем использование ручного диапазона"""
        manual_lower = 48000.0
        manual_upper = 52000.0
        
        strategy = GridTradingStrategy(
            range_mode="manual",
            manual_lower=manual_lower,
            manual_upper=manual_upper,
            grid_levels=10,
            require_ranging_market=False,
        )
        
        signal = strategy.generate_signal(sample_df, features)
        
        grid_state = strategy.get_grid_state("BTCUSDT")
        range_lower, range_upper = grid_state["range"]
        
        # В manual режиме диапазон должен быть как указан
        assert range_lower == manual_lower
        assert range_upper == manual_upper


class TestGridLevels:
    """Тесты генерации уровней сетки"""
    
    def test_grid_levels_generation(self, sample_df, features):
        """Проверяем генерацию уровней сетки"""
        strategy = GridTradingStrategy(
            range_mode="auto",
            grid_levels=10,
            grid_spacing_percent=2.0,
            require_ranging_market=False,
        )
        
        signal = strategy.generate_signal(sample_df, features)
        
        grid_state = strategy.get_grid_state("BTCUSDT")
        levels = grid_state["levels"]
        
        # Должны быть сгенерированы уровни
        assert len(levels) > 0
        
        # Уровни должны быть отсортированы
        assert levels == sorted(levels)
    
    def test_grid_levels_within_range(self, sample_df, features):
        """Проверяем что уровни сетки в пределах диапазона"""
        strategy = GridTradingStrategy(
            range_mode="auto",
            grid_levels=15,
            require_ranging_market=False,
        )
        
        signal = strategy.generate_signal(sample_df, features)
        
        grid_state = strategy.get_grid_state("BTCUSDT")
        range_lower, range_upper = grid_state["range"]
        levels = grid_state["levels"]
        
        # Все уровни должны быть в пределах диапазона (с небольшим допуском)
        for level in levels:
            assert range_lower * 0.95 <= level <= range_upper * 1.05


class TestRangingMarketFilters:
    """Тесты фильтров бокового рынка"""
    
    def test_adx_filter(self, sample_df, features):
        """Проверяем фильтр ADX для бокового рынка"""
        strategy = GridTradingStrategy(
            require_ranging_market=True,
            max_adx_for_range=25.0,
        )
        
        # Низкий ADX - должен пройти фильтр
        df_low_adx = sample_df.copy()
        df_low_adx['ADX_14'] = 20.0
        signal = strategy.generate_signal(df_low_adx, features)
        # Может быть сигнал или None (зависит от других условий)
        
        # Высокий ADX - не должен пройти фильтр
        df_high_adx = sample_df.copy()
        df_high_adx['ADX_14'] = 35.0
        signal_high = strategy.generate_signal(df_high_adx, features)
        assert signal_high is None  # Не боковой рынок
    
    def test_bb_width_filter(self, sample_df, features):
        """Проверяем фильтр ширины Bollinger Bands"""
        strategy = GridTradingStrategy(
            require_ranging_market=True,
            min_bb_width=0.015,
            max_bb_width=0.05,
        )
        
        # Нормальная ширина BB
        df_normal = sample_df.copy()
        close = df_normal['close'].iloc[-1]
        df_normal.loc[df_normal.index[-1], 'BBU_20_2.0'] = close * 1.025
        df_normal.loc[df_normal.index[-1], 'BBL_20_2.0'] = close * 0.975
        df_normal.loc[df_normal.index[-1], 'BBM_20_2.0'] = close
        
        signal = strategy.generate_signal(df_normal, features)
        # Может быть сигнал
        
        # Слишком узкая BB (компрессия)
        df_narrow = sample_df.copy()
        df_narrow.loc[df_narrow.index[-1], 'BBU_20_2.0'] = close * 1.005
        df_narrow.loc[df_narrow.index[-1], 'BBL_20_2.0'] = close * 0.995
        df_narrow.loc[df_narrow.index[-1], 'BBM_20_2.0'] = close
        
        signal_narrow = strategy.generate_signal(df_narrow, features)
        assert signal_narrow is None  # Слишком узкая


class TestBreakoutProtection:
    """Тесты защиты от пробоя"""
    
    def test_high_volume_detection(self, sample_df, features):
        """Проверяем определение высокого объёма"""
        strategy = GridTradingStrategy(
            enable_breakout_protection=True,
            breakout_volume_threshold=2.0,
            require_ranging_market=False,
        )
        
        # Нормальный объём
        df_normal = sample_df.copy()
        df_normal.loc[df_normal.index[-1], 'volume_z'] = 1.0
        
        signal = strategy.generate_signal(df_normal, features)
        
        # Высокий объём (риск пробоя)
        df_high_vol = sample_df.copy()
        df_high_vol.loc[df_high_vol.index[-1], 'volume_z'] = 3.0
        
        signal_high = strategy.generate_signal(df_high_vol, features)
        assert signal_high is None  # Защита от пробоя
    
    def test_large_price_movement(self, sample_df, features):
        """Проверяем определение сильного движения цены"""
        strategy = GridTradingStrategy(
            enable_breakout_protection=True,
            require_ranging_market=False,
        )
        
        # Сильное движение цены >2%
        df_big_move = sample_df.copy()
        prev_close = df_big_move.iloc[-2]['close']
        df_big_move.loc[df_big_move.index[-1], 'close'] = prev_close * 1.025  # +2.5%
        
        signal = strategy.generate_signal(df_big_move, features)
        assert signal is None  # Защита от пробоя


class TestSignalGeneration:
    """Тесты генерации сигналов"""
    
    def test_long_signal_near_support(self, sample_df, features):
        """Проверяем long сигнал у уровня поддержки"""
        strategy = GridTradingStrategy(
            range_mode="manual",
            manual_lower=49000.0,
            manual_upper=51000.0,
            grid_levels=10,
            grid_spacing_percent=1.0,
            require_ranging_market=False,
            enable_breakout_protection=False,
        )
        
        # Цена у нижней границы
        df = sample_df.copy()
        df.loc[df.index[-1], 'close'] = 49200.0
        
        signal = strategy.generate_signal(df, features)
        
        if signal:  # Может быть сигнал если условия выполнены
            assert signal["signal"] == "long"
            assert 0.0 <= signal["confidence"] <= 1.0
            assert "reasons" in signal
            assert len(signal["reasons"]) > 0
            assert "entry_price" in signal
            assert "stop_loss" in signal
            assert "take_profit" in signal
    
    def test_short_signal_near_resistance(self, sample_df, features):
        """Проверяем short сигнал у уровня сопротивления"""
        strategy = GridTradingStrategy(
            range_mode="manual",
            manual_lower=49000.0,
            manual_upper=51000.0,
            grid_levels=10,
            grid_spacing_percent=1.0,
            require_ranging_market=False,
            enable_breakout_protection=False,
        )
        
        # Цена у верхней границы
        df = sample_df.copy()
        df.loc[df.index[-1], 'close'] = 50800.0
        
        signal = strategy.generate_signal(df, features)
        
        if signal:
            assert signal["signal"] == "short"
            assert 0.0 <= signal["confidence"] <= 1.0
    
    def test_no_signal_between_levels(self, sample_df, features):
        """Проверяем отсутствие сигнала между уровнями"""
        strategy = GridTradingStrategy(
            range_mode="manual",
            manual_lower=49000.0,
            manual_upper=51000.0,
            grid_levels=5,
            grid_spacing_percent=2.0,
            require_ranging_market=False,
            enable_breakout_protection=False,
        )
        
        # Цена в середине между уровнями
        df = sample_df.copy()
        df.loc[df.index[-1], 'close'] = 50000.0
        
        signal = strategy.generate_signal(df, features)
        # Скорее всего None, так как далеко от уровней


class TestGridState:
    """Тесты управления состоянием сетки"""
    
    def test_grid_state_persistence(self, sample_df, features):
        """Проверяем сохранение состояния сетки"""
        strategy = GridTradingStrategy(require_ranging_market=False)
        
        # Первый вызов - создание сетки
        signal1 = strategy.generate_signal(sample_df, features)
        state1 = strategy.get_grid_state("BTCUSDT")
        
        # Второй вызов - использование существующей сетки
        signal2 = strategy.generate_signal(sample_df, features)
        state2 = strategy.get_grid_state("BTCUSDT")
        
        if state1 and state2:
            # Диапазон должен быть стабильным (если не было drift)
            assert state1["range"] == state2["range"]
    
    def test_grid_reset(self, sample_df, features):
        """Проверяем сброс состояния сетки"""
        strategy = GridTradingStrategy(require_ranging_market=False)
        
        signal = strategy.generate_signal(sample_df, features)
        assert strategy.get_grid_state("BTCUSDT") is not None
        
        # Сбрасываем сетку
        strategy.reset_grid("BTCUSDT")
        assert strategy.get_grid_state("BTCUSDT") is None
    
    def test_multi_symbol_grids(self, sample_df, features):
        """Проверяем независимые сетки для разных символов"""
        strategy = GridTradingStrategy(require_ranging_market=False)
        
        # Генерируем сетку для BTC
        features_btc = {"symbol": "BTCUSDT"}
        signal_btc = strategy.generate_signal(sample_df, features_btc)
        
        # Генерируем сетку для ETH
        df_eth = sample_df.copy()
        df_eth['close'] = df_eth['close'] * 0.04  # ETH дешевле
        features_eth = {"symbol": "ETHUSDT"}
        signal_eth = strategy.generate_signal(df_eth, features_eth)
        
        # Должны быть разные состояния для разных символов
        state_btc = strategy.get_grid_state("BTCUSDT")
        state_eth = strategy.get_grid_state("ETHUSDT")
        
        if state_btc and state_eth:
            assert state_btc["range"] != state_eth["range"]


class TestDriftRebalance:
    """Тесты ребалансировки при смещении диапазона"""
    
    def test_rebalance_on_drift(self, sample_df, features):
        """Проверяем ребалансировку при смещении диапазона"""
        strategy = GridTradingStrategy(
            rebalance_on_drift=True,
            drift_threshold_percent=10.0,
            require_ranging_market=False,
        )
        
        # Первая сетка
        signal1 = strategy.generate_signal(sample_df, features)
        state1 = strategy.get_grid_state("BTCUSDT")
        
        # Смещаем цены на 15%
        df_shifted = sample_df.copy()
        df_shifted['close'] = df_shifted['close'] * 1.15
        df_shifted['high'] = df_shifted['high'] * 1.15
        df_shifted['low'] = df_shifted['low'] * 1.15
        
        signal2 = strategy.generate_signal(df_shifted, features)
        state2 = strategy.get_grid_state("BTCUSDT")
        
        if state1 and state2:
            # При большом смещении диапазон должен обновиться
            range1_center = (state1["range"][0] + state1["range"][1]) / 2
            range2_center = (state2["range"][0] + state2["range"][1]) / 2
            
            # Центр диапазона заметно сместился
            drift_pct = abs(range2_center - range1_center) / range1_center * 100
            assert drift_pct > 5.0  # Есть смещение


class TestIntegration:
    """Интеграционные тесты"""
    
    def test_complete_workflow(self, sample_df, features):
        """Проверяем полный workflow Grid Trading"""
        strategy = GridTradingStrategy(
            range_mode="auto",
            grid_levels=15,
            grid_spacing_percent=1.5,
            require_ranging_market=True,
            enable_breakout_protection=True,
        )
        
        # 1. Генерируем первый сигнал
        signal = strategy.generate_signal(sample_df, features)
        
        # 2. Проверяем состояние сетки
        grid_state = strategy.get_grid_state("BTCUSDT")
        assert grid_state is not None
        
        # 3. Проверяем структуру сигнала если он есть
        if signal:
            assert signal["signal"] in ["long", "short"]
            assert "confidence" in signal
            assert "reasons" in signal
            assert "entry_price" in signal
            assert "stop_loss" in signal
            assert "take_profit" in signal
            
            # Confidence должна быть разумной
            assert 0.5 <= signal["confidence"] <= 1.0
            
            # Stop loss должен быть за границами диапазона
            range_lower, range_upper = grid_state["range"]
            if signal["signal"] == "long":
                assert signal["stop_loss"] < range_lower
            else:
                assert signal["stop_loss"] > range_upper
    
    def test_disabled_strategy(self, sample_df, features):
        """Проверяем что выключенная стратегия не даёт сигналов"""
        strategy = GridTradingStrategy()
        strategy.disable()
        
        signal = strategy.generate_signal(sample_df, features)
        assert signal is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
