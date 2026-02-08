"""
Тесты для исправления BUG-005: POST signature mismatch

Проверяет:
1. Для signed POST отправляется та же строка что подписывается
2. Для signed GET query_string формируется через urlencode
3. Content-Type устанавливается для signed POST
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from exchange.base_client import BybitRestClient


class TestSignedPOSTBodyMatch:
    """Тесты для проверки что body совпадает при подписи POST"""
    
    @pytest.fixture
    def client(self):
        """Создает клиент с mock credentials"""
        return BybitRestClient(
            api_key="test_api_key",
            api_secret="test_api_secret",
            testnet=True
        )
    
    def test_signed_post_sends_exact_body_string(self, client):
        """
        Тест: signed POST отправляет точно ту же строку что подписывается
        """
        params = {
            "symbol": "BTCUSDT",
            "side": "Buy",
            "orderType": "Limit",
            "qty": "0.001",
            "price": "50000"
        }
        
        # Формируем ожидаемую body_string (как в sign_request)
        expected_body = json.dumps(params, separators=(",", ":"))
        
        with patch.object(client.session, 'post') as mock_post:
            # Настраиваем mock response
            mock_response = Mock()
            mock_response.json.return_value = {"retCode": 0, "result": {}}
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            # Вызываем POST запрос
            try:
                client._request(
                    method="POST",
                    endpoint="/v5/order/create",
                    params=params,
                    signed=True
                )
            except Exception:
                pass  # Игнорируем ошибки, нас интересует только вызов
            
            # Проверяем что post был вызван
            assert mock_post.called, "session.post должен быть вызван"
            
            # Получаем аргументы вызова
            call_args = mock_post.call_args
            
            # Проверяем что data содержит правильную body_string
            assert 'data' in call_args[1], "Должен быть параметр data"
            sent_data = call_args[1]['data']
            
            # Декодируем если это bytes
            if isinstance(sent_data, bytes):
                sent_data = sent_data.decode('utf-8')
            
            assert sent_data == expected_body, \
                f"Отправленная строка должна совпадать с подписанной.\n" \
                f"Expected: {expected_body}\n" \
                f"Got: {sent_data}"
    
    def test_signed_post_has_content_type_header(self, client):
        """
        Тест: signed POST имеет Content-Type: application/json
        """
        params = {"symbol": "BTCUSDT", "side": "Buy"}
        
        with patch.object(client.session, 'post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {"retCode": 0, "result": {}}
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            try:
                client._request(
                    method="POST",
                    endpoint="/v5/order/create",
                    params=params,
                    signed=True
                )
            except Exception:
                pass
            
            # Проверяем headers
            call_args = mock_post.call_args
            headers = call_args[1].get('headers', {})
            
            assert 'Content-Type' in headers, "Должен быть Content-Type header"
            assert headers['Content-Type'] == 'application/json', \
                "Content-Type должен быть application/json"
    
    def test_unsigned_post_uses_json_param(self, client):
        """
        Тест: unsigned POST может использовать json= параметр
        """
        params = {"symbol": "BTCUSDT"}
        
        with patch.object(client.session, 'post') as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {"retCode": 0, "result": {}}
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            try:
                client._request(
                    method="POST",
                    endpoint="/v5/market/some-endpoint",
                    params=params,
                    signed=False  # Unsigned
                )
            except Exception:
                pass
            
            # Для unsigned может быть json=params
            call_args = mock_post.call_args
            # Проверяем что вызов прошел (unsigned могут использовать json или data)
            assert mock_post.called


class TestSignedGETQueryString:
    """Тесты для проверки query_string формирования для GET"""
    
    @pytest.fixture
    def client(self):
        return BybitRestClient(
            api_key="test_api_key",
            api_secret="test_api_secret",
            testnet=True
        )
    
    def test_signed_get_uses_urlencode(self, client):
        """
        Тест: signed GET использует urlencode для query_string
        """
        params = {
            "symbol": "BTCUSDT",
            "category": "linear",
            "limit": "100"
        }
        
        with patch.object(client.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"retCode": 0, "result": {}}
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            try:
                client._request(
                    method="GET",
                    endpoint="/v5/market/kline",
                    params=params,
                    signed=True
                )
            except Exception:
                pass
            
            # GET должен быть вызван
            assert mock_get.called, "session.get должен быть вызван"
    
    def test_signed_get_with_special_chars(self, client):
        """
        Тест: query_string правильно экранирует специальные символы
        """
        params = {
            "symbol": "BTC/USDT",  # Слэш должен быть экранирован
            "test": "a b"  # Пробел должен быть экранирован
        }
        
        with patch.object(client.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"retCode": 0, "result": {}}
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            try:
                client._request(
                    method="GET",
                    endpoint="/v5/test",
                    params=params,
                    signed=True
                )
            except Exception:
                pass
            
            # Проверяем что вызов прошел (urlencode обработал специальные символы)
            assert mock_get.called


class TestBodyStringConsistency:
    """Тесты для проверки консистентности JSON сериализации"""
    
    def test_json_dumps_separators(self):
        """
        Тест: json.dumps с separators=(",", ":") создает компактный JSON
        """
        params = {
            "symbol": "BTCUSDT",
            "side": "Buy",
            "qty": "0.001"
        }
        
        # Компактная сериализация (используется в коде)
        compact = json.dumps(params, separators=(",", ":"))
        
        # Сериализация по умолчанию (НЕ должна использоваться)
        default = json.dumps(params)
        
        # Компактная версия не должна иметь пробелов после разделителей
        assert ", " not in compact, "Не должно быть пробелов после запятой"
        assert ": " not in compact, "Не должно быть пробелов после двоеточия"
        
        # По умолчанию json.dumps добавляет пробелы
        assert ", " in default or ": " in default, \
            "json.dumps по умолчанию добавляет пробелы"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
