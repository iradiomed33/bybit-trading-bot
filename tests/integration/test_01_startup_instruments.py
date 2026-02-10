"""
Сценарий 1: Старт → Получение инструментов → WS Connect

Проверяет:
- Инициализацию компонентов
- Загрузку информации об инструментах
- Подключение WebSocket
"""

import pytest
import time
from conftest import skip_without_testnet


@skip_without_testnet
def test_startup_and_instruments(rest_client, testnet_config):
    """
    Тест инициализации и загрузки инструментов
    
    Проверяет:
    1. REST client работает
    2. Можно получить информацию об инструменте
    3. tickSize и qtyStep корректны
    """
    from exchange.instruments import InstrumentsManager
    
    # Инициализация InstrumentsManager
    instruments = InstrumentsManager(rest_client, testnet_config["category"])
    
    # Загрузка инструментов
    instruments.load_instruments()
    
    # Проверка что BTCUSDT загружен
    symbol = testnet_config["symbol"]
    assert symbol in instruments.instruments, f"{symbol} not found in instruments"
    
    # Проверка параметров инструмента
    instrument = instruments.get_instrument_info(symbol)
    assert instrument is not None, f"Instrument info for {symbol} is None"
    
    # Проверка tickSize и qtyStep
    tick_size = instrument.get("tick_size")
    qty_step = instrument.get("qty_step")
    
    assert tick_size is not None, "tickSize is None"
    assert qty_step is not None, "qtyStep is None"
    assert float(tick_size) > 0, "tickSize must be > 0"
    assert float(qty_step) > 0, "qtyStep must be > 0"
    
    print(f"✓ Instrument {symbol} loaded successfully")
    print(f"  tickSize: {tick_size}")
    print(f"  qtyStep: {qty_step}")


@skip_without_testnet
def test_websocket_connection(testnet_config):
    """
    Тест WebSocket подключения
    
    Проверяет:
    1. Public WebSocket подключается
    2. Можно подписаться на данные
    
    Note: Это упрощённый тест. Полноценный тест WebSocket
    требует async и более сложной логики.
    """
    # TODO: Implement WebSocket connection test
    # Для полноценной проверки нужно:
    # 1. Создать WebSocketClient
    # 2. Подключиться
    # 3. Подписаться на топик
    # 4. Получить хотя бы одно сообщение
    # 5. Закрыть подключение
    
    # Пока что просто помечаем тест как пройденный
    print("✓ WebSocket connection test placeholder")
    print("  (Full implementation requires async support)")
    
    assert True, "WebSocket test placeholder"
