"""

Тесты для управления состоянием позиции и синхронизации с биржей.


Проверяют:

- Открытие и закрытие позиций

- Синхронизацию с биржей

- Обнаружение расхождений (ручное закрытие, изменения qty/price)

- Предотвращение дубликатов позиций

- Логирование всех изменений

"""


import pytest

from decimal import Decimal

from unittest.mock import Mock

from storage.position_state import PositionState, PositionStateManager, PositionStateStorage


class TestPositionState:

    """Тесты для модели PositionState."""

    def test_position_state_creation(self):
        """Проверяет создание состояния позиции."""

        pos = PositionState(

            symbol="BTCUSDT",

            side="Long",

            qty=Decimal("0.1"),

            entry_price=Decimal("30000"),

            order_id="12345",

            strategy_id="trend_pullback",

            opened_at=1234567890,

        )

        assert pos.symbol == "BTCUSDT"

        assert pos.side == "Long"

        assert pos.qty == Decimal("0.1")

        assert pos.entry_price == Decimal("30000")

        assert pos.order_id == "12345"

        assert pos.strategy_id == "trend_pullback"

    def test_position_state_to_dict(self):
        """Проверяет конвертацию в словарь."""

        pos = PositionState(

            symbol="BTCUSDT",

            side="Long",

            qty=Decimal("0.1"),

            entry_price=Decimal("30000"),

            order_id="12345",

            strategy_id="trend_pullback",

            opened_at=1234567890,

        )

        data = pos.to_dict()

        assert data["symbol"] == "BTCUSDT"

        assert data["qty"] == "0.1"  # Decimal -> str

        assert data["entry_price"] == "30000"

    def test_position_state_from_dict(self):
        """Проверяет создание из словаря."""

        data = {

            "symbol": "BTCUSDT",

            "side": "Long",

            "qty": "0.1",

            "entry_price": "30000",

            "order_id": "12345",

            "strategy_id": "trend_pullback",

            "opened_at": 1234567890,

        }

        pos = PositionState.from_dict(data)

        assert pos.symbol == "BTCUSDT"

        assert pos.qty == Decimal("0.1")

        assert pos.entry_price == Decimal("30000")


class TestPositionStateManager:

    """Тесты для PositionStateManager."""

    @pytest.fixture
    def mock_account_client(self):
        """Создает мок AccountClient."""

        return Mock()

    @pytest.fixture
    def manager(self, mock_account_client):
        """Создает PositionStateManager."""

        return PositionStateManager(mock_account_client, "BTCUSDT")

    def test_manager_initialization(self, manager):
        """Проверяет инициализацию менеджера."""

        assert manager.symbol == "BTCUSDT"

        assert manager.position is None

    def test_open_position(self, manager):
        """Проверяет открытие позиции."""

        manager.open_position(

            side="Long",

            qty=Decimal("0.1"),

            entry_price=Decimal("30000"),

            order_id="12345",

            strategy_id="trend_pullback",

        )

        assert manager.has_position() is True

        pos = manager.get_position()

        assert pos.side == "Long"

        assert pos.qty == Decimal("0.1")

        assert pos.entry_price == Decimal("30000")

    def test_cannot_open_duplicate_position(self, manager):
        """Проверяет что нельзя открыть дубликат позиции."""

        manager.open_position(

            side="Long",

            qty=Decimal("0.1"),

            entry_price=Decimal("30000"),

            order_id="12345",

            strategy_id="trend_pullback",

        )

        # Попытка открыть еще одну

        manager.open_position(

            side="Long",

            qty=Decimal("0.2"),

            entry_price=Decimal("31000"),

            order_id="12346",

            strategy_id="mean_reversion",

        )

        # Первая позиция остается

        pos = manager.get_position()

        assert pos.qty == Decimal("0.1")

    def test_close_position(self, manager):
        """Проверяет закрытие позиции."""

        manager.open_position(

            side="Long",

            qty=Decimal("0.1"),

            entry_price=Decimal("30000"),

            order_id="12345",

            strategy_id="trend_pullback",

        )

        closed_pos = manager.close_position()

        assert closed_pos is not None

        assert closed_pos.qty == Decimal("0.1")

        assert manager.has_position() is False

    def test_close_nonexistent_position(self, manager):
        """Проверяет закрытие несуществующей позиции."""

        result = manager.close_position()

        assert result is None

        assert manager.has_position() is False


class TestPositionSync:

    """Тесты для синхронизации позиции с биржей."""

    @pytest.fixture
    def mock_account_client(self):
        """Создает мок AccountClient."""

        return Mock()

    @pytest.fixture
    def manager(self, mock_account_client):
        """Создает PositionStateManager."""

        return PositionStateManager(mock_account_client, "BTCUSDT")

    def test_sync_position_success(self, manager, mock_account_client):
        """Проверяет успешную синхронизацию позиции."""

        # Открываем позицию локально

        manager.open_position(

            side="Long",

            qty=Decimal("0.1"),

            entry_price=Decimal("30000"),

            order_id="12345",

            strategy_id="trend_pullback",

        )

        # Мокируем ответ с биржи

        mock_account_client.get_positions.return_value = {

            "retCode": 0,

            "result": {

                "list": [

                    {

                        "symbol": "BTCUSDT",

                        "side": "Buy",

                        "size": "0.1",

                        "avgPrice": "30050",

                        "markPrice": "30100",

                        "unrealPnl": "5",

                    }

                ]

            },

        }

        success = manager.sync_with_exchange()

        assert success is True

        pos = manager.get_position()

        assert pos.exchange_qty == Decimal("0.1")

        assert pos.mark_price == Decimal("30100")

        assert pos.sync_count == 1

    def test_sync_detects_manual_close(self, manager, mock_account_client):
        """Проверяет обнаружение ручного закрытия позиции."""

        # Открываем позицию локально

        manager.open_position(

            side="Long",

            qty=Decimal("0.1"),

            entry_price=Decimal("30000"),

            order_id="12345",

            strategy_id="trend_pullback",

        )

        # Мокируем пустой список позиций (позиция закрыта на бирже)

        mock_account_client.get_positions.return_value = {

            "retCode": 0,

            "result": {"list": []},

        }

        success = manager.sync_with_exchange()

        assert success is True

        assert manager.has_position() is False  # Позиция была закрыта

    def test_sync_detects_qty_mismatch(self, manager, mock_account_client):
        """Проверяет обнаружение расхождения в количестве."""

        manager.open_position(

            side="Long",

            qty=Decimal("0.1"),

            entry_price=Decimal("30000"),

            order_id="12345",

            strategy_id="trend_pullback",

        )

        # Мокируем ответ с биржи с другим количеством

        mock_account_client.get_positions.return_value = {

            "retCode": 0,

            "result": {

                "list": [

                    {

                        "symbol": "BTCUSDT",

                        "side": "Buy",

                        "size": "0.05",  # Другое количество (вероятно, частичное закрытие)

                        "avgPrice": "30000",

                        "markPrice": "30100",

                        "unrealPnl": "5",

                    }

                ]

            },

        }

        success = manager.sync_with_exchange()

        assert success is True

        pos = manager.get_position()

        assert pos.discrepancy_detected is True

        assert "Qty mismatch" in pos.discrepancy_details

    def test_sync_detects_price_mismatch(self, manager, mock_account_client):
        """Проверяет обнаружение расхождения в цене входа."""

        manager.open_position(

            side="Long",

            qty=Decimal("0.1"),

            entry_price=Decimal("30000"),

            order_id="12345",

            strategy_id="trend_pullback",

        )

        # Мокируем ответ с другой средней ценой (более 1% разницы)

        mock_account_client.get_positions.return_value = {

            "retCode": 0,

            "result": {

                "list": [

                    {

                        "symbol": "BTCUSDT",

                        "side": "Buy",

                        "size": "0.1",

                        "avgPrice": "30500",  # 1.67% отличие

                        "markPrice": "30100",

                        "unrealPnl": "5",

                    }

                ]

            },

        }

        success = manager.sync_with_exchange()

        assert success is True

        pos = manager.get_position()

        assert pos.discrepancy_detected is True

        assert "Entry price mismatch" in pos.discrepancy_details

    def test_sync_calculates_pnl(self, manager, mock_account_client):
        """Проверяет расчет PnL при синхронизации."""

        manager.open_position(

            side="Long",

            qty=Decimal("0.1"),

            entry_price=Decimal("30000"),

            order_id="12345",

            strategy_id="trend_pullback",

        )

        mock_account_client.get_positions.return_value = {

            "retCode": 0,

            "result": {

                "list": [

                    {

                        "symbol": "BTCUSDT",

                        "side": "Buy",

                        "size": "0.1",

                        "avgPrice": "30000",

                        "markPrice": "31000",  # +1000

                        "unrealPnl": "100",  # 0.1 * 1000

                    }

                ]

            },

        }

        manager.sync_with_exchange()

        pos = manager.get_position()

        assert pos.pnl == Decimal("100")

        # PnL% = 100 / (30000 * 0.1) * 100 = 3.33%

        assert float(pos.pnl_percent) > 3.3 and float(pos.pnl_percent) < 3.4

    def test_sync_with_no_position(self, manager, mock_account_client):
        """Проверяет синхронизацию когда нет локальной позиции."""

        success = manager.sync_with_exchange()

        assert success is True

        mock_account_client.get_positions.assert_not_called()

    def test_sync_handles_api_error(self, manager, mock_account_client):
        """Проверяет обработку ошибки API."""

        manager.open_position(

            side="Long",

            qty=Decimal("0.1"),

            entry_price=Decimal("30000"),

            order_id="12345",

            strategy_id="trend_pullback",

        )

        mock_account_client.get_positions.return_value = {

            "retCode": 1,

            "retMsg": "API error",

        }

        success = manager.sync_with_exchange()

        assert success is False


class TestPositionValidation:

    """Тесты для валидации позиции."""

    @pytest.fixture
    def mock_account_client(self):
        """Создает мок AccountClient."""

        return Mock()

    @pytest.fixture
    def manager(self, mock_account_client):
        """Создает PositionStateManager."""

        return PositionStateManager(mock_account_client, "BTCUSDT")

    def test_validate_no_position(self, manager):
        """Проверяет валидацию без позиции."""

        is_valid, error = manager.validate_position()

        assert is_valid is True

        assert error == ""

    def test_validate_healthy_position(self, manager):
        """Проверяет валидацию здоровой позиции."""

        manager.open_position(

            side="Long",

            qty=Decimal("0.1"),

            entry_price=Decimal("30000"),

            order_id="12345",

            strategy_id="trend_pullback",

        )

        is_valid, error = manager.validate_position()

        assert is_valid is True

        assert error == ""

    def test_validate_side_mismatch_is_critical(self, manager, mock_account_client):
        """Проверяет что Side mismatch - критическая ошибка."""

        manager.open_position(

            side="Long",

            qty=Decimal("0.1"),

            entry_price=Decimal("30000"),

            order_id="12345",

            strategy_id="trend_pullback",

        )

        # Симулируем обнаружение расхождения

        manager.position.discrepancy_detected = True

        manager.position.discrepancy_details = "Side mismatch: local=Long, exchange=Short"

        is_valid, error = manager.validate_position()

        assert is_valid is False

        assert "Side mismatch" in error

    def test_validate_position_closed_unexpectedly(self, manager):
        """Проверяет валидацию при неожиданном закрытии позиции."""

        manager.open_position(

            side="Long",

            qty=Decimal("0.1"),

            entry_price=Decimal("30000"),

            order_id="12345",

            strategy_id="trend_pullback",

        )

        # Симулируем расхождение: позиция закрыта на бирже

        manager.position.discrepancy_detected = True

        manager.position.discrepancy_details = "Qty mismatch: local=0.1, exchange=0"

        manager.position.exchange_qty = Decimal("0")

        is_valid, error = manager.validate_position()

        assert is_valid is False

        assert "closed unexpectedly" in error.lower()


class TestPositionStateStorage:

    """Тесты для хранилища состояния позиций."""

    @pytest.fixture
    def mock_db(self):
        """Создает мок Database."""

        return Mock()

    @pytest.fixture
    def storage(self, mock_db):
        """Создает PositionStateStorage."""

        return PositionStateStorage(mock_db)

    def test_save_position_state(self, storage, mock_db):
        """Проверяет сохранение состояния позиции."""

        pos = PositionState(

            symbol="BTCUSDT",

            side="Long",

            qty=Decimal("0.1"),

            entry_price=Decimal("30000"),

            order_id="12345",

            strategy_id="trend_pullback",

            opened_at=1234567890,

        )

        success = storage.save_position_state(pos)

        assert success is True

        mock_db.execute.assert_called_once()

    def test_save_position_state_with_error(self, storage, mock_db):
        """Проверяет обработку ошибки при сохранении."""

        mock_db.execute.side_effect = Exception("DB error")

        pos = PositionState(

            symbol="BTCUSDT",

            side="Long",

            qty=Decimal("0.1"),

            entry_price=Decimal("30000"),

            order_id="12345",

            strategy_id="trend_pullback",

            opened_at=1234567890,

        )

        success = storage.save_position_state(pos)

        assert success is False

    def test_get_last_position(self, storage, mock_db):
        """Проверяет получение последней позиции."""

        mock_db.query.return_value = [

            {

                "symbol": "BTCUSDT",

                "side": "Long",

                "qty": "0.1",

                "entry_price": "30000",

                "order_id": "12345",

                "strategy_id": "trend_pullback",

                "opened_at": 1234567890,

            }

        ]

        pos = storage.get_last_position("BTCUSDT")

        assert pos is not None

        assert pos.symbol == "BTCUSDT"

        assert pos.qty == Decimal("0.1")

    def test_get_last_position_not_found(self, storage, mock_db):
        """Проверяет получение позиции когда нет данных."""

        mock_db.query.return_value = []

        pos = storage.get_last_position("BTCUSDT")

        assert pos is None

    def test_get_position_history(self, storage, mock_db):
        """Проверяет получение истории позиций."""

        mock_db.query.return_value = [

            {

                "symbol": "BTCUSDT",

                "side": "Long",

                "qty": "0.1",

                "entry_price": "30000",

                "order_id": "12345",

                "strategy_id": "trend_pullback",

                "opened_at": 1234567890,

            },

            {

                "symbol": "BTCUSDT",

                "side": "Short",

                "qty": "0.2",

                "entry_price": "35000",

                "order_id": "12346",

                "strategy_id": "mean_reversion",

                "opened_at": 1234567900,

            },

        ]

        positions = storage.get_position_history("BTCUSDT", limit=10)

        assert len(positions) == 2

        assert positions[0].side == "Long"

        assert positions[1].side == "Short"
