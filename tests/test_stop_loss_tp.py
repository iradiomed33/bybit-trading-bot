"""

Тесты для менеджера стоп-лоссов и тейк-профитов.


Проверяют:

- Расчет SL/TP на основе ATR

- Fallback к процентам при отсутствии ATR

- Минимальные расстояния

- Биржевые и виртуальные ордера

- Обнаружение триггеров

- Частичные заполнения

- Trailing stops

"""


import pytest

from decimal import Decimal

from unittest.mock import Mock

from execution.stop_loss_tp_manager import (

    StopLossTakeProfitManager,

    StopLossTPConfig,

    StopLossTakeProfitLevels,

)


class TestStopLossTPConfig:

    """Тесты конфигурации"""

    def test_default_config(self):
        """Проверяет значения по умолчанию"""

        config = StopLossTPConfig()

        assert config.sl_atr_multiplier == 1.5

        assert config.tp_atr_multiplier == 2.0

        assert config.use_exchange_sl_tp is True

        assert config.use_virtual_levels is True

        assert config.enable_trailing_stop is True

    def test_custom_config(self):
        """Проверяет пользовательскую конфигурацию"""

        config = StopLossTPConfig(

            sl_atr_multiplier=2.0,

            tp_atr_multiplier=3.0,

            use_exchange_sl_tp=False,

        )

        assert config.sl_atr_multiplier == 2.0

        assert config.tp_atr_multiplier == 3.0

        assert config.use_exchange_sl_tp is False


class TestStopLossTakeProfitLevels:

    """Тесты для модели уровней SL/TP"""

    def test_levels_creation(self):
        """Проверяет создание уровней"""

        levels = StopLossTakeProfitLevels(

            position_id="pos_123",

            symbol="BTCUSDT",

            side="Long",

            entry_price=Decimal("30000"),

            entry_qty=Decimal("0.1"),

            atr=Decimal("500"),

            sl_price=Decimal("29250"),

            tp_price=Decimal("31000"),

        )

        assert levels.position_id == "pos_123"

        assert levels.side == "Long"

        assert levels.entry_price == Decimal("30000")

        assert levels.sl_hit is False

        assert levels.tp_hit is False

    def test_levels_to_dict(self):
        """Проверяет конвертацию в словарь"""

        levels = StopLossTakeProfitLevels(

            position_id="pos_123",

            symbol="BTCUSDT",

            side="Long",

            entry_price=Decimal("30000"),

            entry_qty=Decimal("0.1"),

            atr=Decimal("500"),

            sl_price=Decimal("29250"),

            tp_price=Decimal("31000"),

        )

        data = levels.to_dict()

        assert data["position_id"] == "pos_123"

        assert data["entry_price"] == "30000"

        assert data["atr"] == "500"

        assert data["sl_hit"] is False

    def test_levels_from_dict(self):
        """Проверяет создание из словаря"""

        data = {

            "position_id": "pos_123",

            "symbol": "BTCUSDT",

            "side": "Long",

            "entry_price": "30000",

            "entry_qty": "0.1",

            "atr": "500",

            "sl_price": "29250",

            "tp_price": "31000",

            "sl_hit": False,

            "tp_hit": False,

            "closed_qty": "0",

        }

        levels = StopLossTakeProfitLevels.from_dict(data)

        assert levels.position_id == "pos_123"

        assert levels.entry_price == Decimal("30000")

        assert levels.atr == Decimal("500")


class TestStopLossTakeProfitCalculation:

    """Тесты расчета SL/TP"""

    @pytest.fixture
    def mock_order_manager(self):
        """Создает мок для OrderManager"""

        return Mock()

    @pytest.fixture
    def manager(self, mock_order_manager):
        """Создает менеджер с конфигурацией"""

        config = StopLossTPConfig(

            sl_atr_multiplier=1.5,

            tp_atr_multiplier=2.0,

        )

        return StopLossTakeProfitManager(mock_order_manager, config)

    def test_calculate_levels_with_atr(self, manager):
        """Проверяет расчет уровней с ATR (Long позиция)"""

        levels = manager.calculate_levels(

            position_id="pos_123",

            symbol="BTCUSDT",

            side="Long",

            entry_price=Decimal("30000"),

            entry_qty=Decimal("0.1"),

            current_atr=Decimal("500"),

        )

        # Long: SL = entry - (ATR * 1.5) = 30000 - 750 = 29250

        assert levels.sl_price == Decimal("29250")

        # Long: TP = entry + (ATR * 2.0) = 30000 + 1000 = 31000

        assert levels.tp_price == Decimal("31000")

        assert levels.side == "Long"

    def test_calculate_levels_short_with_atr(self, manager):
        """Проверяет расчет уровней для Short позиции"""

        levels = manager.calculate_levels(

            position_id="pos_123",

            symbol="BTCUSDT",

            side="Short",

            entry_price=Decimal("30000"),

            entry_qty=Decimal("0.1"),

            current_atr=Decimal("500"),

        )

        # Short: SL = entry + (ATR * 1.5) = 30000 + 750 = 30750

        assert levels.sl_price == Decimal("30750")

        # Short: TP = entry - (ATR * 2.0) = 30000 - 1000 = 29000

        assert levels.tp_price == Decimal("29000")

    def test_calculate_levels_fallback_percent(self, manager):
        """Проверяет fallback к процентам при отсутствии ATR"""

        levels = manager.calculate_levels(

            position_id="pos_123",

            symbol="BTCUSDT",

            side="Long",

            entry_price=Decimal("30000"),

            entry_qty=Decimal("0.1"),

            current_atr=None,

        )

        # Fallback: SL% = 1.0% → 30000 * 0.01 = 300

        # Long: SL = 30000 - 300 = 29700

        assert levels.sl_price == Decimal("29700")

        # Fallback: TP% = 2.0% → 30000 * 0.02 = 600

        # Long: TP = 30000 + 600 = 30600

        assert levels.tp_price == Decimal("30600")

    def test_minimum_sl_distance_enforced(self, manager):
        """Проверяет что минимальное расстояние SL соблюдается"""

        # Очень маленький ATR

        levels = manager.calculate_levels(

            position_id="pos_123",

            symbol="BTCUSDT",

            side="Long",

            entry_price=Decimal("30000"),

            entry_qty=Decimal("0.1"),

            current_atr=Decimal("5"),  # Очень мало

        )

        # ATR * 1.5 = 7.5, но min_sl_distance = 10

        # Должен быть использован минимум

        assert levels.sl_price == Decimal("29990")  # 30000 - 10

    def test_multiple_positions(self, manager):
        """Проверяет управление несколькими позициями"""

        levels1 = manager.calculate_levels(

            position_id="pos_1",

            symbol="BTCUSDT",

            side="Long",

            entry_price=Decimal("30000"),

            entry_qty=Decimal("0.1"),

            current_atr=Decimal("500"),

        )

        levels2 = manager.calculate_levels(

            position_id="pos_2",

            symbol="ETHUSDT",

            side="Short",

            entry_price=Decimal("2000"),

            entry_qty=Decimal("1.0"),

            current_atr=Decimal("50"),

        )

        assert manager.get_levels("pos_1") == levels1

        assert manager.get_levels("pos_2") == levels2

        assert len(manager.get_all_active_levels()) == 2


class TestVirtualLevelTriggering:

    """Тесты виртуального триггерирования SL/TP"""

    @pytest.fixture
    def mock_order_manager(self):

        return Mock()

    @pytest.fixture
    def manager(self, mock_order_manager):

        config = StopLossTPConfig(use_virtual_levels=True)

        return StopLossTakeProfitManager(mock_order_manager, config)

    def test_long_sl_trigger(self, manager):
        """Проверяет триггерирование SL для Long позиции"""

        manager.calculate_levels(

            position_id="pos_123",

            symbol="BTCUSDT",

            side="Long",

            entry_price=Decimal("30000"),

            entry_qty=Decimal("0.1"),

            current_atr=Decimal("500"),

        )

        # Цена падает ниже SL (29250)

        triggered, trigger_type = manager.check_virtual_levels(

            position_id="pos_123",

            current_price=Decimal("29000"),

            current_qty=Decimal("0.1"),

        )

        assert triggered is True

        assert trigger_type == "sl"

    def test_long_tp_trigger(self, manager):
        """Проверяет триггерирование TP для Long позиции"""

        manager.calculate_levels(

            position_id="pos_123",

            symbol="BTCUSDT",

            side="Long",

            entry_price=Decimal("30000"),

            entry_qty=Decimal("0.1"),

            current_atr=Decimal("500"),

        )

        # Цена растет выше TP (31000)

        triggered, trigger_type = manager.check_virtual_levels(

            position_id="pos_123",

            current_price=Decimal("31500"),

            current_qty=Decimal("0.1"),

        )

        assert triggered is True

        assert trigger_type == "tp"

    def test_short_sl_trigger(self, manager):
        """Проверяет триггерирование SL для Short позиции"""

        manager.calculate_levels(

            position_id="pos_123",

            symbol="BTCUSDT",

            side="Short",

            entry_price=Decimal("30000"),

            entry_qty=Decimal("0.1"),

            current_atr=Decimal("500"),

        )

        # Short: SL = 30750, цена растет выше SL

        triggered, trigger_type = manager.check_virtual_levels(

            position_id="pos_123",

            current_price=Decimal("31000"),

            current_qty=Decimal("0.1"),

        )

        assert triggered is True

        assert trigger_type == "sl"

    def test_short_tp_trigger(self, manager):
        """Проверяет триггерирование TP для Short позиции"""

        manager.calculate_levels(

            position_id="pos_123",

            symbol="BTCUSDT",

            side="Short",

            entry_price=Decimal("30000"),

            entry_qty=Decimal("0.1"),

            current_atr=Decimal("500"),

        )

        # Short: TP = 29000, цена падает ниже TP

        triggered, trigger_type = manager.check_virtual_levels(

            position_id="pos_123",

            current_price=Decimal("28500"),

            current_qty=Decimal("0.1"),

        )

        assert triggered is True

        assert trigger_type == "tp"

    def test_no_trigger_in_range(self, manager):
        """Проверяет что триггер не срабатывает внутри диапазона"""

        manager.calculate_levels(

            position_id="pos_123",

            symbol="BTCUSDT",

            side="Long",

            entry_price=Decimal("30000"),

            entry_qty=Decimal("0.1"),

            current_atr=Decimal("500"),

        )

        # Цена между SL (29250) и TP (31000)

        triggered, trigger_type = manager.check_virtual_levels(

            position_id="pos_123",

            current_price=Decimal("30500"),

            current_qty=Decimal("0.1"),

        )

        assert triggered is False

        assert trigger_type is None

    def test_double_trigger_prevention(self, manager):
        """Проверяет что уровень не может быть триггернут дважды"""

        manager.calculate_levels(

            position_id="pos_123",

            symbol="BTCUSDT",

            side="Long",

            entry_price=Decimal("30000"),

            entry_qty=Decimal("0.1"),

            current_atr=Decimal("500"),

        )

        # Первый триггер SL

        triggered1, type1 = manager.check_virtual_levels(

            position_id="pos_123",

            current_price=Decimal("29000"),

            current_qty=Decimal("0.1"),

        )

        # Второй вызов - SL уже триггернут

        triggered2, type2 = manager.check_virtual_levels(

            position_id="pos_123",

            current_price=Decimal("28500"),

            current_qty=Decimal("0.1"),

        )

        assert triggered1 is True

        assert type1 == "sl"

        assert triggered2 is False  # Уже триггернут

        assert type2 is None


class TestPartialFills:

    """Тесты обработки частичных заполнений"""

    @pytest.fixture
    def mock_order_manager(self):

        return Mock()

    @pytest.fixture
    def manager(self, mock_order_manager):

        return StopLossTakeProfitManager(mock_order_manager)

    def test_partial_fill_update(self, manager):
        """Проверяет обновление при частичном заполнении"""

        original_qty = Decimal("1.0")

        manager.calculate_levels(

            position_id="pos_123",

            symbol="BTCUSDT",

            side="Long",

            entry_price=Decimal("30000"),

            entry_qty=original_qty,

            current_atr=Decimal("500"),

        )

        # 0.3 заполнено, 0.7 осталось

        updated = manager.handle_partial_fill(

            position_id="pos_123",

            filled_qty=Decimal("0.3"),

            remaining_qty=Decimal("0.7"),

        )

        assert updated is not None

        assert updated.entry_qty == Decimal("0.7")

        assert updated.closed_qty == Decimal("0.3")

        # SL/TP остаются на месте

        assert updated.sl_price == Decimal("29250")  # Не изменился

        assert updated.tp_price == Decimal("31000")

    def test_full_fill_closes_position(self, manager):
        """Проверяет что позиция может быть полностью закрыта"""

        manager.calculate_levels(

            position_id="pos_123",

            symbol="BTCUSDT",

            side="Long",

            entry_price=Decimal("30000"),

            entry_qty=Decimal("1.0"),

            current_atr=Decimal("500"),

        )

        # Полное заполнение

        updated = manager.handle_partial_fill(

            position_id="pos_123",

            filled_qty=Decimal("1.0"),

            remaining_qty=Decimal("0"),

        )

        assert updated is not None

        # При remaining_qty=0 позиция полностью закрыта - запись остаётся для истории

        # но entry_qty остаётся исходный для истории


class TestTrailingStop:

    """Тесты trailing stop функции"""

    @pytest.fixture
    def mock_order_manager(self):

        return Mock()

    @pytest.fixture
    def manager(self, mock_order_manager):

        config = StopLossTPConfig(enable_trailing_stop=True, trailing_multiplier=0.5)

        return StopLossTakeProfitManager(mock_order_manager, config)

    def test_trailing_stop_long_position(self, manager):
        """Проверяет trailing stop для Long позиции"""

        manager.calculate_levels(

            position_id="pos_123",

            symbol="BTCUSDT",

            side="Long",

            entry_price=Decimal("30000"),

            entry_qty=Decimal("0.1"),

            current_atr=Decimal("500"),

        )

        old_sl = manager.get_levels("pos_123").sl_price

        # Цена растет, SL должен расти

        updated = manager.update_trailing_stop(

            position_id="pos_123",

            current_price=Decimal("31000"),  # +1000 от entry

        )

        assert updated is True

        new_sl = manager.get_levels("pos_123").sl_price

        # new_sl = 31000 - (500 * 0.5) = 30750

        assert new_sl == Decimal("30750")

        assert new_sl > old_sl

    def test_trailing_stop_short_position(self, manager):
        """Проверяет trailing stop для Short позиции"""

        manager.calculate_levels(

            position_id="pos_123",

            symbol="BTCUSDT",

            side="Short",

            entry_price=Decimal("30000"),

            entry_qty=Decimal("0.1"),

            current_atr=Decimal("500"),

        )

        old_sl = manager.get_levels("pos_123").sl_price

        # Цена падает, SL должен падать

        updated = manager.update_trailing_stop(

            position_id="pos_123",

            current_price=Decimal("29000"),  # -1000 от entry

        )

        assert updated is True

        new_sl = manager.get_levels("pos_123").sl_price

        # new_sl = 29000 + (500 * 0.5) = 29250

        assert new_sl == Decimal("29250")

        assert new_sl < old_sl

    def test_trailing_stop_not_updating_against_trend(self, manager):
        """Проверяет что trailing не движется против тренда"""

        manager.calculate_levels(

            position_id="pos_123",

            symbol="BTCUSDT",

            side="Long",

            entry_price=Decimal("30000"),

            entry_qty=Decimal("0.1"),

            current_atr=Decimal("500"),

        )

        old_sl = manager.get_levels("pos_123").sl_price

        # Цена падает - trailing stop не должен уходить

        updated = manager.update_trailing_stop(

            position_id="pos_123",

            current_price=Decimal("29500"),  # Ниже entry

        )

        assert updated is False

        new_sl = manager.get_levels("pos_123").sl_price

        assert new_sl == old_sl


class TestCleanup:

    """Тесты очистки старых позиций"""

    @pytest.fixture
    def mock_order_manager(self):

        return Mock()

    @pytest.fixture
    def manager(self, mock_order_manager):

        return StopLossTakeProfitManager(mock_order_manager)

    def test_close_position_levels(self, manager):
        """Проверяет закрытие отслеживания позиции"""

        manager.calculate_levels(

            position_id="pos_123",

            symbol="BTCUSDT",

            side="Long",

            entry_price=Decimal("30000"),

            entry_qty=Decimal("0.1"),

            current_atr=Decimal("500"),

        )

        assert manager.get_levels("pos_123") is not None

        closed = manager.close_position_levels("pos_123")

        assert closed is True

        assert manager.get_levels("pos_123") is None

    def test_close_nonexistent_position(self, manager):
        """Проверяет закрытие несуществующей позиции"""

        closed = manager.close_position_levels("pos_nonexistent")

        assert closed is False
