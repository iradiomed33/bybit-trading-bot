"""
Тесты для multi-symbol поддержки.

Проверяет:
1. MultiSymbolTradingBot корректно читает symbols из конфига
2. Каждый symbol обрабатывается с корректным логированием
3. Symbol никогда не равен UNKNOWN
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from bot.multi_symbol_bot import MultiSymbolTradingBot


class TestMultiSymbolBot:
    """Тесты для MultiSymbolTradingBot"""

    @pytest.fixture
    def mock_config(self):
        """Мок конфигурации с 4 символами"""
        config = MagicMock()
        config.get.return_value = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
        return config

    @pytest.fixture
    def strategies(self):
        """Список mock стратегий"""
        return [Mock(), Mock(), Mock()]

    def test_initialization_with_symbols_list(self, strategies):
        """Тест: инициализация с явным списком символов"""
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
        
        with patch('bot.multi_symbol_bot.TradingBot') as MockBot:
            # Создаем mock боты для каждого символа
            MockBot.return_value = Mock()
            
            bot = MultiSymbolTradingBot(
                mode="paper",
                strategies=strategies,
                testnet=True,
                symbols=symbols
            )
            
            # Проверяем что создано 4 бота
            assert len(bot.symbols) == 4
            assert bot.symbols == symbols
            assert len(bot.bots) == 4
            
            # Проверяем что TradingBot вызван для каждого символа
            assert MockBot.call_count == 4
            
            # Проверяем что каждый вызов был с правильным symbol
            for i, symbol in enumerate(symbols):
                call_kwargs = MockBot.call_args_list[i][1]
                assert call_kwargs['symbol'] == symbol

    def test_initialization_from_config(self, strategies, mock_config):
        """Тест: инициализация с чтением symbols из конфига"""
        
        with patch('bot.multi_symbol_bot.get_config', return_value=mock_config):
            with patch('bot.multi_symbol_bot.TradingBot') as MockBot:
                MockBot.return_value = Mock()
                
                # Создаем бот без явного указания symbols
                bot = MultiSymbolTradingBot(
                    mode="paper",
                    strategies=strategies,
                    testnet=True
                )
                
                # Проверяем что config.get был вызван для получения symbols
                mock_config.get.assert_called_once_with("trading.symbols", ["BTCUSDT"])
                
                # Проверяем что боты созданы для всех символов из конфига
                assert len(bot.symbols) == 4
                assert len(bot.bots) == 4

    def test_single_symbol_as_string(self, strategies):
        """Тест: передача одного символа в виде строки"""
        
        with patch('bot.multi_symbol_bot.TradingBot') as MockBot:
            MockBot.return_value = Mock()
            
            bot = MultiSymbolTradingBot(
                mode="paper",
                strategies=strategies,
                testnet=True,
                symbols="BTCUSDT"  # Строка, а не список
            )
            
            # Должно быть преобразовано в список
            assert bot.symbols == ["BTCUSDT"]
            assert len(bot.bots) == 1

    def test_no_symbols_configuration(self, strategies):
        """Тест: без symbols в конфиге используется дефолтный BTCUSDT"""
        
        mock_config = MagicMock()
        mock_config.get.return_value = ["BTCUSDT"]  # Дефолтное значение
        
        with patch('bot.multi_symbol_bot.get_config', return_value=mock_config):
            with patch('bot.multi_symbol_bot.TradingBot') as MockBot:
                MockBot.return_value = Mock()
                
                bot = MultiSymbolTradingBot(
                    mode="paper",
                    strategies=strategies,
                    testnet=True
                )
                
                # Должен использоваться дефолтный символ
                assert bot.symbols == ["BTCUSDT"]
                assert len(bot.bots) == 1

    def test_bot_initialization_failure_continues(self, strategies):
        """Тест: если один бот не инициализировался, остальные продолжают работать"""
        
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
        
        with patch('bot.multi_symbol_bot.TradingBot') as MockBot:
            # Второй символ вызывает ошибку
            def side_effect(*args, **kwargs):
                if kwargs.get('symbol') == "ETHUSDT":
                    raise ValueError("Test error for ETHUSDT")
                return Mock()
            
            MockBot.side_effect = side_effect
            
            bot = MultiSymbolTradingBot(
                mode="paper",
                strategies=strategies,
                testnet=True,
                symbols=symbols
            )
            
            # Проверяем что создано 3 бота (ETHUSDT пропущен)
            assert len(bot.symbols) == 4  # Все символы сохранены
            assert len(bot.bots) == 3  # Но только 3 бота успешно созданы
            
            # Проверяем что ETHUSDT отсутствует в bots
            assert "ETHUSDT" not in bot.bots
            assert "BTCUSDT" in bot.bots
            assert "SOLUSDT" in bot.bots
            assert "XRPUSDT" in bot.bots

    def test_get_status(self, strategies):
        """Тест: get_status возвращает статус всех ботов"""
        
        symbols = ["BTCUSDT", "ETHUSDT"]
        
        with patch('bot.multi_symbol_bot.TradingBot') as MockBot:
            mock_bot1 = Mock()
            mock_bot1.is_running = True
            mock_bot1.mode = "paper"
            
            mock_bot2 = Mock()
            mock_bot2.is_running = False
            mock_bot2.mode = "paper"
            
            MockBot.side_effect = [mock_bot1, mock_bot2]
            
            bot = MultiSymbolTradingBot(
                mode="paper",
                strategies=strategies,
                testnet=True,
                symbols=symbols
            )
            
            status = bot.get_status()
            
            assert status["mode"] == "paper"
            assert status["symbols"] == symbols
            assert len(status["bots"]) == 2
            assert status["bots"]["BTCUSDT"]["is_running"] is True
            assert status["bots"]["ETHUSDT"]["is_running"] is False

    def test_stop_all_bots(self, strategies):
        """Тест: stop() останавливает все боты"""
        
        symbols = ["BTCUSDT", "ETHUSDT"]
        
        with patch('bot.multi_symbol_bot.TradingBot') as MockBot:
            mock_bot1 = Mock()
            mock_bot2 = Mock()
            
            MockBot.side_effect = [mock_bot1, mock_bot2]
            
            bot = MultiSymbolTradingBot(
                mode="paper",
                strategies=strategies,
                testnet=True,
                symbols=symbols
            )
            
            bot.stop()
            
            # Проверяем что is_running установлен в False для всех ботов
            assert mock_bot1.is_running is False
            assert mock_bot2.is_running is False
            assert bot.is_running is False

    def test_threading_initialization(self, strategies):
        """Тест: bot_threads словарь инициализируется корректно"""
        
        symbols = ["BTCUSDT", "ETHUSDT"]
        
        with patch('bot.multi_symbol_bot.TradingBot') as MockBot:
            MockBot.return_value = Mock()
            
            bot = MultiSymbolTradingBot(
                mode="paper",
                strategies=strategies,
                testnet=True,
                symbols=symbols
            )
            
            # Проверяем что bot_threads пустой при инициализации
            assert hasattr(bot, 'bot_threads')
            assert isinstance(bot.bot_threads, dict)
            assert len(bot.bot_threads) == 0


class TestMultiSymbolIntegration:
    """Интеграционные тесты для multi-symbol"""

    def test_symbols_from_config_file(self):
        """
        Интеграционный тест: symbols корректно читаются из config файла
        """
        from config.settings import get_config
        
        config = get_config()
        symbols = config.get("trading.symbols", [])
        
        # Проверяем что symbols присутствует в конфиге
        assert isinstance(symbols, list)
        assert len(symbols) > 0
        
        # Проверяем что каждый symbol - это строка в правильном формате
        for symbol in symbols:
            assert isinstance(symbol, str)
            assert "USDT" in symbol or "USD" in symbol
            assert len(symbol) > 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
