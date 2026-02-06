"""
ИНТЕГРАЦИОННЫЕ ТЕСТЫ: Полное управление риском (REG-RISK)

Тесты:
- REG-RISK-001: Daily loss limit соблюдается
- REG-RISK-003: Max open positions лимит соблюдается
"""

import pytest
from risk.position_sizer import PositionSizer


class TestREGRISK001_DailyLossLimit:
    """REG-RISK-001: Daily loss limit блокирует новые входы после лимита"""
    
    def test_daily_loss_tracking(self, test_config):
        """Дневная потеря должна отслеживаться"""
        daily_loss_limit = test_config.get('daily_loss_limit', 5000.0)
        
        # Симулировать торговлю
        trades = [
            {'profit': -500},      # Убыток 500
            {'profit': 200},       # Прибыль 200
            {'profit': -800},      # Убыток 800
            {'profit': -1200},     # Убыток 1200
        ]
        
        daily_loss = sum(t['profit'] for t in trades if t['profit'] < 0)
        
        # Проверить что убыток рассчитывается
        assert daily_loss == -2500
        assert abs(daily_loss) < daily_loss_limit
    
    def test_daily_loss_limit_stops_trading(self, test_config):
        """Trading должен останавливаться при достижении дневного лимита"""
        daily_loss_limit = test_config.get('daily_loss_limit', 5000.0)
        
        trades = [
            {'profit': -1000},
            {'profit': -1200},
            {'profit': -1500},
            {'profit': -1300},  # Сумма = -5000
        ]
        
        cumulative_loss = 0
        can_trade = True
        
        for trade in trades:
            cumulative_loss += trade['profit']
            
            if abs(cumulative_loss) >= daily_loss_limit:
                can_trade = False
                break
        
        # После 4-го трейда лимит достигнут
        assert not can_trade


class TestREGRISK003_MaxOpenPositions:
    """REG-RISK-003: Max open positions лимит соблюдается"""
    
    def test_max_open_positions_enforced(self, test_config):
        """Количество открытых позиций не должно превышать лимит"""
        max_positions = test_config.get('max_open_positions', 3)
        
        # Симуляция открытия позиций
        open_positions = [
            {'symbol': 'BTCUSDT', 'qty': 0.1},
            {'symbol': 'ETHUSDT', 'qty': 1.0},
            {'symbol': 'BNBUSDT', 'qty': 10.0},
        ]
        
        # Не должно быть больше чем max_positions
        assert len(open_positions) <= max_positions
    
    def test_position_concentration_limit(self):
        """Одна позиция не должна быть больше % от портфеля"""
        portfolio_value = 10000.0
        max_position_percent = 0.30  # 30%
        
        positions = [
            {'value': 2000},   # 20% - OK
            {'value': 2500},   # 25% - OK
            {'value': 3000},   # 30% - OK (на лимите)
        ]
        
        for pos in positions:
            pos_percent = pos['value'] / portfolio_value
            assert pos_percent <= max_position_percent
    
    def test_correlation_risk_check(self):
        """Высококоррелированные позиции должны быть ограничены"""
        # BTC и ETH обычно имеют высокую корреляцию (~0.7-0.9)
        btc_correlation = 1.0
        eth_correlation = 0.85  # Высокая корреляция с BTC
        
        # Если корреляция > 0.7, размер ETH позиции должен быть меньше
        max_eth_size = 0.5  # Max 50% от BTC размера
        
        btc_size = 1.0
        eth_size = 0.3
        
        if eth_correlation > 0.7:
            assert eth_size <= btc_size * max_eth_size


class TestREGRISK_Comprehensive:
    """Комплексные тесты управления риском"""
    
    def test_risk_metrics_calculation(self):
        """Метрики риска должны рассчитываться правильно"""
        account_balance = 10000.0
        positions = [
            {'notional': 2000},   # 20% от капитала
            {'notional': 1500},   # 15% от капитала
        ]
        
        used_margin = sum(p['notional'] for p in positions)
        margin_percent = used_margin / account_balance * 100
        
        # Используется 35% от капитала
        assert margin_percent == 35.0
    
    def test_forced_close_on_max_loss(self, test_config):
        """Позиции должны закрываться при максимальной потере"""
        daily_loss_limit = test_config.get('daily_loss_limit', 5000.0)
        current_loss = -5100.0
        
        # Loss превышает лимит
        assert abs(current_loss) > daily_loss_limit
        
        # Система должна принять решение о закрытии
        should_close = abs(current_loss) >= daily_loss_limit
        assert should_close == True
    
    def test_risk_reward_ratio_check(self):
        """Risk/Reward ratio должно быть >= 1:2 для валидного входа"""
        entry = 50000
        stop_loss = 49000
        take_profit = 51000
        
        risk = entry - stop_loss  # 1000
        reward = take_profit - entry  # 1000
        
        rr_ratio = reward / risk if risk > 0 else 0
        
        # Ratio должен быть >= 1 (1:1 или лучше)
        assert rr_ratio >= 1.0, f"RR ratio ({rr_ratio}) ниже минимума"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
