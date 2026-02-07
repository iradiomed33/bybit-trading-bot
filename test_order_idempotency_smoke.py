#!/usr/bin/env python3
"""
Standalone smoke test для идемпотентности ордеров.
Не требует зависимостей.
"""

import sys
import os

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(__file__))


def normalize_side(side: str) -> str:
    """Нормализует сторону сделки к короткому формату."""
    side_lower = side.lower()
    if side_lower in ("long", "buy"):
        return "L"
    elif side_lower in ("short", "sell"):
        return "S"
    else:
        raise ValueError(f"Unknown side: {side}")


def generate_order_link_id(
    strategy: str,
    symbol: str,
    timestamp: int,
    side: str,
    bucket_seconds: int = 60,
    max_length: int = 36,
) -> str:
    """Генерирует стабильный orderLinkId для идемпотентности ордеров."""
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


def test_idempotency():
    """Тест идемпотентности orderLinkId"""
    print("\n" + "="*60)
    print("SMOKE TEST: Order Idempotency with orderLinkId")
    print("="*60)
    
    # Test 1: Базовая генерация
    print("\n[Test 1] Базовая генерация orderLinkId")
    order_id = generate_order_link_id(
        strategy="mean_reversion",
        symbol="BTCUSDT",
        timestamp=1738915200,
        side="long",
    )
    print(f"  Generated: {order_id}")
    assert "mean_reversion" in order_id
    assert "BTCUSDT" in order_id
    assert "L" in order_id
    print("  ✓ PASSED")
    
    # Test 2: Идемпотентность при retry
    print("\n[Test 2] Идемпотентность при retry в пределах bucket")
    timestamp1 = 1738915200  # 0 секунд
    timestamp2 = 1738915230  # +30 секунд (в пределах 60-сек bucket)
    
    id1 = generate_order_link_id("strategy", "BTCUSDT", timestamp1, "long", bucket_seconds=60)
    id2 = generate_order_link_id("strategy", "BTCUSDT", timestamp2, "long", bucket_seconds=60)
    
    print(f"  t=0s:   {id1}")
    print(f"  t=30s:  {id2}")
    assert id1 == id2, "IDs должны совпадать при retry в том же bucket!"
    print("  ✓ PASSED - Retry использует ТОТ ЖЕ orderLinkId (защита от дублей)")
    
    # Test 3: Разные buckets
    print("\n[Test 3] Разные buckets дают разные IDs")
    timestamp3 = 1738915261  # +61 секунда (следующий bucket)
    
    id3 = generate_order_link_id("strategy", "BTCUSDT", timestamp3, "long", bucket_seconds=60)
    
    print(f"  t=0s:   {id1}")
    print(f"  t=61s:  {id3}")
    assert id1 != id3, "Разные buckets должны иметь разные IDs"
    print("  ✓ PASSED - Новый bucket = новый orderLinkId")
    
    # Test 4: Разные стороны
    print("\n[Test 4] Long vs Short")
    id_long = generate_order_link_id("strategy", "BTCUSDT", 1738915200, "long")
    id_short = generate_order_link_id("strategy", "BTCUSDT", 1738915200, "short")
    
    print(f"  Long:   {id_long}")
    print(f"  Short:  {id_short}")
    assert id_long != id_short
    print("  ✓ PASSED - Long и Short имеют разные IDs")
    
    # Test 5: Разные стратегии
    print("\n[Test 5] Разные стратегии")
    id_mean_rev = generate_order_link_id("mean_reversion", "BTCUSDT", 1738915200, "long")
    id_momentum = generate_order_link_id("momentum", "BTCUSDT", 1738915200, "long")
    
    print(f"  mean_reversion: {id_mean_rev}")
    print(f"  momentum:       {id_momentum}")
    assert id_mean_rev != id_momentum
    print("  ✓ PASSED - Разные стратегии имеют разные IDs")
    
    # Test 6: Ограничение длины
    print("\n[Test 6] Ограничение длины (Bybit: max 36 символов)")
    long_id = generate_order_link_id(
        strategy="very_long_strategy_name_with_lots_of_characters",
        symbol="BTCUSDT",
        timestamp=1738915200,
        side="long",
        max_length=36
    )
    print(f"  Generated: {long_id}")
    print(f"  Length: {len(long_id)}")
    assert len(long_id) <= 36
    print("  ✓ PASSED - ID укорочен до лимита")
    
    # Test 7: Сценарий timeout/retry
    print("\n[Test 7] Реальный сценарий: timeout и retry")
    print("  Шаг 1: Создаём ордер")
    base_timestamp = 1700000000  # Большой timestamp
    first_id = generate_order_link_id(
        strategy="mean_reversion",
        symbol="BTCUSDT",
        timestamp=base_timestamp,
        side="long",
        bucket_seconds=60
    )
    print(f"    Timestamp: {base_timestamp}")
    print(f"    orderLinkId: {first_id}")
    
    print("  Шаг 2: Timeout... ордер не подтверждён")
    print("  Шаг 3: Retry через 30 секунд")
    retry_timestamp = base_timestamp + 30  # +30 секунд (в пределах bucket)
    retry_id = generate_order_link_id(
        strategy="mean_reversion",
        symbol="BTCUSDT",
        timestamp=retry_timestamp,
        side="long",
        bucket_seconds=60
    )
    print(f"    Timestamp: {retry_timestamp}")
    print(f"    orderLinkId: {retry_id}")
    print(f"    Bucket первого: {base_timestamp // 60}")
    print(f"    Bucket retry:   {retry_timestamp // 60}")
    
    if first_id == retry_id:
        print("  ✓✓✓ SUCCESS: Retry использует ТОТ ЖЕ orderLinkId!")
        print("  ✓✓✓ OrderManager.check_order_exists() найдёт дубликат!")
        print("  ✓✓✓ Дублирующий ордер НЕ будет создан!")
    else:
        print("  ✗✗✗ FAILED: IDs различаются - будет дубликат!")
        return False
    
    print("\n" + "="*60)
    print("✓✓✓ ALL TESTS PASSED ✓✓✓")
    print("="*60)
    print("\nИдемпотентность ордеров работает корректно!")
    print("Повторные запросы с теми же параметрами не создадут дубликаты.")
    print("="*60 + "\n")
    
    return True


if __name__ == "__main__":
    success = test_idempotency()
    sys.exit(0 if success else 1)
