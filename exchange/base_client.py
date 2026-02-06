"""

Базовый REST клиент для Bybit API V5.

Обеспечивает подпись запросов, обработку ошибок и rate-limit.


Документация:

- Authentication: https://bybit-exchange.github.io/docs/v5/guide#authentication

- Rate Limits: https://bybit-exchange.github.io/docs/v5/rate-limit

"""


import time

import hmac

import hashlib

import requests

import json

from typing import Optional, Dict, Any

from logger import setup_logger

from config import Config


logger = setup_logger(__name__)


class BybitRestClient:

    """

    Базовый REST клиент для Bybit API V5.

    Поддерживает публичные и приватные эндпоинты.

    """

    def __init__(self, api_key: str = "", api_secret: str = "", testnet: bool = True):
        """

        Args:

            api_key: API ключ (для приватных эндпоинтов)

            api_secret: API secret (для приватных эндпоинтов)

            testnet: Использовать testnet (True) или mainnet (False)

        """

        self.api_key = api_key or Config.BYBIT_API_KEY

        self.api_secret = api_secret or Config.BYBIT_API_SECRET

        self.base_url = Config.BYBIT_REST_TESTNET if testnet else Config.BYBIT_REST_MAINNET

        self.session = requests.Session()

        self.session.headers.update({"Content-Type": "application/json"})

        # Rate limit tracking (упрощённый)

        self._last_request_time = 0

        self._min_request_interval = 0.1  # 100ms между запросами

        # Смещение времени для синхронизации с сервером

        self._time_offset = 0

        self._sync_server_time()

        logger.info(f"BybitRestClient initialized: {self.base_url}")

    def sign_request(

        self,

        method: str,

        path: str,

        query_string: str = "",

        body_string: str = "",

        timestamp: str = "",

    ) -> str:
        """

        Подпись запроса согласно Bybit V5 authentication spec.


        Bybit V5 требует разные форматы подписи для GET и POST:

        - GET: Подпись создается из sorted query params

        - POST/PUT/DELETE: Подпись создается из raw JSON body string


        Args:

            method: HTTP метод (GET, POST, PUT, DELETE)

            path: API путь, например "/v5/account/wallet-balance"

            query_string: Для GET - sorted query params как "k1=v1&k2=v2"

            body_string: Для POST - raw JSON body как '{"k1":"v1","k2":"v2"}'

            timestamp: Unix timestamp в миллисекундах (используется из _sync_server_time)


        Returns:

            Hex-закодированная HMAC-SHA256 подпись


        Example (GET):

            query = "accountType=UNIFIED&coin=BTC"

            sig = sign_request("GET", "/v5/account/wallet-balance", query_string=query, ...)


        Example (POST):

            body = '{"symbol":"BTCUSDT","side":"Buy"}'

            sig = sign_request("POST", "/v5/order/create", body_string=body, ...)


        Docs: https://bybit-exchange.github.io/docs/v5/guide#authentication

        """

        recv_window = "5000"

        # Выбираем параметры для подписи в зависимости от метода

        if method.upper() == "GET":

            # GET: подпись из sorted query params

            param_str = f"{timestamp}{self.api_key}{recv_window}{query_string}"

        else:

            # POST/PUT/DELETE: подпись из raw JSON body

            param_str = f"{timestamp}{self.api_key}{recv_window}{body_string}"

        # Создаем HMAC-SHA256 подпись

        signature = hmac.new(

            self.api_secret.encode("utf-8"),

            param_str.encode("utf-8"),

            hashlib.sha256,

        ).hexdigest()

        return signature

    def _rate_limit_wait(self):
        """Простая защита от rate-limit: ждём минимальный интервал между запросами"""

        elapsed = time.time() - self._last_request_time

        if elapsed < self._min_request_interval:

            time.sleep(self._min_request_interval - elapsed)

        self._last_request_time = time.time()

    def _sync_server_time(self):
        """Синхронизация времени с сервером Bybit для правильной подписи"""

        try:

            response = self.session.get(f"{self.base_url}/v5/market/time")

            response.raise_for_status()

            data = response.json()

            if data.get("retCode") == 0:

                server_time = int(data.get("result", {}).get("timeNano", 0)) // 1_000_000

                client_time = int(time.time() * 1000)

                self._time_offset = server_time - client_time

                logger.debug(f"Server time sync: offset={self._time_offset}ms")

            else:

                logger.warning("Failed to sync server time")

        except Exception as e:

            logger.warning(f"Failed to sync server time: {e}")

    def _request(

        self,

        method: str,

        endpoint: str,

        params: Optional[Dict[str, Any]] = None,

        signed: bool = False,

        retry_count: int = 3,

    ) -> Dict[str, Any]:
        """

        Выполняет HTTP запрос к Bybit API.


        Args:

            method: HTTP метод (GET, POST)

            endpoint: API endpoint (например /v5/market/kline)

            params: Параметры запроса

            signed: Требуется ли подпись (приватные эндпоинты)

            retry_count: Количество повторов при ошибке


        Returns:

            JSON ответ от API


        Raises:

            Exception: При критической ошибке после всех повторов

        """

        params = params or {}

        url = f"{self.base_url}{endpoint}"

        headers = {}

        # Если требуется подпись (приватные эндпоинты)

        if signed:

            # Используем синхронизированное время с сервером

            timestamp = str(int(time.time() * 1000) + self._time_offset)

            recv_window = "5000"

            # Для GET и POST используем разные форматы подписи

            if method.upper() == "GET":

                # GET: сортируем параметры в URL-encoded строку

                query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))

                signature = self.sign_request(

                    method=method,

                    path=endpoint,

                    query_string=query_string,

                    timestamp=timestamp,

                )

            else:

                # POST/PUT/DELETE: используем raw JSON body для подписи

                body_string = json.dumps(params, separators=(",", ":"))

                signature = self.sign_request(

                    method=method,

                    path=endpoint,

                    body_string=body_string,

                    timestamp=timestamp,

                )

            headers.update(

                {

                    "X-BAPI-API-KEY": self.api_key,

                    "X-BAPI-TIMESTAMP": timestamp,

                    "X-BAPI-SIGN": signature,

                    "X-BAPI-RECV-WINDOW": recv_window,

                }

            )

        # Retry логика

        for attempt in range(retry_count):

            try:

                self._rate_limit_wait()

                if method.upper() == "GET":

                    response = self.session.get(url, params=params, headers=headers)

                elif method.upper() == "POST":

                    response = self.session.post(url, json=params, headers=headers)

                else:

                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()

                data = response.json()

                # Проверяем retCode (стандарт Bybit V5)

                ret_code = data.get("retCode", -1)

                ret_msg = data.get("retMsg", "Unknown error")

                if ret_code != 0:

                    logger.error(

                        f"API error: retCode={ret_code}, retMsg={ret_msg}, endpoint={endpoint}, params={params}"

                    )

                    # Некоторые ошибки не стоит повторять

                    if ret_code in [10001, 10003, 10004]:  # Auth errors

                        raise Exception(f"Authentication error: {ret_msg}")

                    if ret_code == 10006:  # Rate limit

                        logger.warning("Rate limit hit, waiting...")

                        time.sleep(2**attempt)  # Exponential backoff

                        continue

                    raise Exception(f"API error {ret_code}: {ret_msg}")

                logger.debug(f"Request success: {method} {endpoint} (attempt {attempt + 1})")

                return data

            except requests.exceptions.RequestException as e:

                logger.warning(f"Request failed (attempt {attempt + 1}/{retry_count}): {e}")

                if attempt == retry_count - 1:

                    raise Exception(f"Request failed after {retry_count} attempts: {e}")

                time.sleep(2**attempt)  # Exponential backoff

        raise Exception("Request failed: max retries exceeded")

    def get(

        self, endpoint: str, params: Optional[Dict[str, Any]] = None, signed: bool = False

    ) -> Dict[str, Any]:
        """GET запрос"""

        return self._request("GET", endpoint, params, signed)

    def post(

        self, endpoint: str, params: Optional[Dict[str, Any]] = None, signed: bool = True

    ) -> Dict[str, Any]:
        """POST запрос"""

        return self._request("POST", endpoint, params, signed)
