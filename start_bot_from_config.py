"""
Запуск бота с использованием настроек из config/bot_settings.json
Читает режим (paper/live) из конфигурации и запускает соответствующую команду
"""
import sys
from config import get_config
from logger import setup_logger
from bot.trading_bot import TradingBot
from bot.strategy_builder import StrategyBuilder

logger = setup_logger(__name__)

def main():
    try:
        # Загружаем конфигурацию
        cfg = get_config()
        
        # Читаем режим из конфигурации
        mode = cfg.get("trading.mode") or "paper"
        testnet = cfg.get("trading.testnet", True)
        
        # Получаем символ
        symbol = cfg.get("trading.symbol") or "BTCUSDT"
        
        logger.info("="*60)
        logger.info(f"Запуск бота из конфигурации")
        logger.info(f"Режим: {mode.upper()}")
        logger.info(f"Testnet: {testnet}")
        logger.info(f"Символ: {symbol}")
        logger.info("="*60)
        
        # Строим стратегии
        builder = StrategyBuilder(cfg)
        strategies = builder.build_strategies()
        
        # Создаем и запускаем бота
        bot = TradingBot(
            mode=mode,
            strategies=strategies,
            symbol=symbol,
            testnet=testnet,
            config=cfg
        )
        
        logger.info(f"Бот создан в режиме {mode.upper()}")
        bot.run()
        
    except KeyboardInterrupt:
        logger.info("\nОстановка бота...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
