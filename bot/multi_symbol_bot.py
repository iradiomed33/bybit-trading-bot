"""
TASK-004 (P0): MultiSymbol Trading Bot Orchestrator

Координирует запуск нескольких TradingBot инстансов (по одному на символ),
гарантируя что каждый имеет свои (не шаренные) экземпляры стратегий.

Архитектура:
- MultiSymbolBot: Главный оркестратор
- TradingBot: Один бот на один символ
- StrategyFactory: Создает per-symbol стратегии

Flow:
1. MultiSymbolBot инициализируется с list символов
2. Для каждого символа:
   a. Создаёт НОВЫЕ экземпляры стратегий через StrategyFactory
   b. Создаёт TradingBot с этими стратегиями
   c. Запускает TradingBot в отдельном потоке
3. Все TradingBot работают параллельно, с собственными стратегиями
"""

import threading
import time
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json

from logger import setup_logger
from bot.trading_bot import TradingBot
from bot.strategy_factory import StrategyFactory

logger = setup_logger(__name__)


@dataclass
class MultiSymbolConfig:
    """Конфигурация для MultiSymbolBot"""
    
    symbols: List[str]  # ["BTCUSDT", "ETHUSDT", ...]
    mode: str = "paper"  # "paper" или "live"
    testnet: bool = True
    max_concurrent: int = 5  # Максимум одновременных ботов
    check_interval: int = 30  # Интервал проверки здоровья в секундах
    stop_on_error: bool = False  # Остановить все если один упал


class MultiSymbolBot:
    """
    TASK-004: Главный оркестратор для MultiSymbol торговли
    
    Запускает по одному TradingBot на каждый символ, гарантируя что
    у каждого есть собственные (не шаренные) экземпляры стратегий.
    """
    
    def __init__(self, config: MultiSymbolConfig):
        """
        Args:
            config: Конфигурация
        """
        self.config = config
        self.bots: Dict[str, TradingBot] = {}
        self.threads: Dict[str, threading.Thread] = {}
        self.is_running = False
        self.errors: Dict[str, list] = {symbol: [] for symbol in config.symbols}
        self.stats: Dict[str, dict] = {symbol: {} for symbol in config.symbols}
        
        logger.info(f"MultiSymbolBot initialized for symbols: {config.symbols}")
        logger.info(f"  Mode: {config.mode}, Testnet: {config.testnet}")
        logger.info(f"  Max concurrent: {config.max_concurrent}")
    
    def initialize(self) -> bool:
        """
        Инициализировать все TradingBot инстансы.
        
        ВАЖНОЕ: Для каждого символа создаёт НОВЫЕ экземпляры стратегий!
        
        Returns:
            True если успешно, False если ошибка
        """
        logger.info("=" * 70)
        logger.info("Initializing MultiSymbolBot")
        logger.info("=" * 70)
        
        try:
            for symbol in self.config.symbols:
                logger.info(f"\n[{symbol}] Creating strategies (per-symbol)...")
                
                # TASK-004: Создаём НОВЫЕ экземпляры стратегий для этого символа
                strategies = StrategyFactory.create_strategies()
                strategy_ids = StrategyFactory.get_strategy_ids(strategies)
                logger.info(f"[{symbol}] Strategy instances: {strategy_ids}")
                
                # Создаём TradingBot для этого символа
                logger.info(f"[{symbol}] Creating TradingBot...")
                bot = TradingBot(
                    mode=self.config.mode,
                    strategies=strategies,  # ВАЖНОЕ: new instances!
                    symbol=symbol,
                    testnet=self.config.testnet,
                )
                
                self.bots[symbol] = bot
                logger.info(f"[{symbol}] TradingBot initialized (strategies={len(strategies)})")
            
            logger.info("\n" + "=" * 70)
            logger.info(f"✓ All {len(self.bots)} TradingBot instances initialized")
            logger.info("=" * 70)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize MultiSymbolBot: {e}", exc_info=True)
            return False
    
    def start(self) -> bool:
        """
        Запустить все TradingBot в отдельных потоках.
        
        Returns:
            True если все запустились, False если ошибка
        """
        if not self.bots:
            logger.error("No bots initialized. Call initialize() first")
            return False
        
        if self.is_running:
            logger.warning("MultiSymbolBot is already running")
            return False
        
        logger.info("=" * 70)
        logger.info("Starting MultiSymbolBot threads")
        logger.info("=" * 70)
        
        try:
            # Запускаем потоки с ограничением одновременности
            active_threads = 0
            
            for symbol in self.config.symbols:
                # Ждём если достигли лимита одновременных потоков
                while active_threads >= self.config.max_concurrent:
                    time.sleep(0.1)
                    active_threads = sum(1 for t in self.threads.values() if t.is_alive())
                
                bot = self.bots[symbol]
                
                # Создаём и запускаем поток
                thread = threading.Thread(
                    target=self._run_bot_thread,
                    args=(symbol, bot),
                    name=f"TradingBot-{symbol}",
                    daemon=False,
                )
                
                self.threads[symbol] = thread
                thread.start()
                
                logger.info(f"[{symbol}] Thread started (active: {active_threads + 1}/{self.config.max_concurrent})")
            
            self.is_running = True
            
            # Поток для мониторинга здоровья
            monitor_thread = threading.Thread(
                target=self._monitor_health,
                name="MultiSymbolHealthMonitor",
                daemon=True,
            )
            monitor_thread.start()
            
            logger.info("\n" + "=" * 70)
            logger.info(f"✓ All {len(self.threads)} threads started")
            logger.info("=" * 70)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MultiSymbolBot: {e}", exc_info=True)
            self.is_running = False
            return False
    
    def _run_bot_thread(self, symbol: str, bot: TradingBot):
        """
        Запускает TradingBot в потоке, обрабатывает ошибки.
        """
        logger.info(f"[{symbol}] Bot thread started")
        
        try:
            bot.run()
        except KeyboardInterrupt:
            logger.info(f"[{symbol}] Interrupted by user")
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"[{symbol}] Bot crashed: {error_msg}")
            self.errors[symbol].append({
                "timestamp": datetime.now().isoformat(),
                "error": error_msg,
            })
            
            if self.config.stop_on_error:
                logger.critical(f"[{symbol}] Stopping all bots due to error")
                self.stop()
        finally:
            logger.info(f"[{symbol}] Bot thread finished")
    
    def _monitor_health(self):
        """Поток для мониторинга здоровья ботов"""
        logger.info("Health monitor thread started")
        
        while self.is_running:
            time.sleep(self.config.check_interval)
            
            logger.info("\n" + "=" * 70)
            logger.info("Health Check")
            logger.info("=" * 70)
            
            for symbol in self.config.symbols:
                thread = self.threads.get(symbol)
                bot = self.bots.get(symbol)
                is_alive = thread.is_alive() if thread else False
                
                status = "🟢 ALIVE" if is_alive else "🔴 DEAD"
                errors = len(self.errors[symbol])
                
                logger.info(f"[{symbol}] {status} | Errors: {errors}")
                
                if bot:
                    if hasattr(bot, 'metrics'):
                        logger.debug(f"[{symbol}] Trades: {bot.metrics.total_trades if hasattr(bot, 'metrics') else 'N/A'}")
        
        logger.info("Health monitor thread finished")
    
    def stop(self):
        """Остановить все ботов"""
        if not self.is_running:
            return
        
        logger.info("=" * 70)
        logger.info("Stopping MultiSymbolBot")
        logger.info("=" * 70)
        
        # Останавливаем каждый бот
        for symbol, bot in self.bots.items():
            logger.info(f"[{symbol}] Stopping bot...")
            try:
                bot.stop()
            except Exception as e:
                logger.error(f"[{symbol}] Error stopping bot: {e}")
        
        # Ждём завершения потоков
        for symbol, thread in self.threads.items():
            logger.info(f"[{symbol}] Waiting for thread to finish...")
            thread.join(timeout=30)
            
            if thread.is_alive():
                logger.warning(f"[{symbol}] Thread did not terminate within timeout")
        
        self.is_running = False
        logger.info("\n" + "=" * 70)
        logger.info("MultiSymbolBot stopped")
        logger.info("=" * 70)
    
    def get_report(self) -> Dict[str, Any]:
        """Получить отчет о работе всех ботов"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "is_running": self.is_running,
            "symbols": {},
        }
        
        for symbol in self.config.symbols:
            bot = self.bots.get(symbol)
            errors = self.errors.get(symbol, [])
            
            symbol_report = {
                "is_running": self.threads[symbol].is_alive() if symbol in self.threads else False,
                "error_count": len(errors),
                "errors": errors[-5:] if errors else [],  # Последние 5 ошибок
            }
            
            # Добавляем статистику из бота если доступна
            if bot and hasattr(bot, "metrics"):
                symbol_report["metrics"] = {
                    "total_trades": bot.metrics.total_trades,
                    "winning_trades": bot.metrics.winning_trades,
                    "losing_trades": bot.metrics.losing_trades,
                }
            
            report["symbols"][symbol] = symbol_report
        
        return report


# Convenience function для создания и запуска
def run_multisymbol_bot(symbols: List[str], mode: str = "paper", testnet: bool = True) -> int:
    """
    Создаёт и запускает MultiSymbolBot с указанными символами.
    
    Args:
        symbols: Список символов для торговли (e.g., ["BTCUSDT", "ETHUSDT"])
        mode: "paper" или "live"
        testnet: Использовать testnet
        
    Returns:
        0 если успешно, 1 если ошибка
        
    Example:
        sys.exit(run_multisymbol_bot(
            symbols=["BTCUSDT", "ETHUSDT", "XRPUSDT"],
            mode="paper",
            testnet=True,
        ))
    """
    
    config = MultiSymbolConfig(
        symbols=symbols,
        mode=mode,
        testnet=testnet,
        max_concurrent=len(symbols),  # Все одновременно
    )
    
    bot = MultiSymbolBot(config)
    
    if not bot.initialize():
        logger.error("Failed to initialize MultiSymbolBot")
        return 1
    
    try:
        if not bot.start():
            logger.error("Failed to start MultiSymbolBot")
            return 1
        
        # Держим программу активной
        while bot.is_running:
            time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user")
    
    finally:
        bot.stop()
    
    return 0


if __name__ == "__main__":
    import sys
    
    # Demo: запуск 3 символов
    sys.exit(run_multisymbol_bot(
        symbols=["BTCUSDT", "ETHUSDT", "XRPUSDT"],
        mode="paper",
        testnet=True,
    ))
