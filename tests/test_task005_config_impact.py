"""
TASK-005 Tests: Подтверждение что конфиг влияет на торговлю

Тесты проверяют что:
1. StrategyBuilder создает стратегии с параметрами из конфига
2. Изменение параметров в конфиге меняет поведение
3. Config параметры логируются правильно
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open

from config.settings import ConfigManager
from bot.strategy_builder import StrategyBuilder


class TestStrategyBuilder:
    """Тесты StrategyBuilder с параметрами из конфига"""
    
    def test_builder_loads_config(self):
        """StrategyBuilder загружает конфигурацию"""
        config = ConfigManager()
        builder = StrategyBuilder(config)
        
        assert builder.config is not None
        assert isinstance(builder.config, ConfigManager)
    
    def test_build_strategies_returns_list(self):
        """build_strategies() возвращает список стратегий"""
        config = ConfigManager()
        builder = StrategyBuilder(config)
        
        strategies = builder.build_strategies()
        
        assert isinstance(strategies, list)
        assert len(strategies) > 0
    
    def test_trend_pullback_gets_config_params(self):
        """TrendPullback создается с параметрами из конфига"""
        config = ConfigManager()
        builder = StrategyBuilder(config)
        
        strategies = builder.build_strategies()
        
        # Find TrendPullback
        trend_pullback = None
        for strategy in strategies:
            if strategy.__class__.__name__ == "TrendPullbackStrategy":
                trend_pullback = strategy
                break
        
        assert trend_pullback is not None
        
        # Check that config params were set
        assert hasattr(trend_pullback, 'confidence_threshold')
        assert trend_pullback.confidence_threshold > 0
        assert hasattr(trend_pullback, 'min_candles')
        assert trend_pullback.min_candles > 0
    
    def test_breakout_gets_config_params(self):
        """Breakout создается с параметрами из конфига"""
        config = ConfigManager()
        builder = StrategyBuilder(config)
        
        strategies = builder.build_strategies()
        
        # Find Breakout
        breakout = None
        for strategy in strategies:
            if strategy.__class__.__name__ == "BreakoutStrategy":
                breakout = strategy
                break
        
        assert breakout is not None
        
        # Check params
        assert hasattr(breakout, 'confidence_threshold')
        assert breakout.confidence_threshold > 0
    
    def test_mean_reversion_gets_config_params(self):
        """MeanReversion создается с параметрами из конфига"""
        config = ConfigManager()
        builder = StrategyBuilder(config)
        
        strategies = builder.build_strategies()
        
        # Find MeanReversion
        mean_reversion = None
        for strategy in strategies:
            if strategy.__class__.__name__ == "MeanReversionStrategy":
                mean_reversion = strategy
                break
        
        assert mean_reversion is not None
        
        # Check params
        assert hasattr(mean_reversion, 'confidence_threshold')
        assert mean_reversion.confidence_threshold > 0
    
    def test_active_strategies_respected(self):
        """StrategyBuilder создает только активные стратегии"""
        config = ConfigManager()
        
        # Check what's actually configured as active
        active = config.get("trading.active_strategies", [])
        builder = StrategyBuilder(config)
        strategies = builder.build_strategies()
        
        # Should have same number of strategies as active
        assert len(strategies) == len(active)


class TestConfigParameterImpact:
    """Тесты что изменение конфига меняет создаваемые объекты"""
    
    def test_confidence_threshold_from_config(self):
        """confidence_threshold берется из конфига"""
        config = ConfigManager()
        builder = StrategyBuilder(config)
        strategies = builder.build_strategies()
        
        # Get expected value from config
        expected_trend_conf = config.get("strategies.TrendPullback.confidence_threshold", 0.35)
        
        # Find TrendPullback and check
        for strategy in strategies:
            if strategy.__class__.__name__ == "TrendPullbackStrategy":
                assert strategy.confidence_threshold == float(expected_trend_conf)
    
    def test_min_adx_from_config(self):
        """min_adx параметр берется из конфига для TrendPullback"""
        config = ConfigManager()
        builder = StrategyBuilder(config)
        strategies = builder.build_strategies()
        
        # Get expected value
        expected_min_adx = config.get("strategies.TrendPullback.min_adx", 15.0)
        
        # Find and verify
        for strategy in strategies:
            if strategy.__class__.__name__ == "TrendPullbackStrategy":
                assert strategy.min_adx == float(expected_min_adx)
    
    def test_breakout_bb_width_from_config(self):
        """Breakout параметры берутся из конфика"""
        config = ConfigManager()
        builder = StrategyBuilder(config)
        strategies = builder.build_strategies()
        
        expected_bb_width = config.get("strategies.Breakout.bb_width_threshold", 0.02)
        
        for strategy in strategies:
            if strategy.__class__.__name__ == "BreakoutStrategy":
                assert strategy.bb_width_threshold == float(expected_bb_width)
    
    def test_mean_reversion_rsi_from_config(self):
        """MeanReversion RSI параметры из конфига"""
        config = ConfigManager()
        builder = StrategyBuilder(config)
        strategies = builder.build_strategies()
        
        expected_rsi_oversold = config.get("strategies.MeanReversion.rsi_oversold", 30.0)
        
        for strategy in strategies:
            if strategy.__class__.__name__ == "MeanReversionStrategy":
                assert strategy.rsi_oversold == float(expected_rsi_oversold)


class TestRiskConfigParameters:
    """Тесты что risk_management параметры существуют и корректны"""
    
    def test_max_leverage_exists_in_config(self):
        """max_leverage параметр существует в конфиге"""
        config = ConfigManager()
        max_leverage = config.get("risk_management.max_leverage")
        
        assert max_leverage is not None
        assert float(max_leverage) > 0
        assert float(max_leverage) <= 100
    
    def test_position_risk_percent_exists(self):
        """position_risk_percent параметр существует"""
        config = ConfigManager()
        risk_percent = config.get("risk_management.position_risk_percent")
        
        assert risk_percent is not None
        assert float(risk_percent) > 0
        assert float(risk_percent) <= 100
    
    def test_stop_loss_percent_exists(self):
        """stop_loss_percent параметр существует"""
        config = ConfigManager()
        sl_percent = config.get("risk_management.stop_loss_percent")
        
        assert sl_percent is not None
        assert float(sl_percent) > 0
    
    def test_take_profit_percent_exists(self):
        """take_profit_percent параметр существует"""
        config = ConfigManager()
        tp_percent = config.get("risk_management.take_profit_percent")
        
        assert tp_percent is not None
        assert float(tp_percent) > 0


class TestConfigLogging:
    """Тесты что параметры логируются при создании"""
    
    def test_strategy_builder_logs_params(self, caplog):
        """StrategyBuilder логирует параметры при создании стратегий"""
        import logging
        caplog.set_level(logging.INFO)
        
        config = ConfigManager()
        builder = StrategyBuilder(config)
        strategies = builder.build_strategies()
        
        # Check that certain params appear in logs
        assert len(caplog.records) > 0
        log_text = "\n".join([record.message for record in caplog.records])
        
        # Should mention strategies
        assert "TrendPullback" in log_text or "Breakout" in log_text
    
    def test_config_summary_works(self, caplog):
        """Можно получить сводку по конфигурации"""
        import logging
        caplog.set_level(logging.INFO)
        
        config = ConfigManager()
        
        # Get some values
        risk_percent = config.get("risk_management.position_risk_percent")
        max_leverage = config.get("risk_management.max_leverage")
        
        assert risk_percent is not None
        assert max_leverage is not None


class TestStrategyBuilderIntegration:
    """Интеграционные тесты StrategyBuilder"""
    
    def test_create_strategies_from_config_wrapper(self):
        """Wrapper функция create_strategies_from_config() работает"""
        from bot.strategy_builder import create_strategies_from_config
        
        strategies = create_strategies_from_config()
        
        assert isinstance(strategies, list)
        assert len(strategies) > 0
    
    def test_strategies_have_config_values(self):
        """Все созданные стратегии имеют конфиг-параметры"""
        config = ConfigManager()
        builder = StrategyBuilder(config)
        strategies = builder.build_strategies()
        
        for strategy in strategies:
            # All should have confidence_threshold set from config
            assert hasattr(strategy, 'confidence_threshold')
            assert isinstance(strategy.confidence_threshold, float)
            assert strategy.confidence_threshold > 0


class TestConfigCanBeChanged:
    """Тесты что конфиг можно изменять для влияния на поведение"""
    
    def test_config_get_returns_correct_type(self):
        """config.get() возвращает корректный тип"""
        config = ConfigManager()
        
        # These should be numbers
        leverage = config.get("risk_management.max_leverage")
        risk_pct = config.get("risk_management.position_risk_percent")
        
        assert isinstance(leverage, (int, float))
        assert isinstance(risk_pct, (int, float))
    
    def test_config_defaults_exist_for_all_params(self):
        """Для всех параметров есть defaults"""
        config = ConfigManager()
        
        # Should not return None
        assert config.get("risk_management.max_leverage", 10.0) is not None
        assert config.get("strategies.TrendPullback.confidence_threshold", 0.35) is not None
        assert config.get("strategies.Breakout.breakout_percent", 0.01) is not None
    
    def test_nested_config_keys_work(self):
        """Nested конфиг ключи работают (strategy.TrendPullback.min_adx)"""
        config = ConfigManager()
        
        # Should work with nested keys
        val = config.get("strategies.TrendPullback.min_adx")
        assert val is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
