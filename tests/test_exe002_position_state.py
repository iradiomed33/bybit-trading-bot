"""

Тесты для EXE-002: Position State Manager


DoD проверки:

1. После серии partial fills state совпадает с биржей

2. Нет "переворота" из-за неверного qty

3. reduceOnly для закрытий работает корректно

4. Reconciliation синхронизирует локальный state с биржей

"""


import pytest

from decimal import Decimal

from execution.position_state_manager import PositionStateManager


class TestPositionStateManager:

    """Базовые операции с позициями"""

    def test_open_long_position(self):
        """Открыть long позицию"""

        manager = PositionStateManager("BTCUSDT")

        manager.open_position(

            side="Long",

            qty=Decimal("1.0"),

            entry_price=Decimal("50000"),

            order_id="order_1",

        )

        assert manager.position.is_open()

        assert manager.position.side == "Long"

        assert manager.position.qty == Decimal("1.0")

        assert manager.position.avg_entry_price == Decimal("50000")

    def test_open_short_position(self):
        """Открыть short позицию"""

        manager = PositionStateManager("ETHUSDT")

        manager.open_position(

            side="Short",

            qty=Decimal("10.0"),

            entry_price=Decimal("3000"),

            order_id="order_1",

        )

        assert manager.position.is_open()

        assert manager.position.side == "Short"

        assert manager.position.qty == Decimal("10.0")

        assert manager.position.avg_entry_price == Decimal("3000")


class TestPartialFills:

    """DoD #1: После серии partial fills state совпадает с биржей"""

    def test_partial_fill_series_updates_avg_price(self):
        """Серия partial fills должна обновить среднюю цену"""

        manager = PositionStateManager("BTCUSDT")

        # Открываем позицию с 0.5 BTC @ 50000

        manager.open_position(

            side="Long",

            qty=Decimal("0.5"),

            entry_price=Decimal("50000"),

            order_id="order_1",

        )

        assert manager.position.qty == Decimal("0.5")

        assert manager.position.avg_entry_price == Decimal("50000")

        # Partial fill #1: добавляем 0.3 BTC @ 51000

        success, msg = manager.add_partial_fill(

            order_id="order_2",

            fill_qty=Decimal("0.3"),

            fill_price=Decimal("51000"),

            side="Long",

        )

        assert success

        assert manager.position.qty == Decimal("0.8")

        # avg = (0.5*50000 + 0.3*51000) / 0.8 = (25000 + 15300) / 0.8 = 50375

        expected_avg = (

            Decimal("0.5") * Decimal("50000") + Decimal("0.3") * Decimal("51000")

        ) / Decimal("0.8")

        assert manager.position.avg_entry_price == expected_avg

        # Partial fill #2: добавляем 0.2 BTC @ 49000

        success, msg = manager.add_partial_fill(

            order_id="order_3",

            fill_qty=Decimal("0.2"),

            fill_price=Decimal("49000"),

            side="Long",

        )

        assert success

        assert manager.position.qty == Decimal("1.0")

        expected_avg = (

            Decimal("0.5") * Decimal("50000")

            + Decimal("0.3") * Decimal("51000")

            + Decimal("0.2") * Decimal("49000")

        ) / Decimal("1.0")

        assert manager.position.avg_entry_price == expected_avg

    def test_reconcile_after_partial_fills(self):
        """После серии fills, reconcile с биржей"""

        manager = PositionStateManager("BTCUSDT")

        # Открываем 0.5 @ 50000

        manager.open_position("Long", Decimal("0.5"), Decimal("50000"), "order_1")

        # Добавляем 0.3 @ 51000

        manager.add_partial_fill("order_2", Decimal("0.3"), Decimal("51000"), "Long")

        # Добавляем 0.2 @ 49000

        manager.add_partial_fill("order_3", Decimal("0.2"), Decimal("49000"), "Long")

        local_qty = manager.position.qty

        local_avg = manager.position.avg_entry_price

        # Reconcile с биржей (должна быть sama)

        exchange_qty = Decimal("1.0")

        exchange_avg = (

            Decimal("0.5") * Decimal("50000")

            + Decimal("0.3") * Decimal("51000")

            + Decimal("0.2") * Decimal("49000")

        ) / Decimal("1.0")

        success, msg = manager.reconcile_with_exchange(exchange_qty, exchange_avg)

        assert success

        assert manager.position.qty == exchange_qty

        assert manager.position.avg_entry_price == exchange_avg


class TestReduceOnly:

    """DoD #2 и #3: Нет "переворота", reduceOnly работает"""

    def test_cannot_flip_position(self):
        """Нельзя перевернуть позицию через partial fill"""

        manager = PositionStateManager("BTCUSDT")

        # Открываем long 1.0 @ 50000

        manager.open_position("Long", Decimal("1.0"), Decimal("50000"), "order_1")

        # Пытаемся добавить Short (которая закроет) 0.5

        success, msg = manager.add_partial_fill(

            order_id="order_2",

            fill_qty=Decimal("0.5"),

            fill_price=Decimal("51000"),

            side="Short",  # Редукция (противоположная)

        )

        assert success

        assert manager.position.qty == Decimal("0.5")  # Уменьшили, не перевернули

        assert manager.position.side == "Long"  # Остались в long

    def test_partial_close_doesnt_flip(self):
        """Partial close не переворачивает позицию"""

        manager = PositionStateManager("BTCUSDT")

        # Long 2.0 @ 50000

        manager.open_position("Long", Decimal("2.0"), Decimal("50000"), "order_1")

        # Close 0.5 @ 51000

        success, msg = manager.close_position(

            close_qty=Decimal("0.5"),

            close_price=Decimal("51000"),

            order_id="order_2",

        )

        assert success

        assert manager.position.qty == Decimal("1.5")

        assert manager.position.side == "Long"  # Осталась long

        # Ещё close 1.0 @ 51500

        success, msg = manager.close_position(

            close_qty=Decimal("1.0"),

            close_price=Decimal("51500"),

            order_id="order_3",

        )

        assert success

        assert manager.position.qty == Decimal("0.5")

        assert manager.position.side == "Long"

    def test_full_close_clears_position(self):
        """Полное закрытие очищает позицию"""

        manager = PositionStateManager("BTCUSDT")

        manager.open_position("Long", Decimal("1.0"), Decimal("50000"), "order_1")

        success, msg = manager.close_position(

            close_qty=Decimal("1.0"),

            close_price=Decimal("51000"),

            order_id="order_2",

        )

        assert success

        assert not manager.position.is_open()

        assert manager.position.qty == Decimal("0")

        assert manager.position.side is None

    def test_cannot_close_more_than_open(self):
        """Нельзя закрыть больше чем открыто"""

        manager = PositionStateManager("BTCUSDT")

        manager.open_position("Long", Decimal("1.0"), Decimal("50000"), "order_1")

        success, msg = manager.close_position(

            close_qty=Decimal("2.0"),  # Больше чем есть

            close_price=Decimal("51000"),

            order_id="order_2",

        )

        assert not success

        assert "Cannot close" in msg

        assert manager.position.qty == Decimal("1.0")  # Не изменилась


class TestReconciliation:

    """DoD #4: Reconciliation синхронизирует с биржей"""

    def test_reconcile_corrects_qty(self):
        """Reconcile исправляет неверный qty"""

        manager = PositionStateManager("BTCUSDT")

        manager.open_position("Long", Decimal("1.0"), Decimal("50000"), "order_1")

        # Биржа говорит что у нас 0.95 (может быть fee или partial fill не синхронизировалась)

        success, msg = manager.reconcile_with_exchange(

            exchange_qty=Decimal("0.95"),

            exchange_avg_price=Decimal("50000"),

        )

        assert success

        assert manager.position.qty == Decimal("0.95")

    def test_reconcile_corrects_avg_price(self):
        """Reconcile исправляет неверную average price"""

        manager = PositionStateManager("BTCUSDT")

        manager.open_position("Long", Decimal("1.0"), Decimal("50000"), "order_1")

        # Локально думаем avg = 50000, но биржа говорит 50100

        success, msg = manager.reconcile_with_exchange(

            exchange_qty=Decimal("1.0"),

            exchange_avg_price=Decimal("50100"),

        )

        assert success

        assert manager.position.avg_entry_price == Decimal("50100")

    def test_reconcile_complex_scenario(self):
        """Сложный сценарий: несколько fills + reconcile"""

        manager = PositionStateManager("BTCUSDT")

        # Открываем 0.5 @ 50000

        manager.open_position("Long", Decimal("0.5"), Decimal("50000"), "order_1")

        # Добавляем 0.3 @ 51000

        manager.add_partial_fill("order_2", Decimal("0.3"), Decimal("51000"), "Long")

        # Локальное состояние: qty=0.8, avg=50375

        assert manager.position.qty == Decimal("0.8")

        # Но биржа говорит что-то немного другое (может быть комиссия повлияла)

        # Биржа говорит: qty=0.8, но avg из-за комиссии слегка выше

        success, msg = manager.reconcile_with_exchange(

            exchange_qty=Decimal("0.8"),

            exchange_avg_price=Decimal("50380"),

        )

        assert success

        assert manager.position.qty == Decimal("0.8")

        assert manager.position.avg_entry_price == Decimal("50380")


class TestShortPosition:

    """Тесты для short позиций"""

    def test_short_partial_fills(self):
        """Short позиция с partial fills"""

        manager = PositionStateManager("ETHUSDT")

        # Short 10 @ 3000

        manager.open_position("Short", Decimal("10"), Decimal("3000"), "order_1")

        # Добавляем short 5 @ 2950

        success, msg = manager.add_partial_fill("order_2", Decimal("5"), Decimal("2950"), "Short")

        assert success

        assert manager.position.qty == Decimal("15")

        # avg = (10*3000 + 5*2950) / 15 = (30000 + 14750) / 15 = 2983.33

        expected_avg = (Decimal("10") * Decimal("3000") + Decimal("5") * Decimal("2950")) / Decimal(

            "15"

        )

        assert manager.position.avg_entry_price == expected_avg

    def test_short_partial_close(self):
        """Закрыть часть short позиции"""

        manager = PositionStateManager("ETHUSDT")

        manager.open_position("Short", Decimal("10"), Decimal("3000"), "order_1")

        # Закрываем 3 @ 2950

        success, msg = manager.close_position(

            close_qty=Decimal("3"),

            close_price=Decimal("2950"),

            order_id="order_2",

        )

        assert success

        assert manager.position.qty == Decimal("7")

        assert manager.position.side == "Short"


class TestOrderTracking:

    """Отслеживание ордеров"""

    def test_order_history(self):
        """История ордеров"""

        manager = PositionStateManager("BTCUSDT")

        manager.open_position("Long", Decimal("1.0"), Decimal("50000"), "order_1")

        manager.add_partial_fill("order_2", Decimal("0.5"), Decimal("51000"), "Long")

        manager.close_position(Decimal("0.5"), Decimal("51500"), "order_3")

        orders = manager.get_orders()

        assert len(orders) >= 2

        assert orders[0]["order_id"] == "order_1"

        assert orders[0]["side"] == "Long"

        assert orders[0]["qty"] == Decimal("1.0")

    def test_reduce_only_flag(self):
        """Флаг reduceOnly на закрывающем ордере"""

        manager = PositionStateManager("BTCUSDT")

        manager.open_position("Long", Decimal("1.0"), Decimal("50000"), "order_1")

        manager.close_position(Decimal("0.5"), Decimal("51000"), "order_2")

        orders = manager.get_orders()

        close_order = [o for o in orders if o["order_id"] == "order_2"][0]

        assert close_order["reduce_only"] is True

        assert close_order["side"] == "Sell"  # Opposite side


class TestGetInfo:

    """Получение информации о позиции"""

    def test_position_info(self):
        """Получить информацию о позиции"""

        manager = PositionStateManager("BTCUSDT")

        manager.open_position("Long", Decimal("1.0"), Decimal("50000"), "order_1")

        info = manager.get_position_info()

        assert info["symbol"] == "BTCUSDT"

        assert info["side"] == "Long"

        assert info["qty"] == Decimal("1.0")

        assert info["avg_entry_price"] == Decimal("50000")

        assert info["is_open"] is True

    def test_closed_position_info(self):
        """Информация о закрытой позиции"""

        manager = PositionStateManager("BTCUSDT")

        manager.open_position("Long", Decimal("1.0"), Decimal("50000"), "order_1")

        manager.close_position(Decimal("1.0"), Decimal("51000"), "order_2")

        info = manager.get_position_info()

        assert info["is_open"] is False

        assert info["qty"] == Decimal("0")

        assert info["side"] is None


if __name__ == "__main__":

    pytest.main([__file__, "-v"])
