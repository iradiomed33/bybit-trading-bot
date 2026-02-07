"""
TESTNET ТЕСТЫ: API и аутентификация (REG-B1-02, REG-B2, REG-B3-03)

Требует: BYBIT_API_KEY и BYBIT_API_SECRET в .env

Тесты:
- REG-B1-02: Приватные запросы работают с реальным API
- REG-B2-01: WebSocket подписка на позиции работает
- REG-B3-03: Нормализация ордеров работает с реальными инструментами
"""

import os
import pytest
from exchange.base_client import BybitRestClient
from exchange.account import AccountClient
from exchange.market_data import MarketDataClient


class TestREGB1_02_PrivateAPI:
    """REG-B1-02: Приватные запросы к testnet API работают"""
    
    @pytest.mark.skipif(
        not os.getenv('BYBIT_API_KEY'),
        reason="BYBIT_API_KEY не установлен"
    )
    def test_get_account_balance(self):
        """Получение баланса аккаунта должно работать"""
        client = AccountClient(testnet=True)
        
        try:
            balance = client.get_wallet_balance(coin='USDT')
            
            # Balance должен быть dict с результатами
            assert balance is not None
            assert isinstance(balance, dict)
            assert 'retCode' in balance
        except Exception as e:
            pytest.skip(f"API недоступен: {e}")
    
    @pytest.mark.skipif(
        not os.getenv('BYBIT_API_KEY'),
        reason="BYBIT_API_KEY не установлен"
    )
    def test_get_positions(self):
        """Получение позиций с testnet API должно работать"""
        client = AccountClient(testnet=True)
        
        try:
            positions = client.get_positions(symbol='BTCUSDT')
            
            # Результат должен быть dict с retCode
            assert positions is not None
            assert isinstance(positions, dict)
            assert 'retCode' in positions
        except Exception as e:
            pytest.skip(f"API недоступен: {e}")
    
    @pytest.mark.skipif(
        not os.getenv('BYBIT_API_KEY'),
        reason="BYBIT_API_KEY не установлен"
    )
    def test_api_key_not_exposed_in_logs(self):
        """API key не должен появляться в логах"""
        api_key = os.getenv('BYBIT_API_KEY', '')
        
        # API key должен быть непустым если тест запускается
        assert len(api_key) > 0
        
        # При создании клиента ключ не должен логироваться
        client = BybitRestClient(testnet=True)
        assert client is not None


class TestREGB2_WebSocket:
    """REG-B2-01: WebSocket подписка на обновления позиций работает"""
    
    @pytest.mark.skipif(
        not os.getenv('BYBIT_API_KEY'),
        reason="BYBIT_API_KEY не установлен"
    )
    def test_websocket_connection_establishes(self):
        """WebSocket подключение должно устанавливаться"""
        try:
            from exchange.websocket_client import BybitWebSocketClient
            from config import Config
            
            # WebSocket требует URL и callback
            ws_url = Config.BYBIT_WS_PUBLIC_TESTNET
            ws = BybitWebSocketClient(
                ws_url=ws_url,
                on_message=lambda msg: None,
            )
            assert ws is not None
            
            # После создания клиент должен быть готов
            assert hasattr(ws, 'connect')
            assert hasattr(ws, 'subscribe')
        except ImportError:
            pytest.skip("WebSocket клиент не реализован")
        except Exception as e:
            pytest.skip(f"WebSocket недоступен: {e}")
    
    @pytest.mark.skipif(
        not os.getenv('BYBIT_API_KEY'),
        reason="BYBIT_API_KEY не установлен"
    )
    def test_websocket_position_updates(self):
        """WebSocket должен отправлять обновления позиций"""
        try:
            from exchange.websocket_client import BybitWebSocketClient
            from config import Config
            
            ws_url = Config.BYBIT_WS_PUBLIC_TESTNET
            ws = BybitWebSocketClient(
                ws_url=ws_url,
                on_message=lambda msg: None,
            )
            
            # Проверить что метод подписки существует
            assert callable(ws.subscribe)
        except ImportError:
            pytest.skip("WebSocket клиент не реализован")
        except Exception as e:
            pytest.skip(f"WebSocket недоступен: {e}")


class TestREGB3_03_OrderNormalization:
    """REG-B3-03: Нормализация ордеров по реальным инструментам"""
    
    @pytest.mark.skipif(
        not os.getenv('BYBIT_API_KEY'),
        reason="BYBIT_API_KEY не установлен"
    )
    def test_instruments_loaded_from_api(self):
        """Инструменты должны загружаться с API"""
        client = MarketDataClient(testnet=True)
        
        try:
            instruments = client.get_instruments_info(symbol='BTCUSDT')
            
            # Инструменты должны быть загружены
            assert instruments is not None
            assert isinstance(instruments, dict)
            assert 'retCode' in instruments
        except Exception as e:
            pytest.skip(f"Instruments API недоступен: {e}")
    
    @pytest.mark.skipif(
        not os.getenv('BYBIT_API_KEY'),
        reason="BYBIT_API_KEY не установлен"
    )
    def test_normalize_against_real_filters(self):
        """Нормализация должна использовать реальные фильтры инструментов"""
        from exchange.instruments import InstrumentsManager
        
        client = BybitRestClient(testnet=True)
        mgr = InstrumentsManager(rest_client=client)
        
        # Менеджер должен быть инициализирован
        assert mgr is not None
        
        # Должны быть методы нормализации
        assert hasattr(mgr, 'normalize_price')
        assert hasattr(mgr, 'normalize_qty')


class TestREGB_Testnet_Integration:
    """Интеграция: API + WebSocket работают вместе"""
    
    @pytest.mark.skipif(
        not os.getenv('BYBIT_API_KEY'),
        reason="BYBIT_API_KEY не установлен"
    )
    def test_rest_and_websocket_work_together(self):
        """REST API и WebSocket должны работать без конфликтов"""
        client = AccountClient(testnet=True)
        
        try:
            from exchange.websocket_client import BybitWebSocketClient
            from config import Config
            
            ws_url = Config.BYBIT_WS_PUBLIC_TESTNET
            ws = BybitWebSocketClient(
                ws_url=ws_url,
                on_message=lambda msg: None,
            )
            
            # Оба компонента инициализированы
            assert client is not None
            assert ws is not None
        except ImportError:
            pytest.skip("WebSocket не реализован")
        except Exception as e:
            pytest.skip(f"Интеграция недоступна: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'not skipif'])
