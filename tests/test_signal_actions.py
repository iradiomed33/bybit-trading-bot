"""
Тесты для обработки сигналов и правил flip/add/ignore.

Проверяют:
- Определение действия для одинакового/противоположного направления
- Валидация ADD (пирамидинга)
- Валидация FLIP
- Обработка конфликтных сигналов
- Управление позициями при каждом действии
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock
from execution.position_signal_handler import (
    PositionSignalHandler,
    SignalActionConfig,
    SignalAction,
    SignalActionResult,
    PositionManager,
)


class TestSignalActionConfig:
    """Тесты конфигурации"""

    def test_default_config(self):
        """Проверяет значения по умолчанию"""
        config = SignalActionConfig()

        assert config.default_action == SignalAction.IGNORE
        assert config.long_signal_action == SignalAction.IGNORE
        assert config.short_signal_action == SignalAction.IGNORE
        assert config.max_pyramid_levels == 3
        assert config.flip_immediately is True

    def test_custom_config_allow_add(self):
        """Проверяет конфигурацию с разрешением ADD"""
        config = SignalActionConfig(
            long_signal_action=SignalAction.ADD,
            short_signal_action=SignalAction.ADD,
            max_pyramid_levels=5,
        )

        assert config.long_signal_action == SignalAction.ADD
        assert config.short_signal_action == SignalAction.ADD
        assert config.max_pyramid_levels == 5

    def test_custom_config_allow_flip(self):
        """Проверяет конфигурацию с разрешением FLIP"""
        config = SignalActionConfig(
            long_signal_action=SignalAction.FLIP,
            short_signal_action=SignalAction.FLIP,
        )

        assert config.long_signal_action == SignalAction.FLIP
        assert config.short_signal_action == SignalAction.FLIP


class TestNoPositionScenarios:
    """Тесты когда нет открытой позиции"""

    @pytest.fixture
    def handler(self):
        """Создает обработчик"""
        return PositionSignalHandler()

    def test_no_position_long_signal(self, handler):
        """При отсутствии позиции лонг сигнал обрабатывается"""
        result = handler.handle_signal(
            current_position=None,
            new_signal={"signal": "long", "confidence": 0.8},
            current_price=Decimal("30000"),
            account_balance=Decimal("10000"),
        )

        assert result.action_taken == SignalAction.IGNORE  # IGNORE = нет конфликта
        assert result.success is True
        assert "No position conflict" in result.message

    def test_no_position_short_signal(self, handler):
        """При отсутствии позиции шорт сигнал обрабатывается"""
        result = handler.handle_signal(
            current_position=None,
            new_signal={"signal": "short", "confidence": 0.8},
            current_price=Decimal("30000"),
            account_balance=Decimal("10000"),
        )

        assert result.action_taken == SignalAction.IGNORE
        assert result.success is True


class TestIgnoreAction:
    """Тесты действия IGNORE"""

    @pytest.fixture
    def handler(self):
        """Обработчик с IGNORE по умолчанию"""
        return PositionSignalHandler(SignalActionConfig(default_action=SignalAction.IGNORE))

    def test_ignore_same_direction_long(self, handler):
        """Игнорировать лонг сигнал если уже в лонге"""
        current_pos = {
            "symbol": "BTCUSDT",
            "side": "Long",
            "qty": Decimal("0.1"),
            "entry_price": Decimal("30000"),
        }

        result = handler.handle_signal(
            current_position=current_pos,
            new_signal={"signal": "long", "confidence": 0.8},
            current_price=Decimal("31000"),
            account_balance=Decimal("10000"),
        )

        assert result.action_taken == SignalAction.IGNORE
        assert result.success is False
        assert "Position conflict" in result.message

    def test_ignore_same_direction_short(self, handler):
        """Игнорировать шорт сигнал если уже в шорте"""
        current_pos = {
            "symbol": "BTCUSDT",
            "side": "Short",
            "qty": Decimal("0.1"),
            "entry_price": Decimal("30000"),
        }

        result = handler.handle_signal(
            current_position=current_pos,
            new_signal={"signal": "short", "confidence": 0.8},
            current_price=Decimal("29000"),
            account_balance=Decimal("10000"),
        )

        assert result.action_taken == SignalAction.IGNORE
        assert result.success is False
        assert "Position conflict" in result.message


class TestAddAction:
    """Тесты действия ADD (пирамидинг)"""

    @pytest.fixture
    def handler_with_add(self):
        """Обработчик с разрешением ADD"""
        config = SignalActionConfig(
            long_signal_action=SignalAction.ADD,
            short_signal_action=SignalAction.ADD,
            max_pyramid_levels=3,
            pyramid_qty_increase=Decimal("0.5"),
        )
        return PositionSignalHandler(config)

    def test_add_same_direction_long(self, handler_with_add):
        """Добавить к лонг позиции при лонг сигнале"""
        current_pos = {
            "symbol": "BTCUSDT",
            "side": "Long",
            "qty": Decimal("0.1"),
            "entry_price": Decimal("30000"),
            "pyramid_level": 1,
        }

        result = handler_with_add.handle_signal(
            current_position=current_pos,
            new_signal={"signal": "long", "confidence": 0.8},
            current_price=Decimal("31000"),
            account_balance=Decimal("10000"),
        )

        assert result.action_taken == SignalAction.ADD
        assert result.success is True
        assert result.old_qty == Decimal("0.1")
        # add_qty = 0.1 * 0.5 = 0.05
        assert result.new_qty == Decimal("0.15")

    def test_add_respects_max_pyramid_levels(self, handler_with_add):
        """Не добавлять если достигнут максимум пирамид"""
        current_pos = {
            "symbol": "BTCUSDT",
            "side": "Long",
            "qty": Decimal("0.1"),
            "entry_price": Decimal("30000"),
            "pyramid_level": 3,  # Максимум достигнут
        }

        result = handler_with_add.handle_signal(
            current_position=current_pos,
            new_signal={"signal": "long", "confidence": 0.8},
            current_price=Decimal("31000"),
            account_balance=Decimal("10000"),
        )

        assert result.action_taken == SignalAction.ADD
        assert result.success is False
        assert "Max pyramid levels" in result.message

    def test_add_respects_qty_increase_limit(self, handler_with_add):
        """Не добавлять если увеличение qty превышает лимит"""
        current_pos = {
            "symbol": "BTCUSDT",
            "side": "Long",
            "qty": Decimal("10.0"),  # Большая позиция
            "entry_price": Decimal("30000"),
            "pyramid_level": 1,
        }

        # Пытаемся добавить 10 * 0.5 = 5.0, но лимит max_position_qty_increase_percent = 50%
        result = handler_with_add.handle_signal(
            current_position=current_pos,
            new_signal={"signal": "long", "confidence": 0.8},
            current_price=Decimal("31000"),
            account_balance=Decimal("10000"),
        )

        # При цене 31000 и qty 10 notional = 310000 > 5000 лимит
        # Нужно проверить что qty_increase_percent соблюдается
        # 5.0 <= 10 * 0.5 (50% limit) - будет добавлено, но fail на notional
        assert result.success is False
        assert "exposure too high" in result.message.lower()

    def test_add_with_confidence_requirement(self):
        """Требовать высокую confidence для ADD"""
        config = SignalActionConfig(
            long_signal_action=SignalAction.ADD,
            require_higher_confidence=True,
            min_confidence_for_action=0.8,
        )
        handler = PositionSignalHandler(config)

        current_pos = {
            "symbol": "BTCUSDT",
            "side": "Long",
            "qty": Decimal("0.1"),
            "entry_price": Decimal("30000"),
            "pyramid_level": 1,
        }

        # Низкая confidence
        result = handler.handle_signal(
            current_position=current_pos,
            new_signal={"signal": "long", "confidence": 0.5},  # < 0.8
            current_price=Decimal("31000"),
            account_balance=Decimal("10000"),
        )

        assert result.success is False
        assert "Confidence too low" in result.message

        # Высокая confidence
        result = handler.handle_signal(
            current_position=current_pos,
            new_signal={"signal": "long", "confidence": 0.9},  # >= 0.8
            current_price=Decimal("31000"),
            account_balance=Decimal("10000"),
        )

        assert result.success is True


class TestFlipAction:
    """Тесты действия FLIP"""

    @pytest.fixture
    def handler_with_flip(self):
        """Обработчик с разрешением FLIP"""
        config = SignalActionConfig(
            long_signal_action=SignalAction.FLIP,
            short_signal_action=SignalAction.FLIP,
        )
        return PositionSignalHandler(config)

    def test_flip_long_to_short(self, handler_with_flip):
        """Flip из лонга в шорт"""
        current_pos = {
            "symbol": "BTCUSDT",
            "side": "Long",
            "qty": Decimal("0.1"),
            "entry_price": Decimal("30000"),
            "pyramid_level": 2,
        }

        result = handler_with_flip.handle_signal(
            current_position=current_pos,
            new_signal={"signal": "short", "confidence": 0.8},
            current_price=Decimal("32000"),
            account_balance=Decimal("10000"),
        )

        assert result.action_taken == SignalAction.FLIP
        assert result.success is True
        assert result.position_update["close_side"] == "Long"
        assert result.position_update["open_side"] == "short"
        assert result.position_update["close_qty"] == 0.1
        # После flip pyramid_level сбрасывается
        assert result.position_update["pyramid_level"] == 1

    def test_flip_short_to_long(self, handler_with_flip):
        """Flip из шорта в лонг"""
        current_pos = {
            "symbol": "BTCUSDT",
            "side": "Short",
            "qty": Decimal("0.2"),
            "entry_price": Decimal("31000"),
            "pyramid_level": 1,
        }

        result = handler_with_flip.handle_signal(
            current_position=current_pos,
            new_signal={"signal": "long", "confidence": 0.8},
            current_price=Decimal("29000"),
            account_balance=Decimal("10000"),
        )

        assert result.action_taken == SignalAction.FLIP
        assert result.success is True
        assert result.position_update["close_side"] == "Short"
        assert result.position_update["open_side"] == "long"
        assert result.position_update["close_qty"] == 0.2


class TestOppositeDirectionScenarios:
    """Тесты сценариев с противоположным направлением"""

    def test_opposite_signal_with_ignore_config(self):
        """При противоположном сигнале с IGNORE - сигнал игнорируется"""
        config = SignalActionConfig(
            long_signal_action=SignalAction.IGNORE,
            short_signal_action=SignalAction.IGNORE,
        )
        handler = PositionSignalHandler(config)

        current_pos = {
            "symbol": "BTCUSDT",
            "side": "Long",
            "qty": Decimal("0.1"),
            "entry_price": Decimal("30000"),
        }

        result = handler.handle_signal(
            current_position=current_pos,
            new_signal={"signal": "short", "confidence": 0.8},
            current_price=Decimal("31000"),
            account_balance=Decimal("10000"),
        )

        assert result.action_taken == SignalAction.IGNORE
        assert result.success is False

    def test_opposite_signal_with_flip_config(self):
        """При противоположном сигнале с FLIP - выполняется flip"""
        config = SignalActionConfig(
            long_signal_action=SignalAction.FLIP,
            short_signal_action=SignalAction.FLIP,
        )
        handler = PositionSignalHandler(config)

        current_pos = {
            "symbol": "BTCUSDT",
            "side": "Long",
            "qty": Decimal("0.1"),
            "entry_price": Decimal("30000"),
        }

        result = handler.handle_signal(
            current_position=current_pos,
            new_signal={"signal": "short", "confidence": 0.8},
            current_price=Decimal("31000"),
            account_balance=Decimal("10000"),
        )

        assert result.action_taken == SignalAction.FLIP
        assert result.success is True


class TestPositionManager:
    """Тесты PositionManager"""

    @pytest.fixture
    def mock_order_manager(self):
        """Мок для OrderManager"""
        return Mock()

    @pytest.fixture
    def manager(self, mock_order_manager):
        """Создает PositionManager"""
        config = SignalActionConfig(
            long_signal_action=SignalAction.ADD,
            short_signal_action=SignalAction.ADD,
        )
        return PositionManager(mock_order_manager, config)

    def test_register_position(self, manager):
        """Регистрация позиции"""
        manager.register_position(
            symbol="BTCUSDT",
            side="Long",
            entry_price=Decimal("30000"),
            qty=Decimal("0.1"),
            order_id="ord_123",
            strategy_id="trend_pullback",
        )

        pos = manager.get_position("BTCUSDT")
        assert pos is not None
        assert pos["side"] == "Long"
        assert pos["qty"] == Decimal("0.1")
        assert pos["pyramid_level"] == 1

    def test_add_to_position(self, manager):
        """Добавить к позиции"""
        manager.register_position(
            symbol="BTCUSDT",
            side="Long",
            entry_price=Decimal("30000"),
            qty=Decimal("1.0"),
            order_id="ord_123",
        )

        manager.add_to_position(
            symbol="BTCUSDT",
            add_qty=Decimal("0.5"),
            entry_price=Decimal("31000"),
            order_id="ord_124",
        )

        pos = manager.get_position("BTCUSDT")
        assert pos["qty"] == Decimal("1.5")
        assert pos["pyramid_level"] == 2
        # Средневзвешенная цена: (1.0 * 30000 + 0.5 * 31000) / 1.5 = 30333.33
        assert pos["entry_price"] == (
            Decimal("30000") * Decimal("1.0") + Decimal("31000") * Decimal("0.5")
        ) / Decimal("1.5")

    def test_close_position(self, manager):
        """Закрытие позиции"""
        manager.register_position(
            symbol="BTCUSDT",
            side="Long",
            entry_price=Decimal("30000"),
            qty=Decimal("0.1"),
            order_id="ord_123",
        )

        assert manager.has_position("BTCUSDT") is True

        closed = manager.close_position("BTCUSDT")

        assert closed is not None
        assert manager.has_position("BTCUSDT") is False

    def test_get_all_positions(self, manager):
        """Получить все позиции"""
        manager.register_position(
            symbol="BTCUSDT",
            side="Long",
            entry_price=Decimal("30000"),
            qty=Decimal("0.1"),
            order_id="ord_123",
        )

        manager.register_position(
            symbol="ETHUSDT",
            side="Short",
            entry_price=Decimal("2000"),
            qty=Decimal("1.0"),
            order_id="ord_124",
        )

        all_pos = manager.get_all_positions()

        assert len(all_pos) == 2
        assert "BTCUSDT" in all_pos
        assert "ETHUSDT" in all_pos
