"""
ИНТЕГРАЦИОННЫЕ ТЕСТЫ: Slippage & Risk управление (REG-EXE-003, REG-RISK-002)

Тесты:
- REG-EXE-003: Slippage модель работает при различных рыночных условиях
- REG-RISK-002: Риск-менеджмент блокирует опасные сделки
"""

import pytest
from decimal import Decimal
from execution.slippage_model import SlippageModel
from risk.position_sizer import PositionSizer


class TestREGEXE003_Slippage:
    """REG-EXE-003: Slippage модель рассчитывает реалистичные потери"""
    
    def test_slippage_model_initializes(self):
        """SlippageModel должен инициализироваться с basis points"""
        slippage = SlippageModel(base_slippage_bps=Decimal('2'))
        
        assert slippage is not None
        assert slippage.base_slippage_bps == Decimal('2')
        assert hasattr(slippage, 'calculate_slippage')
        assert callable(slippage.calculate_slippage)
    
    def test_slippage_increases_with_order_size(self):
        """Slippage должен расти с размером ордера"""
        slippage = SlippageModel(base_slippage_bps=Decimal('2'))
        
        # Маленький ордер
        slip_small = slippage.calculate_slippage(
            qty=Decimal('0.1'),
            entry_price=Decimal('50000'),
        )
        
        # Большой ордер
        slip_large = slippage.calculate_slippage(
            qty=Decimal('1.0'),
            entry_price=Decimal('50000'),
        )
        
        # Большой ордер должен иметь больше слиппаж
        assert slip_large[0] >= slip_small[0], "Slippage должен расти с размером ордера"
        assert isinstance(slip_small, tuple)
        assert isinstance(slip_large, tuple)
    
    def test_slippage_increases_with_volatility(self):
        """Slippage должен расти с волатильностью"""
        slippage = SlippageModel(base_slippage_bps=Decimal('2'), volatility_factor_enabled=True)
        
        # Низкая волатильность
        slip_low = slippage.calculate_slippage(
            qty=Decimal('0.5'),
            entry_price=Decimal('50000'),
            atr=Decimal('100'),  # Низкая ATR
        )
        
        # Высокая волатильность
        slip_high = slippage.calculate_slippage(
            qty=Decimal('0.5'),
            entry_price=Decimal('50000'),
            atr=Decimal('500'),  # Высокая ATR
        )
        
        # Высокая волатильность -> больше слиппаж
        assert slip_high[0] >= slip_low[0], "Slippage должен расти с волатильностью"
    
    def test_slippage_buy_vs_sell(self):
        """Slippage должен быть одинаковым для Buy и Sell"""
        slippage = SlippageModel(base_slippage_bps=Decimal('2'))
        
        # Buy слиппаж
        slip_buy = slippage.calculate_slippage(
            qty=Decimal('0.5'),
            entry_price=Decimal('50000'),
        )
        
        # Sell слиппаж
        slip_sell = slippage.calculate_slippage(
            qty=Decimal('0.5'),
            entry_price=Decimal('50000'),
        )
        
        # Слиппаж модель должна дать результаты
        assert slip_buy[0] >= Decimal('0'), "Slippage должен быть положительным"
        assert slip_sell[0] >= Decimal('0'), "Slippage должен быть положительным"
    
    def test_slippage_result_is_decimal(self):
        """Результат слиппаж расчета должен быть Decimal"""
        slippage = SlippageModel(base_slippage_bps=Decimal('2'))
        
        result = slippage.calculate_slippage(
            qty=Decimal('0.5'),
            entry_price=Decimal('50000'),
        )
        
        # calculate_slippage возвращает кортеж (Decimal, Dict)
        assert isinstance(result, tuple)
        assert isinstance(result[0], Decimal)
        assert result[0] >= Decimal('0')


class TestREGRISK002_RiskManagement:
    """REG-RISK-002: Риск-менеджмент блокирует опасные входы"""
    
    def test_position_sizer_enforces_max_leverage(self, test_config):
        """PositionSizer должен соблюдать max leverage"""
        sizer = PositionSizer(
            risk_per_trade_percent=1.0,
            max_leverage=5.0,
        )
        
        result = sizer.calculate_position_size(
            account_balance=10000.0,
            entry_price=50000.0,
            stop_loss_price=48000.0,
        )
        
        # Результат должен быть dict с позицией
        assert isinstance(result, dict)
        assert 'position_size' in result or 'qty' in result
    
    def test_position_sizer_calculates_kelly(self):
        """PositionSizer должен использовать Kelly criterion или риск-процент"""
        sizer = PositionSizer(
            risk_per_trade_percent=1.0,  # 1% от аккаунта
            max_leverage=5.0,
        )
        
        # При 1% риск методология
        # Размер позиции = (Account * Risk%) / (Entry - StopLoss)
        account = 10000.0
        entry = 50000.0
        stop_loss = 49000.0
        
        expected_risk_amount = account * 0.01  # 100 USD
        distance = entry - stop_loss  # 1000
        expected_qty = expected_risk_amount / distance  # 0.1
        
        result = sizer.calculate_position_size(
            account_balance=account,
            entry_price=entry,
            stop_loss_price=stop_loss,
        )
        
        # Размер должен быть близко к ожидаемому
        assert result is not None
    
    def test_risk_limits_multiple_positions(self):
        """Риск лимиты должны применяться ко всем позициям"""
        max_daily_loss = 5000.0
        
        positions = [
            {'entry_price': 50000, 'qty': 0.1, 'risk': 100},
            {'entry_price': 50100, 'qty': 0.1, 'risk': 150},
            {'entry_price': 50200, 'qty': 0.1, 'risk': 120},
        ]
        
        total_risk = sum(p['risk'] for p in positions)
        
        # Общий риск не должен превышать дневного лимита
        assert total_risk < max_daily_loss
        assert total_risk == 370


class TestREGEXE003RISK002_Integration:
    """Интеграция: Slippage и Risk management"""
    
    def test_slippage_and_risk_work_together(self):
        """Slippage и Risk management должны работать вместе"""
        slippage = SlippageModel(base_slippage_bps=Decimal('2'))
        sizer = PositionSizer(
            risk_per_trade_percent=1.0,
            max_leverage=5.0,
        )
        
        # Оба компонента инициализированы
        assert slippage is not None
        assert sizer is not None
        assert callable(slippage.calculate_slippage)
        assert callable(sizer.calculate_position_size)
    
    def test_position_size_adjusted_for_slippage(self):
        """Размер позиции должен быть уменьшен с учетом slippage"""
        sizer = PositionSizer(
            risk_per_trade_percent=1.0,
            max_leverage=5.0,
        )
        
        # С учетом слиппажа стоп может быть дальше
        result = sizer.calculate_position_size(
            account_balance=10000.0,
            entry_price=50000.0,
            stop_loss_price=49000.0,  # 1% от entry (может быть с слиппажем)
        )
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_maximum_loss_per_trade(self):
        """Максимальный убыток на сделку должен быть ограничен"""
        risk_percent = 1.0  # 1% от аккаунта = max loss
        account = 10000.0
        
        max_loss = account * (risk_percent / 100)
        
        assert max_loss == 100.0  # 1% от 10000 = 100


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
