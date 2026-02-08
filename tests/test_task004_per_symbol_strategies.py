"""
TASK-004 Tests: MultiSymbol Per-Symbol Strategy Isolation

Проверяет что каждый символ получает СВОИ (не шаренные) экземпляры стратегий.

Это критично потому что:
- Стратегии содержат состояние (EMA, ADX, последний сигнал и т.д.)
- Если шарить экземпляры между символами → состояние смешивается
- Запуск 3 стратегий на BTCUSDT и ETHUSDT одновременно
  не должен приводить к конфликту состояния между ними
"""

import pytest
import threading
import time
from typing import List, Dict, Set
from unittest.mock import patch, MagicMock

from bot.strategy_factory import StrategyFactory
from bot.multi_symbol_bot import MultiSymbolBot, MultiSymbolConfig


class TestStrategyFactory:
    """Тесты фабрики стратегий"""
    
    def test_create_strategies_returns_new_instances(self):
        """Каждый вызов create_strategies() возвращает НОВЫЕ объекты"""
        strats1 = StrategyFactory.create_strategies()
        strats2 = StrategyFactory.create_strategies()
        
        # Должны быть разные объекты
        assert len(strats1) == len(strats2)
        
        for s1, s2 in zip(strats1, strats2):
            assert id(s1) != id(s2), "Стратегии должны быть разными объектами"
    
    def test_create_strategies_multiple_calls_unique(self):
        """10 вызовов create_strategies() генерят 10 разных наборов"""
        all_ids: Set[int] = set()
        
        for call_num in range(10):
            strategies = StrategyFactory.create_strategies()
            
            for strategy in strategies:
                obj_id = id(strategy)
                assert obj_id not in all_ids, f"Дублирующийся объект на итерации {call_num}"
                all_ids.add(obj_id)
        
        # Всего должно быть 10 * 3 = 30 уникальных объектов
        assert len(all_ids) == 30
    
    def test_verify_per_symbol_instances_detects_duplicates(self):
        """verify_per_symbol_instances() детектирует шаренные объекты"""
        strats1 = StrategyFactory.create_strategies()
        strats2 = StrategyFactory.create_strategies()
        
        # Разные наборы - должны быть уникальны
        assert StrategyFactory.verify_per_symbol_instances(strats1, strats2) is True
        
        # Если передать одно и то же дважды - детектирует дублирование
        assert StrategyFactory.verify_per_symbol_instances(strats1, strats1) is False
    
    def test_verify_3_symbol_isolation(self):
        """3 символа каждый получают unique стратегии"""
        btc_strats = StrategyFactory.create_strategies()
        eth_strats = StrategyFactory.create_strategies()
        xrp_strats = StrategyFactory.create_strategies()
        
        # Все 3 набора должны быть изолированы друг от друга
        assert StrategyFactory.verify_per_symbol_instances(
            btc_strats, eth_strats, xrp_strats
        ) is True
        
        # Проверяем что они действительно разные объекты
        btc_ids = StrategyFactory.get_strategy_ids(btc_strats)
        eth_ids = StrategyFactory.get_strategy_ids(eth_strats)
        xrp_ids = StrategyFactory.get_strategy_ids(xrp_strats)
        
        # Пересечений быть не должно
        assert len(set(btc_ids) & set(eth_ids)) == 0
        assert len(set(eth_ids) & set(xrp_ids)) == 0
        assert len(set(btc_ids) & set(xrp_ids)) == 0
    
    def test_get_strategy_ids_returns_object_ids(self):
        """get_strategy_ids() возвращает id() объектов"""
        strategies = StrategyFactory.create_strategies()
        ids = StrategyFactory.get_strategy_ids(strategies)
        
        assert len(ids) == len(strategies)
        
        for strategy, obj_id in zip(strategies, ids):
            assert obj_id == id(strategy)


class TestMultiSymbolBotInit:
    """Тесты инициализации MultiSymbolBot"""
    
    @patch("bot.multi_symbol_bot.TradingBot")
    def test_initialize_creates_per_symbol_strategies(self, mock_trading_bot):
        """initialize() создаёт НОВЫЕ стратегии для каждого символа"""
        
        config = MultiSymbolConfig(
            symbols=["BTCUSDT", "ETHUSDT"],
            mode="paper",
            testnet=True,
        )
        bot = MultiSymbolBot(config)
        
        # Захватываем какие стратегии передаются каждому TradingBot
        passed_strategies = {}
        
        def capture_init(mode, strategies, symbol, testnet):
            passed_strategies[symbol] = strategies
            return MagicMock()
        
        mock_trading_bot.side_effect = capture_init
        
        bot.initialize()
        
        # Должны быть стратегии для обоих символов
        assert "BTCUSDT" in passed_strategies
        assert "ETHUSDT" in passed_strategies
        
        # Стратегии должны быть разными объектами
        btc_strategies = passed_strategies["BTCUSDT"]
        eth_strategies = passed_strategies["ETHUSDT"]
        
        assert StrategyFactory.verify_per_symbol_instances(
            btc_strategies, eth_strategies
        ) is True, "Стратегии BTCUSDT и ETHUSDT должны быть разными объектами"
    
    @patch("bot.multi_symbol_bot.TradingBot")
    def test_initialize_3_symbols_isolation(self, mock_trading_bot):
        """initialize() на 3+ символов → все полностью изолированы"""
        
        config = MultiSymbolConfig(
            symbols=["BTCUSDT", "ETHUSDT", "XRPUSDT"],
            mode="paper",
            testnet=True,
        )
        bot = MultiSymbolBot(config)
        
        passed_strategies = {}
        
        def capture_init(mode, strategies, symbol, testnet):
            passed_strategies[symbol] = strategies
            return MagicMock()
        
        mock_trading_bot.side_effect = capture_init
        bot.initialize()
        
        # Все 3 набора должны быть изолированы
        all_strategies = [
            passed_strategies["BTCUSDT"],
            passed_strategies["ETHUSDT"],
            passed_strategies["XRPUSDT"],
        ]
        
        assert StrategyFactory.verify_per_symbol_instances(*all_strategies) is True
    
    @patch("bot.multi_symbol_bot.TradingBot")
    def test_initialize_passes_correct_symbol(self, mock_trading_bot):
        """initialize() передаёт правильный symbol каждому TradingBot"""
        
        config = MultiSymbolConfig(
            symbols=["BTCUSDT", "ETHUSDT"],
            mode="live",
            testnet=False,
        )
        bot = MultiSymbolBot(config)
        
        call_args_list = []
        
        def capture_init(mode, strategies, symbol, testnet):
            call_args_list.append({
                "mode": mode,
                "symbol": symbol,
                "testnet": testnet,
                "strategies_count": len(strategies),
            })
            return MagicMock()
        
        mock_trading_bot.side_effect = capture_init
        bot.initialize()
        
        # Проверяем что были вызваны с правильными параметрами
        assert len(call_args_list) == 2
        
        # Первый бот
        assert call_args_list[0]["symbol"] == "BTCUSDT"
        assert call_args_list[0]["mode"] == "live"
        assert call_args_list[0]["testnet"] is False
        
        # Второй бот
        assert call_args_list[1]["symbol"] == "ETHUSDT"
        assert call_args_list[1]["mode"] == "live"
        assert call_args_list[1]["testnet"] is False


class TestMultiSymbolConcurrentAccess:
    """Тесты конкурентного доступа к per-symbol стратегиям"""
    
    def test_concurrent_strategy_creation_no_conflicts(self):
        """Конкурентное создание стратегий из разных потоков уникально"""
        
        all_strategies = {}
        lock = threading.Lock()
        errors = []
        
        def create_strategies_for_symbol(symbol: str):
            try:
                strategies = StrategyFactory.create_strategies()
                with lock:
                    all_strategies[symbol] = strategies
            except Exception as e:
                errors.append(f"{symbol}: {e}")
        
        threads = []
        for symbol in ["BTCUSDT", "ETHUSDT", "XRPUSDT", "ADAUSDT"]:
            t = threading.Thread(target=create_strategies_for_symbol, args=(symbol,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Ошибки при создании: {errors}"
        assert len(all_strategies) == 4
        
        # Все стратегии должны быть уникальны
        strategy_lists = list(all_strategies.values())
        assert StrategyFactory.verify_per_symbol_instances(*strategy_lists) is True
    
    def test_10x_concurrent_creation_10000_objects_unique(self):
        """Даже при 10x параллельных потоках все 300 объектов уникальны"""
        
        all_ids: Set[int] = set()
        lock = threading.Lock()
        errors = []
        
        def create_batch():
            try:
                for i in range(10):
                    strategies = StrategyFactory.create_strategies()
                    for strategy in strategies:
                        obj_id = id(strategy)
                        with lock:
                            if obj_id in all_ids:
                                errors.append(f"Дублирующийся id: {obj_id}")
                            all_ids.add(obj_id)
            except Exception as e:
                errors.append(str(e))
        
        # 10 потоков × 10 итераций × 3 стратегии = 300 уникальных объектов
        threads = [threading.Thread(target=create_batch) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Ошибки: {errors}"
        assert len(all_ids) == 300, f"Ожидалась 300 уникальных объектов, получено {len(all_ids)}"


class TestMultiSymbolBotIntegration:
    """Интеграционные тесты MultiSymbolBot с per-symbol стратегиями"""
    
    @patch("bot.multi_symbol_bot.TradingBot")
    @patch("bot.multi_symbol_bot.StrategyFactory")
    def test_bot_instantiation_flow(self, mock_factory, mock_trading_bot):
        """Полный flow: инициализация и запуск"""
        
        # Настраиваем mock фабрики
        mock_strategy_obj_1 = MagicMock(name="Strategy1")
        mock_strategy_obj_2 = MagicMock(name="Strategy2")
        mock_strategy_obj_3 = MagicMock(name="Strategy3")
        
        # Разные объекты для разных вызовов
        mock_factory.create_strategies.side_effect = [
            [mock_strategy_obj_1, mock_strategy_obj_2, mock_strategy_obj_3],
            [MagicMock(), MagicMock(), MagicMock()],  # Другие объекты
        ]
        
        mock_factory.get_strategy_ids.return_value = [1, 2, 3]
        
        config = MultiSymbolConfig(
            symbols=["BTCUSDT", "ETHUSDT"],
            mode="paper",
        )
        bot = MultiSymbolBot(config)
        
        success = bot.initialize()
        
        assert success is True
        assert len(bot.bots) == 2
        
        # Фабрика должна быть вызвана дважды (для 2 символов)
        assert mock_factory.create_strategies.call_count == 2


class TestPerSymbolStateIsolation:
    """Тесты изоляции состояния per-symbol"""
    
    def test_strategy_objects_independent(self):
        """Объекты из разных create_strategies() вызовов независимы"""
        
        strats1 = StrategyFactory.create_strategies()
        strats2 = StrategyFactory.create_strategies()
        
        # Если есть какой-то mutable state, они не должны конфликтовать
        if hasattr(strats1[0], "_state"):
            strats1[0]._state = {"test": 1}
            # strats2[0] не должен быть затронут
            assert not hasattr(strats2[0], "_state") or strats2[0]._state != {"test": 1}
    
    def test_concurrent_modification_no_conflicts(self):
        """Конкурентное изменение состояния strats1 и strats2 без конфликтов"""
        
        strats1 = StrategyFactory.create_strategies()
        strats2 = StrategyFactory.create_strategies()
        
        errors = []
        
        def modify_strategies(strats, identifier):
            try:
                for i, strat in enumerate(strats):
                    # Добавляем какой-то атрибут
                    strat._test_id = identifier
                    strat._counter = 0
                
                # "Используем" стратегии
                for _ in range(100):
                    for strat in strats:
                        strat._counter += 1
            except Exception as e:
                errors.append(f"{identifier}: {e}")
        
        t1 = threading.Thread(target=modify_strategies, args=(strats1, "STRATS1"))
        t2 = threading.Thread(target=modify_strategies, args=(strats2, "STRATS2"))
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        assert len(errors) == 0, f"Ошибки при изменении: {errors}"
        
        # Проверяем что состояния не смешались
        for strat in strats1:
            assert strat._test_id == "STRATS1"
            assert strat._counter == 100
        
        for strat in strats2:
            assert strat._test_id == "STRATS2"
            assert strat._counter == 100


class TestMultiSymbolReport:
    """Тесты отчётности MultiSymbolBot"""
    
    @patch("bot.multi_symbol_bot.TradingBot")
    def test_get_report_structure(self, mock_trading_bot):
        """get_report() возвращает правильную структуру"""
        
        mock_trading_bot.return_value = MagicMock()
        
        config = MultiSymbolConfig(symbols=["BTCUSDT", "ETHUSDT"])
        bot = MultiSymbolBot(config)
        bot.initialize()
        
        report = bot.get_report()
        
        assert "timestamp" in report
        assert "is_running" in report
        assert "symbols" in report
        assert "BTCUSDT" in report["symbols"]
        assert "ETHUSDT" in report["symbols"]
        
        for symbol_data in report["symbols"].values():
            assert "is_running" in symbol_data
            assert "error_count" in symbol_data
            assert "errors" in symbol_data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
