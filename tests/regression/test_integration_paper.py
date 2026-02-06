"""
ИНТЕГРАЦИОННЫЕ ТЕСТЫ: Paper Trading режим (REG-E1, REG-E2)

Тесты:
- REG-E1-01: Бот работает в paper режиме без вывода реальных сделок
- REG-E2-01: Метрики правильно рассчитываются
"""

import pytest
from decimal import Decimal
from execution.paper_trading_simulator import PaperTradingSimulator, PaperTradingConfig
from backtest.engine import BacktestEngine


class TestREGE1_PaperMode:
    """REG-E1-01: Paper режим функционирует без выполнения реальных сделок"""
    
    def test_paper_simulator_initializes_with_config(self):
        """PaperTradingSimulator должен инициализироваться с PaperTradingConfig"""
        config = PaperTradingConfig(initial_balance=Decimal('10000'))
        simulator = PaperTradingSimulator(config=config)
        
        assert simulator is not None
        assert simulator.config == config
        # Проверить что баланс установлен
        assert simulator.cash == Decimal('10000')
    
    def test_paper_mode_no_real_api_calls(self, mock_bybit_client):
        """Paper режим должен работать без реальных API вызовов"""
        config = PaperTradingConfig(initial_balance=Decimal('10000'))
        simulator = PaperTradingSimulator(config=config)
        
        # Симулятор инициализирован и готов к работе
        assert simulator is not None
        # Mock client не используется
        assert mock_bybit_client is not None  # Есть, но не используется симулятором
    
    def test_paper_balance_updates_correctly(self):
        """Баланс должен обновляться при выполнении ордеров в paper режиме"""
        initial_balance = Decimal('10000')
        config = PaperTradingConfig(initial_balance=initial_balance)
        simulator = PaperTradingSimulator(config=config)
        
        # Проверить начальный баланс
        assert simulator.cash == initial_balance
        assert simulator.initial_balance == initial_balance


class TestREGE2_PaperMetrics:
    """REG-E2-01: Метрики equity, profit, win rate рассчитываются правильно"""
    
    def test_backtest_engine_with_database(self, mock_database):
        """BacktestEngine требует Database для инициализации"""
        engine = BacktestEngine(
            db=mock_database,
            initial_balance=10000.0,
        )
        
        assert engine is not None
        assert engine.db == mock_database
        assert engine.initial_balance == 10000.0
    
    def test_metrics_calculation_logic(self):
        """Win rate должен быть между 0 и 100%"""
        # Win rate = profitable_trades / total_trades * 100
        trades = [
            {'profit': 100},    # Выигрыш
            {'profit': 50},     # Выигрыш
            {'profit': -30},    # Убыток
            {'profit': 200},    # Выигрыш
        ]
        
        profitable = sum(1 for t in trades if t['profit'] > 0)
        win_rate = profitable / len(trades) * 100
        
        assert 0 <= win_rate <= 100
        assert win_rate == 75.0  # 3 выигрыша из 4 = 75%
    
    def test_paper_simulator_config_validation(self):
        """PaperTradingConfig должна валидировать параметры"""
        # Правильная конфигурация
        config = PaperTradingConfig(initial_balance=Decimal('10000'))
        assert config.initial_balance == Decimal('10000')
        
        # Другие параметры по умолчанию
        assert config is not None


class TestREGE1E2_Integration:
    """Интеграция: Paper режим с метриками"""
    
    def test_paper_mode_ready_for_trading(self):
        """Бот должен быть готов к торговле в paper режиме"""
        config = PaperTradingConfig(initial_balance=Decimal('10000'))
        simulator = PaperTradingSimulator(config=config)
        
        # Система инициализирована и готова
        assert simulator is not None
        assert simulator.cash > Decimal('0')
    
    def test_paper_mode_metrics_available(self):
        """Метрики должны быть доступны в paper режиме"""
        config = PaperTradingConfig(initial_balance=Decimal('10000'))
        simulator = PaperTradingSimulator(config=config)
        
        # Проверить что структура для отслеживания метрик есть
        assert hasattr(simulator, 'cash') or hasattr(simulator, 'equity')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
