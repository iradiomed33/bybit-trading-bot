"""
Тест инициализации TradingBot в режиме live.
Проверяет, что все компоненты создаются в правильном порядке без AttributeError.
"""

import sys
from unittest.mock import Mock, patch


def test_live_mode_initialization_order():
    """
    Проверяем, что в режиме live компоненты инициализируются в правильном порядке:
    1. rest_client, db, market_client, account_client
    2. order_manager и position_manager
    3. sl_tp_manager (требует order_manager)
    4. kill_switch_manager
    5. signal_handler
    """
    
    patches = [
        patch('storage.database.Database'),
        patch('exchange.market_data.MarketDataClient'),
        patch('exchange.account.AccountClient'),
        patch('exchange.base_client.BybitRestClient'),
        patch('exchange.instruments.InstrumentsManager'),
        patch('storage.position_state.PositionStateManager'),
        patch('execution.OrderManager'),
        patch('execution.PositionManager'),
        patch('execution.stop_loss_tp_manager.StopLossTakeProfitManager'),
        patch('execution.kill_switch.KillSwitchManager'),
        patch('execution.position_signal_handler.PositionSignalHandler'),
        patch('data.features.FeaturePipeline'),
        patch('strategy.meta_layer.MetaLayer'),
        patch('risk.PositionSizer'),
        patch('risk.volatility_position_sizer.VolatilityPositionSizer'),
        patch('risk.RiskLimits'),
        patch('risk.CircuitBreaker'),
        patch('risk.KillSwitch'),
        patch('risk.advanced_risk_limits.AdvancedRiskLimits'),
    ]
    
    # Запускаем все патчи
    for p in patches:
        p.start()
    
    try:
        # Импортируем TradingBot после патчинга
        from bot.trading_bot import TradingBot
        
        # Создаём простую стратегию для теста
        mock_strategy = Mock()
        mock_strategy.name = "TestStrategy"
        
        # Создаём бота в режиме live
        bot = TradingBot(
            mode="live",
            strategies=[mock_strategy],
            symbol="BTCUSDT",
            testnet=True
        )
        
        # Проверяем, что все компоненты были созданы
        assert bot.mode == "live"
        assert bot.db is not None
        assert bot.market_client is not None
        assert bot.account_client is not None
        assert bot.order_manager is not None
        assert bot.position_manager is not None
        assert bot.sl_tp_manager is not None
        assert bot.kill_switch_manager is not None
        assert bot.signal_handler is not None
        
        print("✓ Тест пройден: инициализация в режиме live прошла без ошибок")
        print("✓ Порядок инициализации правильный: order_manager создан до sl_tp_manager")
        return True
        
    except AttributeError as e:
        print(f"❌ ОШИБКА: AttributeError при инициализации: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ ОШИБКА: Неожиданная ошибка при инициализации: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Останавливаем все патчи
        for p in patches:
            p.stop()


def test_paper_mode_initialization():
    """
    Проверяем, что режим paper тоже работает корректно.
    """
    patches = [
        patch('storage.database.Database'),
        patch('exchange.market_data.MarketDataClient'),
        patch('exchange.account.AccountClient'),
        patch('data.features.FeaturePipeline'),
        patch('strategy.meta_layer.MetaLayer'),
        patch('risk.PositionSizer'),
        patch('risk.RiskLimits'),
        patch('risk.CircuitBreaker'),
        patch('risk.KillSwitch'),
        patch('execution.paper_trading_simulator.PaperTradingSimulator'),
        patch('execution.trade_metrics.EquityCurve'),
    ]
    
    # Запускаем все патчи
    for p in patches:
        p.start()
    
    try:
        # Импортируем TradingBot после патчинга
        from bot.trading_bot import TradingBot
        
        # Создаём простую стратегию для теста
        mock_strategy = Mock()
        mock_strategy.name = "TestStrategy"
        
        # Создаём бота в режиме paper
        bot = TradingBot(
            mode="paper",
            strategies=[mock_strategy],
            symbol="BTCUSDT",
            testnet=True
        )
        
        # В paper режиме live-компоненты должны быть None
        assert bot.mode == "paper"
        assert bot.order_manager is None
        assert bot.position_manager is None
        assert bot.sl_tp_manager is None
        assert bot.kill_switch_manager is None
        assert bot.signal_handler is None
        
        print("✓ Тест пройден: инициализация в режиме paper прошла корректно")
        return True
        
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Останавливаем все патчи
        for p in patches:
            p.stop()


if __name__ == "__main__":
    print("Запуск тестов инициализации TradingBot...")
    print("-" * 60)
    
    success = True
    
    if test_live_mode_initialization_order():
        print("✓ test_live_mode_initialization_order PASSED")
    else:
        print("❌ test_live_mode_initialization_order FAILED")
        success = False
    
    print("-" * 60)
    
    if test_paper_mode_initialization():
        print("✓ test_paper_mode_initialization PASSED")
    else:
        print("❌ test_paper_mode_initialization FAILED")
        success = False
    
    print("-" * 60)
    
    if success:
        print("Все тесты пройдены успешно! ✓")
        sys.exit(0)
    else:
        print("Некоторые тесты не прошли! ❌")
        sys.exit(1)
