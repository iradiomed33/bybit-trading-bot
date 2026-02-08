"""
Multi-Symbol Trading Bot: обработка нескольких торговых пар.

Класс MultiSymbolTradingBot управляет несколькими экземплярами TradingBot,
по одному на каждый торговый символ из конфигурации.

Поддерживает:
- Параллельную обработку символов (threading)
- Индивидуальные риск-лимиты для каждого символа
- Корректное логирование с указанием Symbol
"""

import time
import threading
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
        self.bot_threads: Dict[str, threading.Thread] = {}
        
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
    
    def _run_bot_in_thread(self, symbol: str, bot: TradingBot):
        """
        Запустить бот для символа в отдельном потоке.
        
        Args:
            symbol: Символ для торговли
            bot: Экземпляр TradingBot
        """
        logger.info(f"[Thread-{symbol}] Starting bot for {symbol}...")
        try:
            bot.run()
        except KeyboardInterrupt:
            logger.info(f"[Thread-{symbol}] Received interrupt signal")
        except Exception as e:
            logger.error(f"[Thread-{symbol}] Bot crashed: {e}", exc_info=True)
        finally:
            logger.info(f"[Thread-{symbol}] Bot stopped for {symbol}")
    
    def run(self):
        """
        Запустить обработку всех символов.
        
        Каждый бот запускается в отдельном потоке, что позволяет:
        - Параллельно обрабатывать все символы из конфига
        - Корректно логировать Symbol для каждой пары
        - Иметь индивидуальные риск-параметры per symbol
        """
        logger.info("=" * 70)
        logger.info(f"Starting Multi-Symbol Trading Bot in {self.mode.upper()} mode")
        logger.info(f"Symbols to trade: {', '.join(self.symbols)}")
        logger.info(f"Total bots: {len(self.bots)}")
        logger.info("=" * 70)
        
        if not self.symbols or not self.bots:
            logger.error("No symbols or bots available!")
            return
        
        self.is_running = True
        
        # Запускаем бот для каждого символа в отдельном потоке
        for symbol, bot in self.bots.items():
            logger.info(f"Starting thread for {symbol}...")
            thread = threading.Thread(
                target=self._run_bot_in_thread,
                args=(symbol, bot),
                name=f"Bot-{symbol}",
                daemon=True
            )
            thread.start()
            self.bot_threads[symbol] = thread
            logger.info(f"✓ Thread for {symbol} started")
        
        logger.info(f"All {len(self.bot_threads)} bot threads started")
        logger.info("=" * 70)
        
        # Ожидаем завершения всех потоков или прерывания
        try:
            # Кешируем список потоков для оптимизации
            threads = list(self.bot_threads.values())
            while self.is_running:
                # Проверяем раз в секунду, живы ли потоки
                if not any(t.is_alive() for t in threads):
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, stopping all bots...")
        finally:
            self.stop()
    
    def stop(self):
        """Остановить все боты"""
        logger.info("Stopping all bots...")
        self.is_running = False
        
        # Останавливаем все боты
        for symbol, bot in self.bots.items():
            try:
                logger.info(f"Stopping bot for {symbol}...")
                bot.is_running = False
                logger.info(f"✓ Bot for {symbol} stopped")
            except Exception as e:
                logger.error(f"Error stopping bot for {symbol}: {e}")
        
        # Ожидаем завершения всех потоков (с таймаутом)
        for symbol, thread in self.bot_threads.items():
            if thread.is_alive():
                logger.info(f"Waiting for thread {symbol} to finish...")
                thread.join(timeout=5.0)
                if thread.is_alive():
                    logger.warning(f"Thread {symbol} did not finish in time")
        
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
