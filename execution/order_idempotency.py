"""
Order Idempotency: генерация стабильных orderLinkId для предотвращения дублей.

Ключевые фичи:
- Стабильный orderLinkId на основе strategy + symbol + time_bucket + side
- При retry с теми же параметрами генерируется ИДЕНТИЧНЫЙ orderLinkId
- Защита от дублирующих ордеров
"""

from typing import Optional


def generate_order_link_id(
    strategy: str,
    symbol: str,
    timestamp: int,
    side: str,
    bucket_seconds: int = 60,
    max_length: int = 36,
) -> str:
    """
    Генерирует стабильный orderLinkId для идемпотентности ордеров.

    При retry с теми же параметрами в пределах bucket_seconds
    будет сгенерирован ИДЕНТИЧНЫЙ orderLinkId, что предотвращает
    создание дублирующих ордеров.

    Args:
        strategy: ID стратегии (например, "mean_reversion", "momentum")
        symbol: Торговый символ (например, "BTCUSDT")
        timestamp: Unix timestamp в секундах
        side: Сторона сделки ("long", "short", "Buy", "Sell")
        bucket_seconds: Размер временного bucket в секундах (по умолчанию 60 - одна минута)
        max_length: Максимальная длина orderLinkId (Bybit ограничение: 36 символов)

    Returns:
        Стабильный orderLinkId формата: {strategy}_{symbol}_{bucket}_{side}

    Examples:
        >>> generate_order_link_id("mean_rev", "BTCUSDT", 1738915200, "long")
        'mean_rev_BTCUSDT_289819200_long'

        >>> # Retry через 30 секунд - ТОТ ЖЕ orderLinkId!
        >>> generate_order_link_id("mean_rev", "BTCUSDT", 1738915230, "long")
        'mean_rev_BTCUSDT_289819200_long'

        >>> # Но через 61 секунду - ДРУГОЙ bucket, другой orderLinkId
        >>> generate_order_link_id("mean_rev", "BTCUSDT", 1738915261, "long")
        'mean_rev_BTCUSDT_289819201_long'
    """
    # Нормализуем side к короткому формату
    side_normalized = normalize_side(side)

    # Округляем timestamp до bucket
    bucket = timestamp // bucket_seconds

    # Генерируем orderLinkId
    order_link_id = f"{strategy}_{symbol}_{bucket}_{side_normalized}"

    # Проверяем длину (Bybit ограничение: 36 символов)
    if len(order_link_id) > max_length:
        # Укорачиваем strategy если слишком длинный
        max_strategy_len = max_length - len(f"_{symbol}_{bucket}_{side_normalized}")
        if max_strategy_len > 0:
            strategy_short = strategy[:max_strategy_len]
            order_link_id = f"{strategy_short}_{symbol}_{bucket}_{side_normalized}"
        else:
            # Критическая ситуация - symbol слишком длинный
            # Используем хеш
            import hashlib
            hash_suffix = hashlib.md5(order_link_id.encode()).hexdigest()[:8]
            order_link_id = f"{strategy[:8]}_{symbol[:8]}_{bucket}_{side_normalized}_{hash_suffix}"
            order_link_id = order_link_id[:max_length]

    return order_link_id


def normalize_side(side: str) -> str:
    """
    Нормализует сторону сделки к короткому формату.

    Args:
        side: "long", "short", "Buy", "Sell", "buy", "sell"

    Returns:
        Нормализованная сторона: "L" (long/buy) или "S" (short/sell)

    Examples:
        >>> normalize_side("long")
        'L'
        >>> normalize_side("Buy")
        'L'
        >>> normalize_side("short")
        'S'
        >>> normalize_side("Sell")
        'S'
    """
    side_lower = side.lower()
    if side_lower in ("long", "buy"):
        return "L"
    elif side_lower in ("short", "sell"):
        return "S"
    else:
        raise ValueError(f"Unknown side: {side}")


def parse_order_link_id(order_link_id: str) -> Optional[dict]:
    """
    Парсит orderLinkId обратно в компоненты.

    Args:
        order_link_id: orderLinkId формата {strategy}_{symbol}_{bucket}_{side}

    Returns:
        Dict с компонентами или None если формат неправильный

    Examples:
        >>> parse_order_link_id("mean_rev_BTCUSDT_289819200_L")
        {'strategy': 'mean_rev', 'symbol': 'BTCUSDT', 'bucket': 289819200, 'side': 'L'}
    """
    try:
        parts = order_link_id.split("_")
        if len(parts) < 4:
            return None

        # Последняя часть - side
        side = parts[-1]
        # Предпоследняя - bucket
        bucket = int(parts[-2])
        # Вторая часть - symbol (может содержать _)
        symbol = parts[-3]
        # Всё остальное - strategy
        strategy = "_".join(parts[:-3])

        return {
            "strategy": strategy,
            "symbol": symbol,
            "bucket": bucket,
            "side": side,
        }
    except (ValueError, IndexError):
        return None
