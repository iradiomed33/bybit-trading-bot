"""

Тесты для приватных API вызовов Bybit V5.


Проверяют корректность работы с приватными эндпоинтами:

- /v5/account/wallet-balance

- /v5/position/list

- /v5/order/create

- /v5/order/cancel


Используют моки для тестирования без реального подключения к API.

"""


import pytest

from unittest.mock import Mock, patch

from exchange.base_client import BybitRestClient

from exchange.account import AccountClient


class TestPrivateAPISignatures:

    """Тесты проверяют корректность подписей для приватных вызовов."""

    @pytest.fixture
    def rest_client(self):
        """Создает тестовый REST клиент."""

        return BybitRestClient(

            api_key="TESTKEY",

            api_secret="TESTSECRET",

            testnet=True,

        )

    @patch("exchange.base_client.BybitRestClient._rate_limit_wait")
    @patch("requests.Session.get")
    def test_get_wallet_balance_signature(self, mock_get, mock_wait, rest_client):
        """

        Проверяет что GET /v5/account/wallet-balance использует правильную подпись.

        """

        # Мокируем ответ

        mock_response = Mock()

        mock_response.json.return_value = {

            "retCode": 0,

            "retMsg": "OK",

            "result": {

                "memberId": "123456",

                "accountType": "UNIFIED",

                "accountLtvValue": "0",

                "totalEquityValue": "10000",

                "totalWalletBalance": "10000",

                "totalMarginBalance": "10000",

                "totalAvailableBalance": "10000",

                "coin": [

                    {

                        "coin": "BTC",

                        "walletBalance": "5",

                        "borrowAmount": "0",

                        "transferBalance": "0",

                        "free": "5",

                        "locked": "0",

                        "equityValue": "5",

                    }

                ],

            },

        }

        mock_get.return_value = mock_response

        # Вызываем метод

        result = rest_client.get("/v5/account/wallet-balance", signed=True)

        # Проверяем результат

        assert result["retCode"] == 0

        assert "result" in result

        # Проверяем что были установлены требуемые headers

        call_kwargs = mock_get.call_args[1]

        headers = call_kwargs.get("headers", {})

        assert "X-BAPI-API-KEY" in headers

        assert "X-BAPI-TIMESTAMP" in headers

        assert "X-BAPI-SIGN" in headers

        assert "X-BAPI-RECV-WINDOW" in headers

        assert "X-BAPI-SIGN-TYPE" in headers

        assert headers["X-BAPI-SIGN-TYPE"] == "2"

        # Проверяем что API ключ правильный

        assert headers["X-BAPI-API-KEY"] == "TESTKEY"

    @patch("exchange.base_client.BybitRestClient._rate_limit_wait")
    @patch("requests.Session.post")
    def test_place_order_signature(self, mock_post, mock_wait, rest_client):
        """

        Проверяет что POST /v5/order/create использует правильную подпись.


        POST должен подписать JSON body, а не query string.

        """

        # Мокируем ответ

        mock_response = Mock()

        mock_response.json.return_value = {

            "retCode": 0,

            "retMsg": "OK",

            "result": {

                "orderId": "1234567890",

                "orderLinkId": "my-order",

                "symbol": "BTCUSDT",

                "side": "Buy",

                "orderType": "Limit",

                "qty": "0.1",

                "price": "30000",

                "status": "New",

                "createTime": "1234567890000",

                "updateTime": "1234567890000",

            },

        }

        mock_post.return_value = mock_response

        # Параметры заказа

        params = {

            "symbol": "BTCUSDT",

            "side": "Buy",

            "orderType": "Limit",

            "qty": "0.1",

            "price": "30000",

        }

        # Вызываем метод

        result = rest_client.post("/v5/order/create", params=params, signed=True)

        # Проверяем результат

        assert result["retCode"] == 0

        assert result["result"]["orderId"] == "1234567890"

        # Проверяем что headers установлены

        call_kwargs = mock_post.call_args[1]

        headers = call_kwargs.get("headers", {})

        assert "X-BAPI-API-KEY" in headers

        assert "X-BAPI-SIGN" in headers

        assert "X-BAPI-SIGN-TYPE" in headers

        assert headers["X-BAPI-SIGN-TYPE"] == "2"

    @patch("exchange.base_client.BybitRestClient._rate_limit_wait")
    @patch("requests.Session.post")
    def test_place_order_json_body_in_request(self, mock_post, mock_wait, rest_client):
        """

        Проверяет что POST /v5/order/create отправляет параметры как JSON body.

        """

        mock_response = Mock()

        mock_response.json.return_value = {"retCode": 0, "retMsg": "OK"}

        mock_post.return_value = mock_response

        params = {

            "symbol": "BTCUSDT",

            "side": "Buy",

            "qty": "0.1",

        }

        rest_client.post("/v5/order/create", params=params, signed=True)

        # Проверяем что json параметр был передан

        call_kwargs = mock_post.call_args[1]

        assert "json" in call_kwargs

        assert call_kwargs["json"] == params


class TestAccountClientPrivateMethods:

    """Тесты для приватных методов AccountClient."""

    @pytest.fixture
    def account_client(self):
        """Создает тестовый AccountClient."""

        rest_client = BybitRestClient(

            api_key="TESTKEY",

            api_secret="TESTSECRET",

            testnet=True,

        )

        return AccountClient(rest_client)

    @patch("exchange.base_client.BybitRestClient._rate_limit_wait")
    @patch("requests.Session.get")
    def test_get_wallet_balance_calls_signed_endpoint(self, mock_get, mock_wait, account_client):
        """

        Проверяет что get_wallet_balance вызывает подписанный эндпоинт.

        """

        mock_response = Mock()

        mock_response.json.return_value = {

            "retCode": 0,

            "retMsg": "OK",

            "result": {

                "memberId": "123456",

                "list": [

                    {

                        "coin": [

                            {

                                "coin": "USDT",

                                "walletBalance": "5.5",

                                "borrowAmount": "0",

                                "free": "5.5",

                                "locked": "0",

                            }

                        ],

                    }

                ],

            },

        }

        mock_get.return_value = mock_response

        result = account_client.get_wallet_balance()

        assert result["retCode"] == 0

        assert result["balance"] == 5.5

        assert result["coin"] == "USDT"

        # Проверяем что был подписанный запрос

        call_kwargs = mock_get.call_args[1]

        headers = call_kwargs.get("headers", {})

        assert "X-BAPI-SIGN" in headers

    @patch("exchange.base_client.BybitRestClient._rate_limit_wait")
    @patch("requests.Session.get")
    def test_get_positions_calls_signed_endpoint(self, mock_get, mock_wait, account_client):
        """

        Проверяет что get_positions вызывает подписанный эндпоинт.

        """

        mock_response = Mock()

        mock_response.json.return_value = {

            "retCode": 0,

            "retMsg": "OK",

            "result": {

                "nextPageCursor": "",

                "list": [

                    {

                        "positionIdx": 0,

                        "riskId": 1,

                        "symbol": "BTCUSDT",

                        "side": "Buy",

                        "size": "0.1",

                        "markPrice": "30000",

                        "positionValue": "3000",

                        "unrealizedPnl": "100",

                    }

                ],

            },

        }

        mock_get.return_value = mock_response

        result = account_client.get_positions(category="linear")

        assert result["retCode"] == 0

        assert len(result["result"]["list"]) > 0

        # Проверяем что был подписанный запрос

        call_kwargs = mock_get.call_args[1]

        headers = call_kwargs.get("headers", {})

        assert "X-BAPI-SIGN" in headers


class TestSignatureErrorHandling:

    """Тесты на обработку ошибок подписи."""

    @pytest.fixture
    def rest_client(self):
        """Создает тестовый REST клиент."""

        return BybitRestClient(

            api_key="TESTKEY",

            api_secret="TESTSECRET",

            testnet=True,

        )

    @patch("exchange.base_client.BybitRestClient._rate_limit_wait")
    @patch("requests.Session.get")
    def test_invalid_signature_error(self, mock_get, mock_wait, rest_client):
        """

        Проверяет обработку ошибки неправильной подписи.

        """

        # Мокируем ошибку подписи

        mock_response = Mock()

        mock_response.json.return_value = {

            "retCode": 10001,

            "retMsg": "Invalid API key",

            "result": {},

        }

        mock_get.return_value = mock_response

        with pytest.raises(Exception) as exc_info:

            rest_client.get("/v5/account/wallet-balance", signed=True)

        # 10001 - это аутентификационная ошибка

        assert "Authentication error" in str(exc_info.value) or "API error 10001" in str(

            exc_info.value

        )

    @patch("exchange.base_client.BybitRestClient._rate_limit_wait")
    @patch("requests.Session.post")
    def test_rate_limit_retry(self, mock_post, mock_wait, rest_client):
        """

        Проверяет retry при rate limit ошибке.

        """

        # Первый вызов - rate limit, второй - успех

        mock_response_limit = Mock()

        mock_response_limit.json.return_value = {

            "retCode": 10006,

            "retMsg": "Rate limit exceeded",

        }

        mock_response_success = Mock()

        mock_response_success.json.return_value = {

            "retCode": 0,

            "retMsg": "OK",

            "result": {"orderId": "123"},

        }

        mock_post.side_effect = [mock_response_limit, mock_response_success]

        params = {"symbol": "BTCUSDT"}

        result = rest_client.post("/v5/order/create", params=params, signed=True)

        assert result["retCode"] == 0


class TestPrivateAPIEndpoints:

    """Интеграционные тесты для приватных эндпоинтов."""

    @pytest.fixture
    def rest_client(self):
        """Создает тестовый REST клиент."""

        return BybitRestClient(

            api_key="TESTKEY",

            api_secret="TESTSECRET",

            testnet=True,

        )

    @patch("exchange.base_client.BybitRestClient._rate_limit_wait")
    @patch("requests.Session.get")
    def test_get_endpoint_uses_query_params(self, mock_get, mock_wait, rest_client):
        """

        Проверяет что GET использует query параметры.

        """

        mock_response = Mock()

        mock_response.json.return_value = {"retCode": 0, "result": {}}

        mock_get.return_value = mock_response

        rest_client.get("/v5/orders", params={"symbol": "BTCUSDT"}, signed=True)

        # Проверяем что params передались как query параметры

        call_kwargs = mock_get.call_args[1]

        assert "params" in call_kwargs

    @patch("exchange.base_client.BybitRestClient._rate_limit_wait")
    @patch("requests.Session.post")
    def test_post_endpoint_uses_json_body(self, mock_post, mock_wait, rest_client):
        """

        Проверяет что POST использует JSON body.

        """

        mock_response = Mock()

        mock_response.json.return_value = {"retCode": 0, "result": {}}

        mock_post.return_value = mock_response

        params = {"symbol": "BTCUSDT", "qty": "0.1"}

        rest_client.post("/v5/order/create", params=params, signed=True)

        # Проверяем что params передались в json параметре

        call_kwargs = mock_post.call_args[1]

        assert "json" in call_kwargs

        assert call_kwargs["json"] == params


class TestSignatureWithTimeSynchronization:

    """Тесты на работу подписи с синхронизацией времени."""

    @pytest.fixture
    def rest_client(self):
        """Создает тестовый REST клиент."""

        return BybitRestClient(

            api_key="TESTKEY",

            api_secret="TESTSECRET",

            testnet=True,

        )

    @patch("exchange.base_client.BybitRestClient._rate_limit_wait")
    @patch("requests.Session.get")
    @patch("exchange.base_client.time.time")
    def test_timestamp_with_offset(self, mock_time, mock_get, mock_wait, rest_client):
        """

        Проверяет что timestamp правильно применяет time offset.

        """

        # Устанавливаем mock для time

        mock_time.return_value = 1672738575  # фиксированное время

        # Устанавливаем time offset (предположим, что сервер на 1000ms впереди)

        rest_client._time_offset = 1000

        mock_response = Mock()

        mock_response.json.return_value = {"retCode": 0, "result": {}}

        mock_get.return_value = mock_response

        rest_client.get("/v5/account/wallet-balance", signed=True)

        # Проверяем что timestamp был применен с offset

        call_kwargs = mock_get.call_args[1]

        headers = call_kwargs.get("headers", {})

        timestamp = int(headers["X-BAPI-TIMESTAMP"])

        # Timestamp должен включать offset

        expected_timestamp = int(1672738575 * 1000) + 1000

        assert timestamp == expected_timestamp
