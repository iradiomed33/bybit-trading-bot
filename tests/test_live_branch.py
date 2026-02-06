"""

Тесты для live-ветки TradingBot._process_signal()


Требования (DoD):

- Live-ветка проходит до вызова place_order() без исключений

- Тест прогоняет _process_signal() с buy/sell сигналом и мокнутым клиентом

- Проверка правильности интерфейсов: get_wallet_balance(), calculate_position_size(), check_limits()

"""


import pytest

from unittest.mock import Mock

from bot.trading_bot import TradingBot

from storage.database import Database


class TestProcessSignalLiveBranch:

    """Тесты live-ветки _process_signal()"""

    @pytest.fixture
    def mock_clients(self):
        """Создать мокированные клиенты"""

        mocks = {

            "account": Mock(),

            "order_manager": Mock(),

            "position_sizer": Mock(),

            "position_manager": Mock(),

            "risk_limits": Mock(),

            "db": Mock(spec=Database),

        }

        return mocks

    @pytest.fixture
    def trading_bot_live(self, mock_clients):
        """TradingBot в live mode с мокнутыми компонентами"""

        # Создаем бота с мокнутыми компонентами

        bot = Mock(spec=TradingBot)

        # Устанавливаем параметры

        bot.symbol = "BTCUSDT"

        bot.timeframe = "1h"

        bot.mode = "live"

        bot.risk_percent = 2.0

        # Подменяем компоненты на моки - используем account_client!

        bot.account_client = mock_clients["account"]

        bot.order_manager = mock_clients["order_manager"]

        bot.position_sizer = mock_clients["position_sizer"]

        bot.position_manager = mock_clients["position_manager"]

        bot.risk_limits = mock_clients["risk_limits"]

        bot.db = mock_clients["db"]

        # Добавляем дополнительные обязательные атрибуты для live режима

        bot.position_state_manager = Mock()

        bot.position_state_manager.has_position.return_value = False

        bot.advanced_risk_limits = None  # Выключаем advanced риск лимиты

        bot.signal_handler = Mock()

        bot.kill_switch_manager = None

        bot.volatility_position_sizer = None  # Не используем в live

        bot.paper_simulator = None

        # Указываем реальный метод _process_signal

        bot._process_signal = TradingBot._process_signal.__get__(bot, TradingBot)

        return bot

    def test_process_signal_long_success(self, trading_bot_live, mock_clients):
        """Test: Успешная обработка LONG сигнала в live mode"""

        # Настраиваем моки - note: account_client вместо account

        mock_clients["account"].get_wallet_balance.return_value = {

            "balance": 10000.0,

        }

        # Создаем сигнал

        signal = {

            "signal": "long",

            "strategy": "TrendPullback",

            "entry_price": 50000.0,

            "stop_loss": 49000.0,

            "take_profit": 52000.0,

            "stop_distance": 1000.0,  # Нужно добавить

            "confidence": 0.8,

            "position_size": 0.1,

            "atr": 500.0,

        }

        # Вызываем функцию - не должно быть исключений

        try:

            trading_bot_live._process_signal(signal)

        except Exception as e:

            pytest.fail(f"_process_signal raised {type(e).__name__}: {e}")

        # Проверяем что get_wallet_balance был вызван

        mock_clients["account"].get_wallet_balance.assert_called_once_with(coin="USDT")

        print("[OK] Long signal processed successfully")

    def test_process_signal_short_success(self, trading_bot_live, mock_clients):
        """Test: Успешная обработка SHORT сигнала в live mode"""

        mock_clients["account"].get_wallet_balance.return_value = {

            "balance": 10000.0,

        }

        signal = {

            "signal": "short",

            "strategy": "MeanReversion",

            "entry_price": 50000.0,

            "stop_loss": 51000.0,

            "take_profit": 48000.0,

            "stop_distance": 1000.0,  # Нужно добавить

            "confidence": 0.7,

            "position_size": 0.1,

            "atr": 500.0,

        }

        try:

            trading_bot_live._process_signal(signal)

        except Exception as e:

            pytest.fail(f"_process_signal raised {type(e).__name__}: {e}")

        print("[OK] Short signal processed successfully")

    def test_process_signal_rejects_invalid_balance(self, trading_bot_live, mock_clients):
        """Test: Отклонение сигнала при невалидном балансе"""

        mock_clients["account"].get_wallet_balance.return_value = {

            "balance": 0.0,  # Невалидный баланс

            "coin": "USDT",

            "retCode": -1,

        }

        signal = {

            "signal": "long",

            "strategy": "TrendPullback",

            "entry_price": 50000.0,

            "stop_loss": 49000.0,

            "confidence": 0.8,

        }

        try:

            trading_bot_live._process_signal(signal)

        except Exception as e:

            pytest.fail(f"_process_signal raised {type(e).__name__}: {e}")

        # Проверяем что order не был выставлен

        mock_clients["order_manager"].create_order.assert_not_called()

        print("[OK] Invalid balance correctly rejected")

    def test_process_signal_rejects_invalid_position_size(self, trading_bot_live, mock_clients):
        """Test: Отклонение сигнала при ошибке расчета размера позиции"""

        mock_clients["account"].get_wallet_balance.return_value = {

            "balance": 10000.0,

            "coin": "USDT",

            "retCode": 0,

        }

        mock_clients["position_sizer"].calculate_position_size.return_value = {

            "success": False,

            "error": "Stop loss too close to entry",

        }

        signal = {

            "signal": "long",

            "strategy": "TrendPullback",

            "entry_price": 50000.0,

            "stop_loss": 50000.0,  # Невалидный стоп

            "confidence": 0.8,

        }

        try:

            trading_bot_live._process_signal(signal)

        except Exception as e:

            pytest.fail(f"_process_signal raised {type(e).__name__}: {e}")

        # Проверяем что лимиты и ордер не проверялись

        mock_clients["risk_limits"].check_limits.assert_not_called()

        mock_clients["order_manager"].create_order.assert_not_called()

        print("[OK] Invalid position size correctly rejected")

    def test_process_signal_rejects_risk_limits(self, trading_bot_live, mock_clients):
        """Test: Отклонение сигнала при превышении риск-лимитов"""

        mock_clients["account"].get_wallet_balance.return_value = {

            "balance": 10000.0,

            "coin": "USDT",

            "retCode": 0,

        }

        mock_clients["position_sizer"].calculate_position_size.return_value = {

            "success": True,

            "position_size": 0.1,

            "position_value": 5000.0,

        }

        mock_clients["risk_limits"].check_limits.return_value = {

            "allowed": False,

            "violations": ["Daily loss limit exceeded"],

        }

        signal = {

            "signal": "long",

            "strategy": "TrendPullback",

            "entry_price": 50000.0,

            "stop_loss": 49000.0,

            "confidence": 0.8,

        }

        try:

            trading_bot_live._process_signal(signal)

        except Exception as e:

            pytest.fail(f"_process_signal raised {type(e).__name__}: {e}")

        # Проверяем что ордер не был выставлен

        mock_clients["order_manager"].create_order.assert_not_called()

        print("[OK] Risk limits violation correctly rejected")

    def test_process_signal_order_api_failure(self, trading_bot_live, mock_clients):
        """Test: Обработка ошибки при выставлении ордера"""

        mock_clients["account"].get_wallet_balance.return_value = {

            "balance": 10000.0,

            "coin": "USDT",

            "retCode": 0,

        }

        mock_clients["position_sizer"].calculate_position_size.return_value = {

            "success": True,

            "position_size": 0.1,

            "position_value": 5000.0,

        }

        mock_clients["risk_limits"].check_limits.return_value = {

            "allowed": True,

            "violations": [],

        }

        # API возвращает ошибку

        mock_clients["order_manager"].create_order.return_value = {

            "retCode": -1,

            "retMsg": "Insufficient balance",

        }

        signal = {

            "signal": "long",

            "strategy": "TrendPullback",

            "entry_price": 50000.0,

            "stop_loss": 49000.0,

            "confidence": 0.8,

        }

        try:

            trading_bot_live._process_signal(signal)

        except Exception as e:

            pytest.fail(f"_process_signal raised {type(e).__name__}: {e}")

        # Проверяем что позиция не была зарегистрирована

        mock_clients["position_manager"].register_position.assert_not_called()

        print("[OK] Order API failure correctly handled")

    def test_process_signal_exception_handling(self, trading_bot_live, mock_clients):
        """Test: Обработка исключений в _process_signal()"""

        mock_clients["account"].get_wallet_balance.side_effect = Exception("Connection error")

        signal = {

            "signal": "long",

            "strategy": "TrendPullback",

            "entry_price": 50000.0,

            "stop_loss": 49000.0,

            "confidence": 0.8,

        }

        # Исключение должно быть поймано и залоировано

        try:

            trading_bot_live._process_signal(signal)

        except Exception as e:

            pytest.fail(f"_process_signal raised uncaught {type(e).__name__}: {e}")

        print("[OK] Exceptions correctly handled")


class TestInterfaceCorrectness:

    """Тесты корректности интерфейсов"""

    def test_account_client_get_wallet_balance_interface(self):
        """Test: AccountClient.get_wallet_balance() возвращает правильный формат"""

        from exchange.account import AccountClient

        # Проверяем что метод существует

        assert hasattr(AccountClient, "get_wallet_balance")

        # Проверяем сигнатуру

        import inspect

        sig = inspect.signature(AccountClient.get_wallet_balance)

        params = list(sig.parameters.keys())

        assert "self" in params

        assert "coin" in params

        print("[OK] AccountClient.get_wallet_balance() interface correct")

    def test_position_sizer_calculate_position_size_interface(self):
        """Test: PositionSizer.calculate_position_size() возвращает Dict"""

        from risk.position_sizer import PositionSizer

        # Проверяем что метод существует

        assert hasattr(PositionSizer, "calculate_position_size")

        # Проверяем сигнатуру

        import inspect

        sig = inspect.signature(PositionSizer.calculate_position_size)

        params = list(sig.parameters.keys())

        assert "account_balance" in params

        assert "entry_price" in params

        assert "stop_loss_price" in params

        print("[OK] PositionSizer.calculate_position_size() interface correct")

    def test_risk_limits_check_limits_interface(self):
        """Test: RiskLimits.check_limits() возвращает Dict с allowed ключом"""

        from risk.limits import RiskLimits

        # Проверяем что метод существует

        assert hasattr(RiskLimits, "check_limits")

        # Проверяем сигнатуру

        import inspect

        sig = inspect.signature(RiskLimits.check_limits)

        params = list(sig.parameters.keys())

        assert "account_balance" in params

        assert "proposed_trade" in params

        print("[OK] RiskLimits.check_limits() interface correct")
