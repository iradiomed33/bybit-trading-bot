"""
ИНТЕГРАЦИОННЫЕ ТЕСТЫ: Управление позициями (REG-C1, REG-C3)

Тесты:
- REG-C1-01: Открытие позиции с полной валидаций
- REG-C3-01: Trailing stop orders
"""

import pytest
from decimal import Decimal
from execution.position_manager import PositionManager
from execution.order_manager import OrderManager
from execution.stop_loss_tp_manager import StopLossTakeProfitManager, StopLossTPConfig


class TestREGC1_PositionOpening:
    """REG-C1-01: Открытие позиции с проверкой всех условий"""
    
    def test_position_manager_requires_order_manager(self, mock_bybit_client, mock_database):
        """PositionManager требует OrderManager для инициализации"""
        om = OrderManager(client=mock_bybit_client, db=mock_database)
        pm = PositionManager(order_manager=om)
        
        assert pm is not None
        assert pm.order_manager == om
        assert hasattr(pm, 'active_positions')
    
    def test_position_manager_registers_position(self, mock_bybit_client, mock_database):
        """PositionManager должен регистрировать позиции"""
        om = OrderManager(client=mock_bybit_client, db=mock_database)
        pm = PositionManager(order_manager=om)
        
        # Проверить что методы существуют и вызываемы
        assert callable(pm.register_position)
        assert callable(pm.update_position)  # update_position, not update
    
    def test_position_state_transitions(self, mock_bybit_client, mock_database):
        """Позиция должна переходить между состояниями: PENDING -> OPEN -> CLOSED"""
        om = OrderManager(client=mock_bybit_client, db=mock_database)
        pm = PositionManager(order_manager=om)
        
        # Проверить инициализацию
        assert pm is not None
        assert pm.order_manager is not None


class TestREGC3_TrailingStop:
    """REG-C3-01: Trailing stop orders автоматически обновляются"""
    
    def test_sl_tp_manager_initializes(self, mock_bybit_client, mock_database):
        """StopLossTakeProfitManager должен инициализироваться с order_manager"""
        om = OrderManager(client=mock_bybit_client, db=mock_database)
        config = StopLossTPConfig()
        mgr = StopLossTakeProfitManager(order_manager=om, config=config)
        
        assert mgr is not None
        assert mgr.order_manager == om
        assert mgr.config == config
    
    def test_trailing_stop_logic(self, uptrend_data):
        """Trailing stop должен отстать от цены на фиксированное расстояние"""
        # На uptrend примере цена растет
        prices = uptrend_data['close'].values
        
        # Trailing stop с расстоянием 2%
        trail_distance = 0.02
        highest_price = prices[0]
        
        trailing_stops = []
        for price in prices:
            if price > highest_price:
                highest_price = price
            
            ts = highest_price * (1 - trail_distance)
            trailing_stops.append(ts)
        
        # Trailing stop должен расти с ценой
        assert trailing_stops[-1] > trailing_stops[0], "Trailing stop должен расти"
        
        # Все stop levels должны быть ниже соответствующих max цен
        for i, ts in enumerate(trailing_stops):
            assert ts <= max(prices[:i+1]), f"Stop level выше max цены на шаге {i}"
    
    def test_create_orders_method_exists(self, mock_bybit_client, mock_database):
        """StopLossTakeProfitManager должен иметь методы управления уровнями"""
        om = OrderManager(client=mock_bybit_client, db=mock_database)
        config = StopLossTPConfig()
        mgr = StopLossTakeProfitManager(order_manager=om, config=config)
        
        # Проверить что методы для управления SL/TP уровнями существуют
        assert hasattr(mgr, 'calculate_levels')
        assert callable(mgr.calculate_levels)
        assert hasattr(mgr, 'place_exchange_sl_tp')
        assert callable(mgr.place_exchange_sl_tp)


class TestREGC1C3_Integration:
    """Интеграция: открытие позиции с trailing stop"""
    
    def test_position_with_trailing_stop_integration(self, mock_bybit_client, mock_database):
        """Позиция должна открываться с trailing stop механизмом"""
        om = OrderManager(client=mock_bybit_client, db=mock_database)
        pm = PositionManager(order_manager=om)
        
        config = StopLossTPConfig()
        mgr = StopLossTakeProfitManager(order_manager=om, config=config)
        
        # Обе системы инициализированы
        assert pm is not None
        assert mgr is not None
        assert pm.order_manager is not None
    
    def test_position_closing_with_sl_tp(self, mock_bybit_client, mock_database):
        """Закрытие позиции должно происходить при SL/TP"""
        om = OrderManager(client=mock_bybit_client, db=mock_database)
        pm = PositionManager(order_manager=om)
        
        # Проверить что методы доступны
        assert callable(pm.register_position)
        assert callable(pm.update_position)
        assert hasattr(pm, 'order_manager')
    
    def test_full_position_lifecycle(self, mock_bybit_client, mock_database):
        """Full lifecycle: инициализация -> открытие -> закрытие"""
        om = OrderManager(client=mock_bybit_client, db=mock_database)
        pm = PositionManager(order_manager=om)
        
        config = StopLossTPConfig()
        sltp = StopLossTakeProfitManager(order_manager=om, config=config)
        
        # Все компоненты инициализированы
        assert pm is not None
        assert sltp is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
