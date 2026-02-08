"""
TASK-004 (P0): MultiSymbol — Стратегии Per-Symbol

Фабрика для создания новых экземпляров стратегий для каждого символа.
Гарантирует что каждый TradingBot имеет собственные объекты стратегий,
а не шарит их с другими ботами для других символов.

Проблема: Если использовать одни экземпляры стратегий для разных символов,
они могут иметь конфликтующее внутреннее состояние (индикаторы, кэши и т.д.)

Решение: Создавать новые экземпляры стратегий для каждого TradingBot.
"""

from typing import List, Type, Callable
from logger import setup_logger

logger = setup_logger(__name__)


class StrategyFactory:
    """Фабрика для создания per-symbol экземпляров стратегий"""
    
    @staticmethod
    def create_strategies(strategy_classes: List[Type] = None) -> List:
        """
        Создаёт новые экземпляры стратегий.
        
        Args:
            strategy_classes: Список классов стратегий (если None, используются defaults)
            
        Returns:
            Список новых экземпляров стратегий
            
        Example:
            # Каждый вызов создает НОВЫЕ экземпляры
            strategies_btc = StrategyFactory.create_strategies()  # id(obj) = 123
            strategies_eth = StrategyFactory.create_strategies()  # id(obj) = 456 (разные!)
        """
        
        if strategy_classes is None:
            # Default стратегии
            from strategy.trend_pullback import TrendPullbackStrategy
            from strategy.breakout import BreakoutStrategy
            from strategy.mean_reversion import MeanReversionStrategy
            strategy_classes = [TrendPullbackStrategy, BreakoutStrategy, MeanReversionStrategy]
        
        strategies = []
        for strategy_class in strategy_classes:
            try:
                instance = strategy_class()
                strategies.append(instance)
                logger.debug(f"✓ Created strategy instance: {strategy_class.__name__} (id={id(instance)})")
            except Exception as e:
                logger.error(f"Failed to instantiate {strategy_class.__name__}: {e}")
                raise
        
        logger.info(f"Created {len(strategies)} strategy instances (all new objects)")
        return strategies
    
    @staticmethod
    def verify_per_symbol_instances(*strategy_lists) -> bool:
        """
        Проверяет что разные наборы стратегий содержат РАЗНЫЕ объекты.
        Используется для тестирования.
        
        Args:
            *strategy_lists: Несколько списков стратегий
            
        Returns:
            True если все объекты уникальны, False если есть дубликаты
            
        Example:
            strategies_1 = StrategyFactory.create_strategies()
            strategies_2 = StrategyFactory.create_strategies()
            assert StrategyFactory.verify_per_symbol_instances(strategies_1, strategies_2)
        """
        
        if not strategy_lists:
            return True
        
        all_ids = []
        for i, strategy_list in enumerate(strategy_lists):
            for strategy in strategy_list:
                obj_id = id(strategy)
                if obj_id in all_ids:
                    logger.error(f"Duplicate object detected in list {i}: {type(strategy).__name__} (id={obj_id})")
                    return False
                all_ids.append(obj_id)
        
        logger.debug(f"✓ All {len(all_ids)} strategy objects are unique")
        return True
    
    @staticmethod
    def get_strategy_ids(strategies: List) -> List[int]:
        """Получить ID объектов стратегий (для debug логирования)"""
        return [id(s) for s in strategies]


# TASK-004: Функция для создания фабрики с кастомными классами
def create_strategy_builder(strategy_classes: List[Type]) -> Callable[[], List]:
    """
    Создает функцию-builder для стратегий.
    Удобно использовать с partial() или в конфигурации.
    
    Args:
        strategy_classes: Список классов стратегий
        
    Returns:
        Функция которая создает новые экземпляры при каждом вызове
        
    Example:
        # В конфигурации:
        strategy_builder = create_strategy_builder([
            TrendPullbackStrategy,
            BreakoutStrategy,
            MeanReversionStrategy,
        ])
        
        # При создании каждого бота:
        strategies = strategy_builder()  # Новые экземпляры
    """
    def builder():
        return StrategyFactory.create_strategies(strategy_classes)
    
    return builder


if __name__ == "__main__":
    # Demo: демонстрируем разные объекты
    print("=" * 70)
    print("TASK-004: Strategy Per-Symbol Demo")
    print("=" * 70)
    
    print("\n[1] Creating strategies for BTCUSDT...")
    strategies_btc = StrategyFactory.create_strategies()
    print(f"    Strategy objects: {StrategyFactory.get_strategy_ids(strategies_btc)}")
    
    print("\n[2] Creating strategies for ETHUSDT...")
    strategies_eth = StrategyFactory.create_strategies()
    print(f"    Strategy objects: {StrategyFactory.get_strategy_ids(strategies_eth)}")
    
    print("\n[3] Verifying they are DIFFERENT objects...")
    if StrategyFactory.verify_per_symbol_instances(strategies_btc, strategies_eth):
        print("    ✓ PASS: Each symbol has unique strategy instances")
    else:
        print("    ✗ FAIL: Strategy instances are shared!")
    
    print("\n" + "=" * 70)
