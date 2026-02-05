"""
Тесты для управления инструментами и нормализации ордеров.

Проверяют:
- Загрузку и кэширование информации об инструментах
- Округление цены по tickSize
- Округление количества по qtyStep
- Валидацию минимальных значений (qty, notional)
- Полный цикл нормализации и валидации
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch
from exchange.instruments import InstrumentsManager, normalize_order


class TestInstrumentsManager:
    """Тесты для InstrumentsManager."""

    @pytest.fixture
    def mock_client(self):
        """Создает мок REST клиента."""
        return Mock()

    @pytest.fixture
    def manager(self, mock_client):
        """Создает InstrumentsManager с мок клиентом."""
        return InstrumentsManager(mock_client, category="linear")

    def test_manager_initialization(self, manager):
        """Проверяет инициализацию менеджера."""
        assert manager.category == "linear"
        assert manager.instruments_cache == {}
        assert manager._cache_ttl == 3600

    def test_load_instruments_success(self, manager, mock_client):
        """Проверяет успешную загрузку инструментов."""
        mock_response = {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "priceScale": 2,
                        "qtyScale": 3,
                        "minNotional": "10",
                        "quotePrecision": 2,
                        "lotSizeFilter": {
                            "minOrderQty": "0.001",
                            "maxOrderQty": "1000",
                        },
                    },
                    {
                        "symbol": "ETHUSDT",
                        "priceScale": 2,
                        "qtyScale": 3,
                        "minNotional": "10",
                        "quotePrecision": 2,
                        "lotSizeFilter": {
                            "minOrderQty": "0.01",
                            "maxOrderQty": "10000",
                        },
                    },
                ]
            },
        }
        mock_client.get.return_value = mock_response

        success = manager.load_instruments()

        assert success is True
        assert len(manager.instruments_cache) == 2
        assert "BTCUSDT" in manager.instruments_cache
        assert "ETHUSDT" in manager.instruments_cache

    def test_load_instruments_with_cache_ttl(self, manager, mock_client):
        """Проверяет кэширование инструментов."""
        mock_response = {
            "retCode": 0,
            "result": {"list": [{"symbol": "BTCUSDT", "priceScale": 2, "qtyScale": 3}]},
        }
        mock_client.get.return_value = mock_response

        # Первая загрузка
        manager.load_instruments()
        assert mock_client.get.call_count == 1

        # Вторая загрузка без force_refresh - должна использовать кэш
        manager.load_instruments()
        assert mock_client.get.call_count == 1  # Не должно быть второго вызова

    def test_get_instrument_exists(self, manager, mock_client):
        """Проверяет получение информации об инструменте."""
        mock_response = {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "priceScale": 2,
                        "qtyScale": 3,
                        "minNotional": "10",
                        "quotePrecision": 2,
                        "lotSizeFilter": {
                            "minOrderQty": "0.001",
                            "maxOrderQty": "1000",
                        },
                    }
                ]
            },
        }
        mock_client.get.return_value = mock_response

        manager.load_instruments()
        instrument = manager.get_instrument("BTCUSDT")

        assert instrument is not None
        assert instrument["symbol"] == "BTCUSDT"
        assert instrument["tickSize"] == Decimal("0.01")
        assert instrument["qtyStep"] == Decimal("0.001")
        assert instrument["minOrderQty"] == Decimal("0.001")
        assert instrument["minNotional"] == Decimal("10")

    def test_get_instrument_not_found(self, manager):
        """Проверяет получение несуществующего инструмента."""
        instrument = manager.get_instrument("UNKNOWN")
        assert instrument is None


class TestNormalizePrice:
    """Тесты для нормализации цены."""

    @pytest.fixture
    def manager(self):
        """Создает менеджер с загруженными инструментами."""
        mock_client = Mock()
        mock_response = {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "priceScale": 2,  # tickSize = 0.01
                        "qtyScale": 3,
                        "minNotional": "10",
                        "quotePrecision": 2,
                        "lotSizeFilter": {
                            "minOrderQty": "0.001",
                            "maxOrderQty": "1000",
                        },
                    }
                ]
            },
        }
        mock_client.get.return_value = mock_response

        manager = InstrumentsManager(mock_client)
        manager.load_instruments()
        return manager

    def test_normalize_price_basic(self, manager):
        """Проверяет базовое округление цены."""
        # tickSize = 0.01
        normalized = manager.normalize_price("BTCUSDT", 30000.123)
        assert normalized == Decimal("30000.12")

    def test_normalize_price_rounds_up(self, manager):
        """Проверяет округление цены вверх."""
        normalized = manager.normalize_price("BTCUSDT", 30000.126)
        assert normalized == Decimal("30000.13")

    def test_normalize_price_exact(self, manager):
        """Проверяет цену, которая уже округлена правильно."""
        normalized = manager.normalize_price("BTCUSDT", 30000.00)
        assert normalized == Decimal("30000.00")

    def test_normalize_price_not_found(self, manager):
        """Проверяет нормализацию цены для несуществующего инструмента."""
        normalized = manager.normalize_price("UNKNOWN", 30000.0)
        assert normalized is None


class TestNormalizeQty:
    """Тесты для нормализации количества."""

    @pytest.fixture
    def manager(self):
        """Создает менеджер с загруженными инструментами."""
        mock_client = Mock()
        mock_response = {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "priceScale": 2,
                        "qtyScale": 3,  # qtyStep = 0.001
                        "minNotional": "10",
                        "quotePrecision": 2,
                        "lotSizeFilter": {
                            "minOrderQty": "0.001",
                            "maxOrderQty": "1000",
                        },
                    }
                ]
            },
        }
        mock_client.get.return_value = mock_response

        manager = InstrumentsManager(mock_client)
        manager.load_instruments()
        return manager

    def test_normalize_qty_basic(self, manager):
        """Проверяет базовое округление количества."""
        # qtyStep = 0.001
        normalized = manager.normalize_qty("BTCUSDT", 0.1234)
        assert normalized == Decimal("0.123")

    def test_normalize_qty_rounds_down(self, manager):
        """Проверяет что количество округляется вниз (не превышает)."""
        # ROUND_DOWN должен дать 0.123, а не 0.124
        normalized = manager.normalize_qty("BTCUSDT", 0.12399)
        assert normalized == Decimal("0.123")

    def test_normalize_qty_exact(self, manager):
        """Проверяет количество, которое уже округлено правильно."""
        normalized = manager.normalize_qty("BTCUSDT", 0.100)
        assert normalized == Decimal("0.100")

    def test_normalize_qty_not_found(self, manager):
        """Проверяет нормализацию количества для несуществующего инструмента."""
        normalized = manager.normalize_qty("UNKNOWN", 0.1)
        assert normalized is None


class TestValidateOrder:
    """Тесты для валидации ордера."""

    @pytest.fixture
    def manager(self):
        """Создает менеджер с загруженными инструментами."""
        mock_client = Mock()
        mock_response = {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "priceScale": 2,
                        "qtyScale": 3,
                        "minNotional": "10",  # Минимум 10 USDT
                        "quotePrecision": 2,
                        "lotSizeFilter": {
                            "minOrderQty": "0.001",  # Минимум 0.001 BTC
                            "maxOrderQty": "1000",
                        },
                    }
                ]
            },
        }
        mock_client.get.return_value = mock_response

        manager = InstrumentsManager(mock_client)
        manager.load_instruments()
        return manager

    def test_validate_order_valid(self, manager):
        """Проверяет валидный ордер."""
        is_valid, error_msg = manager.validate_order("BTCUSDT", 30000.0, 0.001)
        # 0.001 * 30000 = 30 USDT > 10 USDT (minNotional)
        assert is_valid is True
        assert error_msg == ""

    def test_validate_order_qty_too_small(self, manager):
        """Проверяет ордер с малым количеством."""
        is_valid, error_msg = manager.validate_order("BTCUSDT", 30000.0, 0.0005)
        # 0.0005 < 0.001 (minOrderQty)
        assert is_valid is False
        assert "minOrderQty" in error_msg

    def test_validate_order_notional_too_small(self, manager):
        """Проверяет ордер с малым notional."""
        # 0.01 * 30000 = 300 USDT > 10 USDT, но проверим с большим количеством
        # чтобы пройти minOrderQty, но не пройти minNotional
        is_valid, error_msg = manager.validate_order("BTCUSDT", 100.0, 0.001)
        # 0.001 * 100 = 0.1 USDT < 10 USDT (minNotional)
        assert is_valid is False
        assert "minNotional" in error_msg

    def test_validate_order_qty_too_large(self, manager):
        """Проверяет ордер с большим количеством."""
        is_valid, error_msg = manager.validate_order("BTCUSDT", 30000.0, 2000.0)
        # 2000 > 1000 (maxOrderQty)
        assert is_valid is False
        assert "maxOrderQty" in error_msg

    def test_validate_order_not_found(self, manager):
        """Проверяет валидацию для несуществующего инструмента."""
        is_valid, error_msg = manager.validate_order("UNKNOWN", 30000.0, 0.1)
        assert is_valid is False
        assert "not found" in error_msg


class TestNormalizeOrderFunction:
    """Тесты для функции normalize_order."""

    @pytest.fixture
    def manager(self):
        """Создает менеджер с загруженными инструментами."""
        mock_client = Mock()
        mock_response = {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "priceScale": 2,
                        "qtyScale": 3,
                        "minNotional": "10",
                        "quotePrecision": 2,
                        "lotSizeFilter": {
                            "minOrderQty": "0.001",
                            "maxOrderQty": "1000",
                        },
                    },
                    {
                        "symbol": "ETHUSDT",
                        "priceScale": 2,
                        "qtyScale": 3,
                        "minNotional": "10",
                        "quotePrecision": 2,
                        "lotSizeFilter": {
                            "minOrderQty": "0.01",
                            "maxOrderQty": "10000",
                        },
                    },
                ]
            },
        }
        mock_client.get.return_value = mock_response

        manager = InstrumentsManager(mock_client)
        manager.load_instruments()
        return manager

    def test_normalize_order_success(self, manager):
        """Проверяет успешную нормализацию ордера."""
        normalized_price, normalized_qty, is_valid, message = normalize_order(
            manager, "BTCUSDT", 30000.123, 0.1234
        )

        assert is_valid is True
        assert normalized_price == Decimal("30000.12")
        assert normalized_qty == Decimal("0.123")
        assert "validated" in message.lower()

    def test_normalize_order_qty_too_small(self, manager):
        """Проверяет нормализацию ордера с малым количеством."""
        normalized_price, normalized_qty, is_valid, message = normalize_order(
            manager, "BTCUSDT", 30000.0, 0.0005
        )

        assert is_valid is False
        assert "minOrderQty" in message

    def test_normalize_order_notional_too_small(self, manager):
        """Проверяет нормализацию ордера с малым notional."""
        normalized_price, normalized_qty, is_valid, message = normalize_order(
            manager, "BTCUSDT", 100.0, 0.001
        )

        assert is_valid is False
        assert "minNotional" in message

    def test_normalize_order_multiple_symbols(self, manager):
        """Проверяет нормализацию ордеров для разных инструментов."""
        # BTC
        price_btc, qty_btc, valid_btc, _ = normalize_order(
            manager, "BTCUSDT", 30000.123, 0.1234
        )
        assert valid_btc is True
        assert price_btc == Decimal("30000.12")
        assert qty_btc == Decimal("0.123")

        # ETH
        price_eth, qty_eth, valid_eth, _ = normalize_order(
            manager, "ETHUSDT", 1800.456, 0.567
        )
        assert valid_eth is True
        assert price_eth == Decimal("1800.46")
        assert qty_eth == Decimal("0.567")

    def test_normalize_order_unknown_symbol(self, manager):
        """Проверяет нормализацию ордера для неизвестного символа."""
        normalized_price, normalized_qty, is_valid, message = normalize_order(
            manager, "UNKNOWN", 30000.0, 0.1
        )

        assert is_valid is False
        assert "normalize" in message.lower() or "unknown" in message.lower()


class TestScaleToDecimal:
    """Тесты для конвертации scale в Decimal."""

    @pytest.fixture
    def manager(self):
        """Создает менеджер."""
        mock_client = Mock()
        return InstrumentsManager(mock_client)

    def test_scale_zero(self, manager):
        """Проверяет scale = 0."""
        result = manager._scale_to_decimal(0)
        assert result == Decimal("1")

    def test_scale_positive(self, manager):
        """Проверяет положительный scale."""
        result = manager._scale_to_decimal(2)
        assert result == Decimal("0.01")

        result = manager._scale_to_decimal(3)
        assert result == Decimal("0.001")

        result = manager._scale_to_decimal(8)
        assert result == Decimal("0.00000001")

    def test_scale_negative(self, manager):
        """Проверяет отрицательный scale."""
        result = manager._scale_to_decimal(-1)
        assert result == Decimal("1")  # Возвращает 1 для отрицательных


class TestEdgeCases:
    """Тесты на граничные случаи."""

    @pytest.fixture
    def manager(self):
        """Создает менеджер с загруженными инструментами."""
        mock_client = Mock()
        mock_response = {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "priceScale": 2,
                        "qtyScale": 8,  # Маленький qtyStep = 0.00000001
                        "minNotional": "10",
                        "quotePrecision": 2,
                        "lotSizeFilter": {
                            "minOrderQty": "0.001",
                            "maxOrderQty": "1000",
                        },
                    }
                ]
            },
        }
        mock_client.get.return_value = mock_response

        manager = InstrumentsManager(mock_client)
        manager.load_instruments()
        return manager

    def test_very_small_qty_step(self, manager):
        """Проверяет нормализацию с очень маленьким qtyStep."""
        # qtyStep = 0.00000001
        normalized = manager.normalize_qty("BTCUSDT", 0.12345678901)
        assert normalized == Decimal("0.12345678")

    def test_very_large_price(self, manager):
        """Проверяет нормализацию с очень большой ценой."""
        normalized = manager.normalize_price("BTCUSDT", 1000000.999)
        assert normalized == Decimal("1000001.00")

    def test_zero_price_normalization(self, manager):
        """Проверяет нормализацию нулевой цены."""
        normalized = manager.normalize_price("BTCUSDT", 0.0)
        assert normalized == Decimal("0.00")

    def test_zero_qty_validation(self, manager):
        """Проверяет валидацию нулевого количества."""
        is_valid, error_msg = manager.validate_order("BTCUSDT", 30000.0, 0.0)
        assert is_valid is False
        assert "minOrderQty" in error_msg
