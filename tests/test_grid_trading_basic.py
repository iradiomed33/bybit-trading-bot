"""
Базовые тесты для Grid Trading стратегии

Проверяем основную функциональность.
"""

import pytest


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


def test_range_mode_validation():
    """Проверяем валидацию режима диапазона"""
    from strategy.grid_trading import GridTradingStrategy
    
    with pytest.raises(ValueError):
        GridTradingStrategy(range_mode="invalid_mode")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
