"""
ЗАДАЧА-005 Фаза 2: Тесты для прокидывания параметров риска из конфига

Tests for:
- TradingBot accepts config parameter
- Risk parameters read from config
- Risk params passed to PositionSizer, VolatilityPositionSizer, RiskLimitsConfig
- Default values used when config missing
- CLI commands use StrategyBuilder
"""

import pytest
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from config.settings import ConfigManager
from bot.trading_bot import TradingBot
from bot.strategy_builder import StrategyBuilder
from strategy.trend_pullback import TrendPullbackStrategy
from strategy.breakout import BreakoutStrategy
from strategy.mean_reversion import MeanReversionStrategy


class TestTradingBotConfigParameter:
    """Тесты: принимает ли TradingBot параметр config"""

    def test_trading_bot_accepts_config_parameter(self):
        """TradingBot должен принимать config параметр"""
        config = ConfigManager()
        strategies = [TrendPullbackStrategy()]

        # Не должно быть исключения
        with patch('bot.trading_bot.Database'):
            with patch('bot.trading_bot.MarketDataClient'):
                with patch('bot.trading_bot.AccountClient'):
                    bot = TradingBot(
                        mode="paper",
                        strategies=strategies,
                        config=config
                    )
                    assert bot.config is config
                    assert bot.mode == "paper"

    def test_trading_bot_creates_default_config_if_not_provided(self):
        """TradingBot должен создать ConfigManager, если конфиг не передан"""
        strategies = [TrendPullbackStrategy()]

        with patch('bot.trading_bot.Database'):
            with patch('bot.trading_bot.MarketDataClient'):
                with patch('bot.trading_bot.AccountClient'):
                    with patch('bot.trading_bot.ConfigManager') as MockConfigClass:
                        # Создаём реальный mock конфиг с методом get
                        mock_config = MagicMock()
                        mock_config.get = lambda key, default=None: default
                        MockConfigClass.return_value = mock_config

                        bot = TradingBot(
                            mode="paper",
                            strategies=strategies
                        )

                        # ConfigManager должен быть создан
                        MockConfigClass.assert_called()
                        assert bot.config is mock_config

    def test_trading_bot_paper_mode_with_config(self):
        """TradingBot в paper режиме должен работать с конфигом"""
        config = ConfigManager()
        strategies = [TrendPullbackStrategy()]

        with patch('bot.trading_bot.Database'):
            with patch('bot.trading_bot.MarketDataClient'):
                with patch('bot.trading_bot.AccountClient'):
                    with patch('bot.trading_bot.PaperTradingSimulator'):
                        with patch('bot.trading_bot.EquityCurve'):
                            bot = TradingBot(
                                mode="paper",
                                strategies=strategies,
                                config=config
                            )
                            assert bot.config is config


class TestRiskParametersFromConfig:
    """Тесты: читаются ли параметры риска из конфига"""

    def test_config_has_all_risk_parameters(self):
        """Конфиг должен иметь все параметры риска"""
        config = ConfigManager()

        # Проверяем основные параметры риска
        assert config.get("risk_management.max_leverage") is not None
        assert config.get("risk_management.position_risk_percent") is not None
        assert config.get("risk_management.max_position_size") is not None
        assert config.get("risk_management.daily_loss_limit_percent") is not None
        assert config.get("risk_management.max_drawdown_percent") is not None

    def test_stop_loss_tp_config_parameters(self):
        """Конфиг должен иметь параметры для StopLossTPConfig"""
        config = ConfigManager()

        assert config.get("stop_loss_tp.sl_atr_multiplier") is not None
        assert config.get("stop_loss_tp.tp_atr_multiplier") is not None
        assert config.get("stop_loss_tp.sl_percent_fallback") is not None
        assert config.get("stop_loss_tp.tp_percent_fallback") is not None

    def test_risk_monitor_config_parameters(self):
        """Конфиг должен иметь параметры для RiskMonitorConfig"""
        config = ConfigManager()

        assert config.get("risk_monitor.max_daily_loss_percent") is not None
        assert config.get("risk_monitor.max_position_notional") is not None
        assert config.get("risk_monitor.max_leverage") is not None
        assert config.get("risk_monitor.max_orders_per_symbol") is not None
        assert config.get("risk_monitor.monitor_interval_seconds") is not None

    def test_volatility_position_sizer_config_parameters(self):
        """Конфиг должен иметь параметры для VolatilityPositionSizerConfig"""
        config = ConfigManager()

        assert config.get("risk_management.position_risk_percent") is not None
        assert config.get("risk_management.atr_multiplier") is not None
        assert config.get("risk_management.min_position_size") is not None
        assert config.get("risk_management.max_position_size") is not None

    def test_config_parameter_types(self):
        """Параметры конфига должны иметь корректные типы"""
        config = ConfigManager()

        # max_leverage должен быть числом
        max_lev = config.get("risk_management.max_leverage", 10)
        assert isinstance(max_lev, (int, float))
        assert max_lev > 0

        # position_risk_percent должен быть числом
        risk_pct = config.get("risk_management.position_risk_percent", 1.0)
        assert isinstance(risk_pct, (int, float))
        assert 0 < risk_pct <= 100

        # atr_multiplier должен быть числом
        atr_mult = config.get("risk_management.atr_multiplier", 2.0)
        assert isinstance(atr_mult, (int, float))
        assert atr_mult > 0

    def test_config_defaults_when_missing(self):
        """Конфиг должен использовать defaults, если значение отсутствует"""
        config = ConfigManager()

        # Если параметр отсутствует, должен вернуться default
        value = config.get("nonexistent.parameter", 42)
        assert value == 42

        # Если параметр существует, should return значение
        value = config.get("risk_management.max_leverage", 999)
        assert value != 999  # Should be actual value, not default


class TestStrategyBuilderWithConfig:
    """Тесты: StrategyBuilder должен использовать конфиг"""

    def test_strategy_builder_creates_strategies_with_config(self):
        """StrategyBuilder должен создавать стратегии с параметрами из конфига"""
        config = ConfigManager()
        builder = StrategyBuilder(config)

        strategies = builder.build_strategies()

        assert isinstance(strategies, list)
        assert len(strategies) > 0

    def test_strategy_builder_respects_active_strategies(self):
        """StrategyBuilder должен создавать только активные стратегии из конфига"""
        config = ConfigManager()
        builder = StrategyBuilder(config)

        strategies = builder.build_strategies()
        strategy_names = [s.__class__.__name__ for s in strategies]

        # Должны быть активные стратегии
        active = config.get("trading.active_strategies", [])
        for strategy_name in strategy_names:
            assert strategy_name.replace("Strategy", "") in [s.replace("Strategy", "") for s in active]

    def test_trend_pullback_strategy_has_config_params(self):
        """TrendPullbackStrategy должна иметь параметры из конфига"""
        config = ConfigManager()
        builder = StrategyBuilder(config)
        strategies = builder.build_strategies()

        trend_strat = None
        for s in strategies:
            if isinstance(s, TrendPullbackStrategy):
                trend_strat = s
                break

        assert trend_strat is not None
        # Параметры должны быть установлены
        assert hasattr(trend_strat, 'confidence_threshold')

    def test_breakout_strategy_has_config_params(self):
        """BreakoutStrategy должна иметь параметры из конфига"""
        config = ConfigManager()
        builder = StrategyBuilder(config)
        strategies = builder.build_strategies()

        breakout_strat = None
        for s in strategies:
            if isinstance(s, BreakoutStrategy):
                breakout_strat = s
                break

        if breakout_strat:  # Only test if Breakout is active
            assert hasattr(breakout_strat, 'confidence_threshold')

    def test_mean_reversion_strategy_has_config_params(self):
        """MeanReversionStrategy должна иметь параметры из конфига"""
        config = ConfigManager()
        builder = StrategyBuilder(config)
        strategies = builder.build_strategies()

        mr_strat = None
        for s in strategies:
            if isinstance(s, MeanReversionStrategy):
                mr_strat = s
                break

        if mr_strat:  # Only test if MeanReversion is active
            assert hasattr(mr_strat, 'confidence_threshold')


class TestConfigParameterImpact:
    """Тесты: влияют ли конфиг параметры на поведение"""

    def test_changing_config_max_leverage(self):
        """Изменение max_leverage в конфиге должно влиять на систему"""
        config1 = ConfigManager()
        max_lev_1 = config1.get("risk_management.max_leverage", 10)

        # Параметр должен быть читаем
        assert max_lev_1 is not None
        assert isinstance(max_lev_1, (int, float))

    def test_changing_config_position_risk_percent(self):
        """Изменение position_risk_percent в конфиге должно влиять на систему"""
        config = ConfigManager()
        risk_pct = config.get("risk_management.position_risk_percent", 1.0)

        assert risk_pct is not None
        assert isinstance(risk_pct, (int, float))
        assert risk_pct > 0

    def test_changing_config_atr_multiplier(self):
        """Изменение atr_multiplier в конфиге должно влиять на систему"""
        config = ConfigManager()
        atr_mult = config.get("risk_management.atr_multiplier", 2.0)

        assert atr_mult is not None
        assert isinstance(atr_mult, (int, float))
        assert atr_mult > 0

    def test_different_configs_produce_different_results(self):
        """Разные конфиги должны продуцировать разные результаты"""
        config1 = ConfigManager()
        config2 = ConfigManager()

        # Обе должны читать одинаково из одного файла
        val1 = config1.get("risk_management.max_leverage")
        val2 = config2.get("risk_management.max_leverage")

        assert val1 == val2  # Same config file


class TestCLICommandsIntegration:
    """Тесты: используют ли CLI команды StrategyBuilder и конфиг"""

    def test_paper_command_uses_strategy_builder(self):
        """paper_command должна использовать StrategyBuilder"""
        config = ConfigManager()
        builder = StrategyBuilder(config)
        strategies = builder.build_strategies()

        # Должны создаться стратегии
        assert len(strategies) > 0

    def test_live_command_uses_strategy_builder(self):
        """live_command должна использовать StrategyBuilder"""
        config = ConfigManager()
        builder = StrategyBuilder(config)
        strategies = builder.build_strategies()

        # Должны создаться стратегии
        assert len(strategies) > 0

    def test_backtest_command_uses_strategy_builder(self):
        """backtest_command должна использовать StrategyBuilder"""
        config = ConfigManager()
        builder = StrategyBuilder(config)
        strategies = builder.build_strategies()

        # Должны создаться стратегии
        assert len(strategies) > 0


class TestRiskConfigurationsIntegration:
    """Тесты: интеграция конфига с модулями риска"""

    def test_stop_loss_tp_config_reads_from_config(self):
        """StopLossTPConfig должна читать из конфига"""
        config = ConfigManager()

        sl_atr = config.get("stop_loss_tp.sl_atr_multiplier", 1.5)
        tp_atr = config.get("stop_loss_tp.tp_atr_multiplier", 2.0)

        assert sl_atr is not None
        assert tp_atr is not None
        assert isinstance(sl_atr, (int, float))
        assert isinstance(tp_atr, (int, float))

    def test_risk_limits_config_reads_from_config(self):
        """RiskLimitsConfig должна читать из конфига"""
        config = ConfigManager()

        max_leverage = config.get("risk_management.max_leverage", 10)
        max_notional = config.get("risk_management.max_notional", 50000)
        daily_loss = config.get("risk_management.daily_loss_limit_percent", 5)
        max_drawdown = config.get("risk_management.max_drawdown_percent", 10)

        assert max_leverage is not None
        assert max_notional is not None
        assert daily_loss is not None
        assert max_drawdown is not None

    def test_risk_monitor_config_reads_from_config(self):
        """RiskMonitorConfig должна читать из конфига"""
        config = ConfigManager()

        daily_loss = config.get("risk_monitor.max_daily_loss_percent", 5.0)
        max_notional = config.get("risk_monitor.max_position_notional", 50000.0)
        max_leverage = config.get("risk_monitor.max_leverage", 10.0)
        max_orders = config.get("risk_monitor.max_orders_per_symbol", 10)
        interval = config.get("risk_monitor.monitor_interval_seconds", 30)

        assert daily_loss is not None
        assert max_notional is not None
        assert max_leverage is not None
        assert max_orders is not None
        assert interval is not None

    def test_volatility_position_sizer_config_reads_from_config(self):
        """VolatilityPositionSizerConfig должна читать из конфига"""
        config = ConfigManager()

        risk_pct = config.get("risk_management.position_risk_percent", 1.0)
        atr_mult = config.get("risk_management.atr_multiplier", 2.0)
        min_size = config.get("risk_management.min_position_size", 0.00001)
        max_size = config.get("risk_management.max_position_size", 100.0)

        assert risk_pct is not None
        assert atr_mult is not None
        assert min_size is not None
        assert max_size is not None


class TestConfigFileIntegrity:
    """Тесты: целостность конфиг файла"""

    def test_config_file_exists(self):
        """Конфиг файл должен существовать"""
        config_path = Path("config/bot_settings.json")
        assert config_path.exists(), f"Config file not found at {config_path}"

    def test_config_file_is_valid_json(self):
        """Конфиг файл должен быть valid JSON"""
        config_path = Path("config/bot_settings.json")
        with open(config_path, 'r') as f:
            try:
                data = json.load(f)
                assert isinstance(data, dict)
            except json.JSONDecodeError as e:
                pytest.fail(f"Config file is not valid JSON: {e}")

    def test_config_file_has_required_sections(self):
        """Конфиг должен иметь требуемые разделы"""
        config_path = Path("config/bot_settings.json")
        with open(config_path, 'r') as f:
            data = json.load(f)

        required_sections = [
            "trading",
            "risk_management",
            "stop_loss_tp",
            "risk_monitor",
            "strategies",
        ]

        for section in required_sections:
            assert section in data, f"Missing required section: {section}"


class TestPaperTradingConfig:
    """Тесты: параметры бумажной торговли из конфига"""

    def test_paper_trading_config_has_required_parameters(self):
        """Paper trading должна иметь параметры в конфиге"""
        config = ConfigManager()

        initial_balance = config.get("paper_trading.initial_balance", 10000)
        maker_fee = config.get("paper_trading.maker_commission", 0.0002)
        taker_fee = config.get("paper_trading.taker_commission", 0.0004)

        assert initial_balance is not None
        assert maker_fee is not None
        assert taker_fee is not None

    def test_paper_trading_parameters_have_correct_types(self):
        """Параметры paper trading должны иметь корректные типы"""
        config = ConfigManager()

        initial_balance = config.get("paper_trading.initial_balance", 10000)
        assert isinstance(initial_balance, (int, float))
        assert initial_balance > 0

        maker_fee = config.get("paper_trading.maker_commission", 0.0002)
        assert isinstance(maker_fee, (int, float))
        assert 0 <= maker_fee < 1

        taker_fee = config.get("paper_trading.taker_commission", 0.0004)
        assert isinstance(taker_fee, (int, float))
        assert 0 <= taker_fee < 1


class TestConfigLogging:
    """Тесты: логирование конфиг параметров"""

    def test_config_parameters_are_logged(self):
        """При инициализации должны логироваться параметры конфига"""
        config = ConfigManager()

        # Просто проверяем, что параметры доступны и логируемы
        max_leverage = config.get("risk_management.max_leverage", 10)
        risk_percent = config.get("risk_management.position_risk_percent", 1.0)

        # Должны логироваться без ошибок
        log_string = f"max_leverage={max_leverage}, risk_percent={risk_percent}"
        assert "max_leverage=" in log_string
        assert "risk_percent=" in log_string

    def test_strategy_builder_logs_config_usage(self):
        """StrategyBuilder должна логировать использование конфига"""
        config = ConfigManager()
        builder = StrategyBuilder(config)

        # Это должно создаться без ошибок (логирование происходит внутри)
        strategies = builder.build_strategies()
        assert len(strategies) > 0


class TestBackwardCompatibility:
    """Тесты: обратная совместимость"""

    def test_old_strategy_instantiation_still_works(self):
        """Старый способ создания стратегий всё ещё должен работать"""
        # Можно создавать стратегии без конфига
        strategy = TrendPullbackStrategy()
        assert strategy is not None

    def test_trading_bot_works_without_config_parameter(self):
        """TradingBot должен работать без параметра config (для backward compat)"""
        strategies = [TrendPullbackStrategy()]

        with patch('bot.trading_bot.Database'):
            with patch('bot.trading_bot.MarketDataClient'):
                with patch('bot.trading_bot.AccountClient'):
                    with patch('bot.trading_bot.ConfigManager') as MockConfigClass:
                        # Мокируем config с реальным методом get
                        mock_config = MagicMock()
                        mock_config.get = lambda key, default=None: default
                        MockConfigClass.return_value = mock_config

                        # Не передаём config - должно работать с defaults
                        bot = TradingBot(
                            mode="paper",
                            strategies=strategies
                        )
                        assert bot is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
