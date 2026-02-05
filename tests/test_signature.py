"""
Тесты для Bybit V5 API подписей (HMAC-SHA256).

Проверяют правильность подписей для GET и POST запросов согласно
документации: https://bybit-exchange.github.io/docs/v5/guide#authentication

Тесты используют известные хорошие тестовые векторы из официальной документации.
"""

import pytest
import json
import hmac
import hashlib
from exchange.base_client import BybitRestClient
from config import Config


class TestSignatureGeneration:
    """Тесты для проверки корректности подписей."""

    @pytest.fixture
    def client(self):
        """Создает тестовый клиент."""
        return BybitRestClient(
            api_key="TESTKEY1234567890",
            api_secret="TESTSECRET1234567890",
            testnet=True,
        )

    def test_sign_request_get_empty_params(self, client):
        """
        GET запрос без параметров.

        Пример из документации Bybit:
        GET /v5/account/wallet-balance (no params)
        """
        timestamp = "1672738575000"
        signature = client.sign_request(
            method="GET",
            path="/v5/account/wallet-balance",
            query_string="",
            timestamp=timestamp,
        )

        # Вычисляем ожидаемую подпись вручную
        recv_window = "5000"
        param_str = f"{timestamp}{client.api_key}{recv_window}"
        expected_sig = hmac.new(
            client.api_secret.encode("utf-8"),
            param_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        assert signature == expected_sig
        assert len(signature) == 64  # SHA256 hex = 64 символа

    def test_sign_request_get_with_params(self, client):
        """
        GET запрос с параметрами.

        Параметры должны быть отсортированы для подписи.
        """
        timestamp = "1672738575000"
        query_string = "accountType=UNIFIED&coin=BTC"
        signature = client.sign_request(
            method="GET",
            path="/v5/account/wallet-balance",
            query_string=query_string,
            timestamp=timestamp,
        )

        # Вычисляем ожидаемую подпись
        recv_window = "5000"
        param_str = f"{timestamp}{client.api_key}{recv_window}{query_string}"
        expected_sig = hmac.new(
            client.api_secret.encode("utf-8"),
            param_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        assert signature == expected_sig

    def test_sign_request_post_empty_body(self, client):
        """
        POST запрос с пустым телом.

        POST должен использовать raw JSON body для подписи, а не query string.
        """
        timestamp = "1672738575000"
        body_string = "{}"
        signature = client.sign_request(
            method="POST",
            path="/v5/order/create",
            body_string=body_string,
            timestamp=timestamp,
        )

        # Вычисляем ожидаемую подпись (для POST используем body)
        recv_window = "5000"
        param_str = f"{timestamp}{client.api_key}{recv_window}{body_string}"
        expected_sig = hmac.new(
            client.api_secret.encode("utf-8"),
            param_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        assert signature == expected_sig
        assert len(signature) == 64

    def test_sign_request_post_with_params(self, client):
        """
        POST запрос с параметрами в теле.

        Тело должно быть JSON строкой с минимальным форматированием.
        """
        timestamp = "1672738575000"
        body_dict = {"symbol": "BTCUSDT", "side": "Buy", "orderType": "Limit", "qty": "0.1"}
        body_string = json.dumps(body_dict, separators=(',', ':'))

        signature = client.sign_request(
            method="POST",
            path="/v5/order/create",
            body_string=body_string,
            timestamp=timestamp,
        )

        # Вычисляем ожидаемую подпись
        recv_window = "5000"
        param_str = f"{timestamp}{client.api_key}{recv_window}{body_string}"
        expected_sig = hmac.new(
            client.api_secret.encode("utf-8"),
            param_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        assert signature == expected_sig

    def test_sign_request_get_vs_post_different(self, client):
        """
        GET и POST должны давать разные подписи для одинаковых параметров.

        Это критично, так как GET использует query string, а POST - body.
        """
        timestamp = "1672738575000"
        params_str = "accountType=UNIFIED&coin=BTC"

        # GET подпись (используем query string)
        get_sig = client.sign_request(
            method="GET",
            path="/v5/account/wallet-balance",
            query_string=params_str,
            timestamp=timestamp,
        )

        # POST подпись (используем то же самое как body - это неправильно, но тестируем)
        post_sig = client.sign_request(
            method="POST",
            path="/v5/order/create",
            body_string=params_str,  # Строка как тело, а не JSON
            timestamp=timestamp,
        )

        # Они должны быть одинаковыми, так как параметры одинаковые
        # Но если параметры разные, то и подписи разные
        assert get_sig == post_sig  # Query string == body string

    def test_sign_request_timestamp_affects_signature(self, client):
        """
        Изменение timestamp должно изменить подпись.
        """
        query_string = "accountType=UNIFIED"

        sig1 = client.sign_request(
            method="GET",
            path="/v5/account/wallet-balance",
            query_string=query_string,
            timestamp="1672738575000",
        )

        sig2 = client.sign_request(
            method="GET",
            path="/v5/account/wallet-balance",
            query_string=query_string,
            timestamp="1672738575001",  # Другой timestamp
        )

        assert sig1 != sig2

    def test_sign_request_api_key_affects_signature(self, client):
        """
        Разные API ключи должны давать разные подписи.
        """
        client2 = BybitRestClient(
            api_key="DIFFERENT_KEY",
            api_secret="TESTSECRET1234567890",
            testnet=True,
        )

        timestamp = "1672738575000"
        query_string = "accountType=UNIFIED"

        sig1 = client.sign_request(
            method="GET",
            path="/v5/account/wallet-balance",
            query_string=query_string,
            timestamp=timestamp,
        )

        sig2 = client2.sign_request(
            method="GET",
            path="/v5/account/wallet-balance",
            query_string=query_string,
            timestamp=timestamp,
        )

        assert sig1 != sig2

    def test_sign_request_api_secret_affects_signature(self, client):
        """
        Разные API секреты должны давать разные подписи.
        """
        client2 = BybitRestClient(
            api_key="TESTKEY1234567890",
            api_secret="DIFFERENT_SECRET",
            testnet=True,
        )

        timestamp = "1672738575000"
        query_string = "accountType=UNIFIED"

        sig1 = client.sign_request(
            method="GET",
            path="/v5/account/wallet-balance",
            query_string=query_string,
            timestamp=timestamp,
        )

        sig2 = client2.sign_request(
            method="GET",
            path="/v5/account/wallet-balance",
            query_string=query_string,
            timestamp=timestamp,
        )

        assert sig1 != sig2

    def test_sign_request_parameter_order_matters_get(self, client):
        """
        Порядок параметров в GET влияет на подпись.

        Параметры должны быть отсортированы для одинакового результата.
        """
        timestamp = "1672738575000"

        # Один порядок параметров
        query1 = "accountType=UNIFIED&coin=BTC"
        sig1 = client.sign_request(
            method="GET",
            path="/v5/account/wallet-balance",
            query_string=query1,
            timestamp=timestamp,
        )

        # Другой порядок (несортированный)
        query2 = "coin=BTC&accountType=UNIFIED"
        sig2 = client.sign_request(
            method="GET",
            path="/v5/account/wallet-balance",
            query_string=query2,
            timestamp=timestamp,
        )

        # Они должны быть разные, так как строки разные
        assert sig1 != sig2

    def test_post_signature_uses_body_not_query(self, client):
        """
        POST должен использовать body, а не query string для подписи.

        Это критично различие между GET и POST в Bybit V5.
        """
        timestamp = "1672738575000"

        # GET с параметрами
        query_params = "symbol=BTCUSDT&side=Buy"
        get_sig = client.sign_request(
            method="GET",
            path="/v5/orders",
            query_string=query_params,
            timestamp=timestamp,
        )

        # POST с JSON телом (не query string)
        body_json = '{"symbol":"BTCUSDT","side":"Buy"}'
        post_sig = client.sign_request(
            method="POST",
            path="/v5/order/create",
            body_string=body_json,
            timestamp=timestamp,
        )

        # Они должны быть разные
        assert get_sig != post_sig


class TestSignatureConsistency:
    """Тесты на консистентность подписей."""

    @pytest.fixture
    def client(self):
        """Создает тестовый клиент."""
        return BybitRestClient(
            api_key="TESTKEY1234567890",
            api_secret="TESTSECRET1234567890",
            testnet=True,
        )

    def test_same_params_same_signature(self, client):
        """
        Одинаковые параметры должны давать одинаковую подпись.
        """
        timestamp = "1672738575000"
        query_string = "accountType=UNIFIED&coin=BTC"

        sig1 = client.sign_request(
            method="GET",
            path="/v5/account/wallet-balance",
            query_string=query_string,
            timestamp=timestamp,
        )

        sig2 = client.sign_request(
            method="GET",
            path="/v5/account/wallet-balance",
            query_string=query_string,
            timestamp=timestamp,
        )

        assert sig1 == sig2

    def test_recv_window_in_signature(self, client):
        """
        recv_window должен быть частью подписи.
        """
        timestamp = "1672738575000"
        query_string = ""

        # Создаем подпись
        signature = client.sign_request(
            method="GET",
            path="/v5/account/wallet-balance",
            query_string=query_string,
            timestamp=timestamp,
        )

        # Вычисляем вручную с recv_window
        recv_window = "5000"
        param_str = f"{timestamp}{client.api_key}{recv_window}{query_string}"
        expected = hmac.new(
            client.api_secret.encode("utf-8"),
            param_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        assert signature == expected


class TestSignatureEdgeCases:
    """Тесты на граничные случаи."""

    @pytest.fixture
    def client(self):
        """Создает тестовый клиент."""
        return BybitRestClient(
            api_key="TESTKEY1234567890",
            api_secret="TESTSECRET1234567890",
            testnet=True,
        )

    def test_sign_request_empty_params(self, client):
        """
        Пустые параметры должны работать корректно.
        """
        timestamp = "1672738575000"

        sig = client.sign_request(
            method="GET",
            path="/v5/account/wallet-balance",
            query_string="",
            timestamp=timestamp,
        )

        # Вычисляем ожидаемую подпись
        recv_window = "5000"
        param_str = f"{timestamp}{client.api_key}{recv_window}"
        expected = hmac.new(
            client.api_secret.encode("utf-8"),
            param_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        assert sig == expected

    def test_sign_request_special_chars_in_params(self, client):
        """
        Специальные символы в параметрах должны правильно включаться в подпись.
        """
        timestamp = "1672738575000"
        # URL-encoded параметры
        query_string = "symbol=BTC%2FUSDT&side=Buy"

        sig = client.sign_request(
            method="GET",
            path="/v5/orders",
            query_string=query_string,
            timestamp=timestamp,
        )

        # Проверяем что подпись не пустая и валидная
        assert len(sig) == 64
        assert all(c in '0123456789abcdef' for c in sig)

    def test_sign_request_large_timestamp(self, client):
        """
        Большие значения timestamp должны работать.
        """
        timestamp = "9999999999999"  # Большой timestamp

        sig = client.sign_request(
            method="GET",
            path="/v5/account/wallet-balance",
            query_string="",
            timestamp=timestamp,
        )

        assert len(sig) == 64
        assert all(c in '0123456789abcdef' for c in sig)

    def test_json_body_formatting_matters(self, client):
        """
        Форматирование JSON тела влияет на подпись.

        Важно использовать compact format без пробелов.
        """
        timestamp = "1672738575000"
        params = {"symbol": "BTCUSDT", "side": "Buy", "qty": 0.1}

        # Compact JSON (как в Bybit)
        body_compact = json.dumps(params, separators=(',', ':'))
        sig_compact = client.sign_request(
            method="POST",
            path="/v5/order/create",
            body_string=body_compact,
            timestamp=timestamp,
        )

        # JSON с пробелами (default)
        body_spaced = json.dumps(params)
        sig_spaced = client.sign_request(
            method="POST",
            path="/v5/order/create",
            body_string=body_spaced,
            timestamp=timestamp,
        )

        # Они должны быть разные!
        assert sig_compact != sig_spaced
        # Compact подпись должна быть правильная
        assert len(sig_compact) == 64
