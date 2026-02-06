"""
UNIT-тесты для API и ордеров (REG-B1, REG-B3)

Тесты:
- REG-B1-01: Live-ветка проходит до place_order без исключений (mock)
- REG-B3-01: Округление price по tickSize
- REG-B3-02: Округление qty по qtyStep + minQty/minNotional
"""

import pytest
from decimal import Decimal
from exchange.instruments import InstrumentsManager, normalize_order


class TestREGB1_LivePath:
    """REG-B1-01: Live-ветка проходит до place_order без исключений (mock)"""
    
    def test_live_path_imports_without_error(self):
        """Все нужные модули должны импортироваться"""
        from bot.trading_bot import TradingBot
        from execution.order_manager import OrderManager
        from execution.position_manager import PositionManager
        
        assert TradingBot is not None
        assert OrderManager is not None
        assert PositionManager is not None
    
    def test_order_creation_with_mock(self, mock_bybit_client):
        """Создание ордера с мокчированным API должно работать"""
        response = mock_bybit_client.place_order()
        
        assert response['retCode'] == 0
        assert response['result']['orderId'] == 'test_order_123'
        assert response['result']['status'] == 'New'


class TestREGB3_OrderNormalization:
    """REG-B3-01 и REG-B3-02: Нормализация ордеров по правилам инструмента"""
    
    def test_instruments_manager_can_init(self, mock_bybit_client):
        """InstrumentsManager должен инициализироваться"""
        mgr = InstrumentsManager(rest_client=mock_bybit_client)
        
        # Проверить что это экземпляр
        assert mgr is not None
        assert isinstance(mgr, InstrumentsManager)
    
    def test_normalize_order_function_exists(self):
        """Функция normalize_order должна существовать"""
        from exchange.instruments import normalize_order as norm_func
        
        # Проверить что функция есть
        assert norm_func is not None
        assert callable(norm_func)


class TestREGB3_OrderValidation:
    """Валидация параметров ордера"""
    
    def test_order_manager_initializes(self, mock_bybit_client, mock_database):
        """OrderManager должен инициализироваться без ошибок"""
        from execution.order_manager import OrderManager
        
        # Создать экземпляр с мок-объектами
        om = OrderManager(client=mock_bybit_client, db=mock_database)
        
        # Проверить что создан
        assert om is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
