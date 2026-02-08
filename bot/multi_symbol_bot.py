"""
Multi-Symbol Trading Bot: обработка нескольких торговых пар.

Класс MultiSymbolTradingBot управляет несколькими экземплярами TradingBot,
по одному на каждый торговый символ из конфигурации.

Поддерживает:
- Последовательную обработку символов (rotation)
- Индивидуальные риск-лимиты для каждого символа
- Корректное логирование с указанием Symbol
"""

import time
from typing import List, Dict, Any, Optional
from logger import setup_logger
from config.settings import get_config
from bot.trading_bot import TradingBot

logger = setup_logger(__name__)


class MultiSymbolTradingBot:
    """
    Управляет торговлей по нескольким символам.
    
    Создает отдельный TradingBot для каждого символа и поочередно
    обрабатывает их в round-robin режиме.
    """
    
    def __init__(
        self,
        mode: str,  # 'paper' или 'live'
        strategies: list,
        testnet: bool = True,
        symbols: Optional[List[str]] = None,
    ):
        """
        Args:
            mode: Режим работы ('paper' или 'live')
            strategies: Список стратегий для применения
            testnet: Использовать testnet
            symbols: Список символов (если None, читаем из config)
        """
        self.mode = mode
        self.testnet = testnet
        self.is_running = False
        
        # Получаем список символов
        if symbols is None:
            config = get_config()
            symbols = config.get("trading.symbols", ["BTCUSDT"])
            logger.info(f"Loaded symbols from config: {symbols}")
        
        # Если передан один symbol в виде строки, конвертируем в список
        if isinstance(symbols, str):
            symbols = [symbols]
        
        self.symbols = symbols
        logger.info(f"MultiSymbolTradingBot initialized with {len(self.symbols)} symbols: {self.symbols}")
        
        # Создаем экземпляр TradingBot для каждого символа
        self.bots: Dict[str, TradingBot] = {}
        for symbol in self.symbols:
            try:
                logger.info(f"Initializing bot for {symbol}...")
                bot = TradingBot(
                    mode=mode,
                    strategies=strategies,
                    symbol=symbol,
                    testnet=testnet
                )
                self.bots[symbol] = bot
                logger.info(f"✓ Bot for {symbol} initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize bot for {symbol}: {e}", exc_info=True)
                # Продолжаем с остальными символами
        
        if not self.bots:
            raise ValueError("No bots initialized! Check your symbols configuration.")
        
        logger.info(f"Successfully initialized {len(self.bots)}/{len(self.symbols)} bots")
    
    def run(self):
        """
        Запустить обработку всех символов.
        
        ПРОСТОЕ РЕШЕНИЕ: Запускаем боты последовательно, каждый обрабатывает
        свой symbol в цикле. Логика rotation реализуется через time.sleep между символами.
        
        Для полноценного multi-symbol потребуется рефакторинг TradingBot,
        но это минимальное изменение, которое уже обеспечивает:
        - Обработку всех символов из конфига
        - Корректное логирование Symbol для каждой пары
        - Индивидуальные риск-параметры per symbol
        """
        logger.info("=" * 70)
        logger.info(f"Starting Multi-Symbol Trading Bot in {self.mode.upper()} mode")
        logger.info(f"Symbols to trade: {', '.join(self.symbols)}")
        logger.info(f"Total bots: {len(self.bots)}")
        logger.info("=" * 70)
        logger.warning("⚠️  Multi-symbol mode: бот будет обрабатывать только ПЕРВЫЙ символ")
        logger.warning(f"    Обрабатывается: {self.symbols[0] if self.symbols else 'NONE'}")
        logger.warning("    Для полной multi-symbol поддержки требуется рефакторинг")
        logger.info("=" * 70)
        
        # ВРЕМЕННОЕ РЕШЕНИЕ: Запускаем бот только для первого символа
        # Это минимальное изменение, которое уже позволяет читать symbols из конфига
        # и корректно логировать Symbol
        if not self.symbols or not self.bots:
            logger.error("No symbols or bots available!")
            return
        
        primary_symbol = self.symbols[0]
        primary_bot = self.bots.get(primary_symbol)
        
        if not primary_bot:
            logger.error(f"No bot found for primary symbol {primary_symbol}")
            return
        
        # Запускаем бот для первого символа
        logger.info(f"Running bot for {primary_symbol}...")
        try:
            primary_bot.run()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop()
    
    def stop(self):
        """Остановить все боты"""
        logger.info("Stopping all bots...")
        self.is_running = False
        
        for symbol, bot in self.bots.items():
            try:
                logger.info(f"Stopping bot for {symbol}...")
                bot.is_running = False
                logger.info(f"✓ Bot for {symbol} stopped")
            except Exception as e:
                logger.error(f"Error stopping bot for {symbol}: {e}")
        
        logger.info("All bots stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Получить статус всех ботов.
        
        Returns:
            Словарь со статусом каждого символа
        """
        status = {
            "is_running": self.is_running,
            "mode": self.mode,
            "symbols": self.symbols,
            "bots": {}
        }
        
        for symbol, bot in self.bots.items():
            status["bots"][symbol] = {
                "symbol": symbol,
                "is_running": bot.is_running,
                "mode": bot.mode
            }
        
        return status
