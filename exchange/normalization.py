"""
Нормализация price/qty согласно instrument rules.

Центральное место для всех операций округления, использующее
реальные tickSize/qtyStep из InstrumentsManager.

Функции:
- round_price() - округление цены по tickSize
- round_qty() - округление количества по qtyStep
- validate_order() - проверка минималов

Использование:
    from exchange.normalization import round_price, round_qty
    
    price = round_price(instruments_manager, "BTCUSDT", 42123.456)
    qty = round_qty(instruments_manager, "BTCUSDT", 0.123456)
"""

from decimal import Decimal
from typing import Optional
from logger import setup_logger

logger = setup_logger(__name__)


def round_price(
    instruments_manager,
    symbol: str,
    price: float | Decimal,
) -> Decimal:
    """
    Округлить цену согласно tickSize инструмента.
    
    Args:
        instruments_manager: InstrumentsManager instance
        symbol: Торговая пара (BTCUSDT, ETHUSDT и т.д.)
        price: Цена для округления
        
    Returns:
        Округленная цена в виде Decimal
        
    Raises:
        ValueError: Если инструмент не найден или instruments_manager=None
    """
    if instruments_manager is None:
        raise ValueError("InstrumentsManager is None - cannot normalize price")
    
    normalized = instruments_manager.normalize_price(symbol, float(price))
    
    if normalized is None:
        raise ValueError(f"Failed to normalize price for {symbol} - instrument not found")
    
    return normalized


def round_qty(
    instruments_manager,
    symbol: str,
    qty: float | Decimal,
) -> Decimal:
    """
    Округлить количество согласно qtyStep инструмента.
    
    Args:
        instruments_manager: InstrumentsManager instance
        symbol: Торговая пара (BTCUSDT, ETHUSDT и т.д.)
        qty: Количество для округления
        
    Returns:
        Округленное количество в виде Decimal
        
    Raises:
        ValueError: Если инструмент не найден или instruments_manager=None
    """
    if instruments_manager is None:
        raise ValueError("InstrumentsManager is None - cannot normalize qty")
    
    normalized = instruments_manager.normalize_qty(symbol, float(qty))
    
    if normalized is None:
        raise ValueError(f"Failed to normalize qty for {symbol} - instrument not found")
    
    return normalized


def validate_order(
    instruments_manager,
    symbol: str,
    price: float | Decimal,
    qty: float | Decimal,
) -> tuple[bool, str]:
    """
    Проверить ордер согласно требованиям биржи.
    
    Args:
        instruments_manager: InstrumentsManager instance
        symbol: Торговая пара
        price: Цена ордера
        qty: Количество
        
    Returns:
        (is_valid, error_message)
    """
    if instruments_manager is None:
        return False, "InstrumentsManager is None"
    
    return instruments_manager.validate_order(symbol, float(price), float(qty))


def normalize_and_validate(
    instruments_manager,
    symbol: str,
    price: float | Decimal,
    qty: float | Decimal,
) -> tuple[Optional[Decimal], Optional[Decimal], str]:
    """
    Нормализовать и валидировать ордер.
    
    Этап 1: Округление price по tickSize и qty по qtyStep
    Этап 2: Валидация против минималов
    
    Args:
        instruments_manager: InstrumentsManager instance
        symbol: Торговая пара
        price: Цена ордера
        qty: Количество
        
    Returns:
        (normalized_price, normalized_qty, error_message)
        Если error_message не пусто - ордер невалидный
    """
    if instruments_manager is None:
        return None, None, "InstrumentsManager is None"
    
    return instruments_manager.normalize_order(symbol, float(price), float(qty))
