"""
Тесты для идемпотентности ордеров через orderLinkId.
"""

import time
try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

from execution.order_idempotency import (
    generate_order_link_id,
    normalize_side,
    parse_order_link_id,
)


class TestGenerateOrderLinkId:
    """Тесты генерации стабильных orderLinkId"""

    def test_basic_generation(self):
        """Базовая генерация orderLinkId"""
        order_link_id = generate_order_link_id(
            strategy="mean_reversion",
            symbol="BTCUSDT",
            timestamp=1738915200,
            side="long",
        )
        
        assert order_link_id is not None
        assert "mean_reversion" in order_link_id
        assert "BTCUSDT" in order_link_id
        assert "L" in order_link_id  # Normalized side

    def test_idempotency_same_bucket(self):
        """Повторные вызовы в одном bucket должны давать одинаковый ID"""
        timestamp1 = 1738915200  # 0 секунд
        timestamp2 = 1738915230  # +30 секунд
        
        id1 = generate_order_link_id("strategy", "BTCUSDT", timestamp1, "long", bucket_seconds=60)
        id2 = generate_order_link_id("strategy", "BTCUSDT", timestamp2, "long", bucket_seconds=60)
        
        # В пределах одного bucket (60 секунд) - ОДИНАКОВЫЙ ID
        assert id1 == id2, "IDs должны совпадать в пределах bucket"

    def test_different_buckets(self):
        """Разные buckets должны давать разные IDs"""
        timestamp1 = 1738915200  # 0 секунд
        timestamp2 = 1738915261  # +61 секунда (следующий bucket)
        
        id1 = generate_order_link_id("strategy", "BTCUSDT", timestamp1, "long", bucket_seconds=60)
        id2 = generate_order_link_id("strategy", "BTCUSDT", timestamp2, "long", bucket_seconds=60)
        
        # Разные buckets - РАЗНЫЕ IDs
        assert id1 != id2, "IDs должны различаться в разных buckets"

    def test_different_sides(self):
        """Разные стороны должны давать разные IDs"""
        timestamp = 1738915200
        
        id_long = generate_order_link_id("strategy", "BTCUSDT", timestamp, "long")
        id_short = generate_order_link_id("strategy", "BTCUSDT", timestamp, "short")
        
        assert id_long != id_short, "Long и Short должны иметь разные IDs"

    def test_different_symbols(self):
        """Разные символы должны давать разные IDs"""
        timestamp = 1738915200
        
        id_btc = generate_order_link_id("strategy", "BTCUSDT", timestamp, "long")
        id_eth = generate_order_link_id("strategy", "ETHUSDT", timestamp, "long")
        
        assert id_btc != id_eth, "Разные символы должны иметь разные IDs"

    def test_different_strategies(self):
        """Разные стратегии должны давать разные IDs"""
        timestamp = 1738915200
        
        id1 = generate_order_link_id("mean_reversion", "BTCUSDT", timestamp, "long")
        id2 = generate_order_link_id("momentum", "BTCUSDT", timestamp, "long")
        
        assert id1 != id2, "Разные стратегии должны иметь разные IDs"

    def test_length_limit(self):
        """Проверка ограничения длины (Bybit: 36 символов)"""
        order_link_id = generate_order_link_id(
            strategy="very_long_strategy_name_that_exceeds_limit",
            symbol="BTCUSDT",
            timestamp=1738915200,
            side="long",
            max_length=36,
        )
        
        assert len(order_link_id) <= 36, f"ID слишком длинный: {len(order_link_id)} > 36"

    def test_bucket_seconds_customization(self):
        """Настройка размера bucket"""
        timestamp1 = 1738915200  # 0 секунд
        timestamp2 = 1738915150  # +150 секунд
        
        # С bucket=60: разные IDs
        id1_60 = generate_order_link_id("strategy", "BTCUSDT", timestamp1, "long", bucket_seconds=60)
        id2_60 = generate_order_link_id("strategy", "BTCUSDT", timestamp2, "long", bucket_seconds=60)
        assert id1_60 != id2_60
        
        # С bucket=300 (5 минут): одинаковые IDs
        id1_300 = generate_order_link_id("strategy", "BTCUSDT", timestamp1, "long", bucket_seconds=300)
        id2_300 = generate_order_link_id("strategy", "BTCUSDT", timestamp2, "long", bucket_seconds=300)
        assert id1_300 == id2_300


class TestNormalizeSide:
    """Тесты нормализации стороны сделки"""

    def test_long_variations(self):
        """Различные варианты long/buy"""
        assert normalize_side("long") == "L"
        assert normalize_side("Long") == "L"
        assert normalize_side("LONG") == "L"
        assert normalize_side("buy") == "L"
        assert normalize_side("Buy") == "L"
        assert normalize_side("BUY") == "L"

    def test_short_variations(self):
        """Различные варианты short/sell"""
        assert normalize_side("short") == "S"
        assert normalize_side("Short") == "S"
        assert normalize_side("SHORT") == "S"
        assert normalize_side("sell") == "S"
        assert normalize_side("Sell") == "S"
        assert normalize_side("SELL") == "S"

    def test_invalid_side(self):
        """Неизвестная сторона должна вызывать ошибку"""
        if not HAS_PYTEST:
            try:
                normalize_side("invalid")
                assert False, "Should raise ValueError"
            except ValueError:
                pass
        else:
            with pytest.raises(ValueError):
                normalize_side("invalid")


class TestParseOrderLinkId:
    """Тесты парсинга orderLinkId"""

    def test_basic_parsing(self):
        """Базовый парсинг orderLinkId"""
        order_link_id = "mean_rev_BTCUSDT_289819200_L"
        parsed = parse_order_link_id(order_link_id)
        
        assert parsed is not None
        assert parsed["strategy"] == "mean_rev"
        assert parsed["symbol"] == "BTCUSDT"
        assert parsed["bucket"] == 289819200
        assert parsed["side"] == "L"

    def test_complex_strategy_name(self):
        """Парсинг с составным именем стратегии"""
        order_link_id = "mean_reversion_with_rsi_BTCUSDT_289819200_S"
        parsed = parse_order_link_id(order_link_id)
        
        assert parsed["strategy"] == "mean_reversion_with_rsi"
        assert parsed["symbol"] == "BTCUSDT"
        assert parsed["side"] == "S"

    def test_invalid_format(self):
        """Неправильный формат должен вернуть None"""
        assert parse_order_link_id("invalid") is None
        assert parse_order_link_id("too_short_id") is None


class TestIdempotencyScenarios:
    """Тесты реальных сценариев идемпотентности"""

    def test_retry_scenario(self):
        """
        Сценарий: создание ордера с timeout и retry.
        
        1. Первый вызов в timestamp=1000
        2. Timeout
        3. Retry в timestamp=1030 (в пределах bucket=60)
        4. Должен использоваться ТОТ ЖЕ orderLinkId
        """
        # Первый вызов
        id1 = generate_order_link_id(
            strategy="mean_reversion",
            symbol="BTCUSDT",
            timestamp=1000,
            side="long",
            bucket_seconds=60
        )
        
        # Retry через 30 секунд
        id2 = generate_order_link_id(
            strategy="mean_reversion",
            symbol="BTCUSDT",
            timestamp=1030,
            side="long",
            bucket_seconds=60
        )
        
        # ИДЕМПОТЕНТНОСТЬ: одинаковые IDs
        assert id1 == id2
        print(f"✓ Retry использует тот же orderLinkId: {id1}")

    def test_different_signals_same_time(self):
        """
        Сценарий: две разные стратегии дают сигнал в одно время.
        
        Должны получить РАЗНЫЕ orderLinkIds.
        """
        timestamp = int(time.time())
        
        id1 = generate_order_link_id("strategy1", "BTCUSDT", timestamp, "long")
        id2 = generate_order_link_id("strategy2", "BTCUSDT", timestamp, "long")
        
        assert id1 != id2
        print(f"✓ Разные стратегии: {id1} != {id2}")

    def test_opposite_sides_same_time(self):
        """
        Сценарий: открытие long и short позиций в одно время.
        
        Должны получить РАЗНЫЕ orderLinkIds.
        """
        timestamp = int(time.time())
        
        id_long = generate_order_link_id("strategy", "BTCUSDT", timestamp, "long")
        id_short = generate_order_link_id("strategy", "BTCUSDT", timestamp, "short")
        
        assert id_long != id_short
        print(f"✓ Long vs Short: {id_long} != {id_short}")


def test_smoke_order_idempotency():
    """Smoke test для проверки основной функциональности"""
    print("\n=== Smoke Test: Order Idempotency ===")
    
    # 1. Генерация orderLinkId
    timestamp = int(time.time())
    order_link_id = generate_order_link_id(
        strategy="test_strategy",
        symbol="BTCUSDT",
        timestamp=timestamp,
        side="long",
    )
    print(f"✓ Generated orderLinkId: {order_link_id}")
    assert len(order_link_id) <= 36
    
    # 2. Идемпотентность при retry
    retry_timestamp = timestamp + 30  # +30 секунд
    retry_id = generate_order_link_id(
        strategy="test_strategy",
        symbol="BTCUSDT",
        timestamp=retry_timestamp,
        side="long",
    )
    assert order_link_id == retry_id
    print(f"✓ Retry (t+30s) uses same ID: {retry_id}")
    
    # 3. Парсинг обратно
    parsed = parse_order_link_id(order_link_id)
    assert parsed is not None
    assert parsed["strategy"] == "test_strategy"
    assert parsed["symbol"] == "BTCUSDT"
    assert parsed["side"] == "L"
    print(f"✓ Parsed back: {parsed}")
    
    print("\n✓✓✓ SMOKE TEST PASSED ✓✓✓")


if __name__ == "__main__":
    # Запуск smoke test
    test_smoke_order_idempotency()
    
    # Запуск всех тестов
    if HAS_PYTEST:
        pytest.main([__file__, "-v"])
    else:
        print("\nNote: Install pytest to run full test suite")
        print("Running manual tests instead...")
        
        # Запуск тестов вручную
        test_gen = TestGenerateOrderLinkId()
        test_gen.test_basic_generation()
        test_gen.test_idempotency_same_bucket()
        test_gen.test_different_buckets()
        test_gen.test_different_sides()
        test_gen.test_different_symbols()
        test_gen.test_different_strategies()
        test_gen.test_length_limit()
        test_gen.test_bucket_seconds_customization()
        print("✓ All TestGenerateOrderLinkId tests passed")
        
        test_norm = TestNormalizeSide()
        test_norm.test_long_variations()
        test_norm.test_short_variations()
        test_norm.test_invalid_side()
        print("✓ All TestNormalizeSide tests passed")
        
        test_parse = TestParseOrderLinkId()
        test_parse.test_basic_parsing()
        test_parse.test_complex_strategy_name()
        test_parse.test_invalid_format()
        print("✓ All TestParseOrderLinkId tests passed")
        
        test_scenarios = TestIdempotencyScenarios()
        test_scenarios.test_retry_scenario()
        test_scenarios.test_different_signals_same_time()
        test_scenarios.test_opposite_sides_same_time()
        print("✓ All TestIdempotencyScenarios tests passed")
        
        print("\n✓✓✓ ALL TESTS PASSED ✓✓✓")
