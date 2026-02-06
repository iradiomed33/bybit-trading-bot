"""

EXE-001 Validation Tests: Maker/Taker политика и выбор типа ордера


Сценарии:

1. TrendPullback в normal режиме → Maker (GTC, post_only, TTL=300)

2. Breakout в normal режиме → Maker (PostOnly, TTL=180)

3. MeanReversion в normal режиме → Maker (GTC, post_only, TTL=600)

4. Любая стратегия в high_vol_event → Taker (IOC/FOK, market)

5. Низкая уверенность (conf < 0.65) → сокращаем TTL вдвое

6. Комиссии: maker 0.02%, taker 0.04%

"""


from decimal import Decimal

from execution.order_policy import (

    OrderPolicySelector,

    COMMISSION_RATES,

)


class TestMakerTakerPolicy:

    """Тесты логики выбора типа ордера"""

    def test_trend_pullback_normal_mode(self):
        """Test 1: TrendPullback в normal режиме = Maker с GTC"""

        params = OrderPolicySelector.get_order_params(

            strategy_name="TrendPullback",

            regime="normal",

            confidence=0.75,

        )

        assert params["order_type"] == "Limit", "TrendPullback normal должен быть Limit"

        assert params["time_in_force"] == "GTC", "GTC для нормального режима"

        assert params["post_only"] is True, "post_only включен"

        assert params["ttl_seconds"] == 300, "TTL 5 минут"

        assert params["maker_intent"] is True, "maker_intent=True"

        assert params["expected_commission"] == float(Decimal("0.0002")), "maker комиссия"

        print("✅ TrendPullback normal: Limit GTC 300s maker")

    def test_breakout_normal_mode(self):
        """Test 2: Breakout в normal режиме = Maker с PostOnly"""

        params = OrderPolicySelector.get_order_params(

            strategy_name="Breakout",

            regime="normal",

            confidence=0.8,

        )

        assert params["order_type"] == "Limit"

        assert params["time_in_force"] == "PostOnly", "PostOnly для пробоя"

        assert params["post_only"] is True

        assert params["ttl_seconds"] == 180, "TTL 3 минуты для пробоя"

        assert params["maker_intent"] is True

        print("✅ Breakout normal: Limit PostOnly 180s maker")

    def test_mean_reversion_normal_mode(self):
        """Test 3: MeanReversion в normal режиме = Maker с GTC"""

        params = OrderPolicySelector.get_order_params(

            strategy_name="MeanReversion",

            regime="normal",

            confidence=0.7,

        )

        assert params["order_type"] == "Limit"

        assert params["time_in_force"] == "GTC"

        assert params["post_only"] is True

        assert params["ttl_seconds"] == 600, "TTL 10 минут для mean reversion"

        assert params["maker_intent"] is True

        print("✅ MeanReversion normal: Limit GTC 600s maker")

    def test_high_vol_event_all_strategies(self):
        """Test 4: high_vol_event для всех стратегий = Taker"""

        for strategy in ["TrendPullback", "Breakout", "MeanReversion"]:

            params = OrderPolicySelector.get_order_params(

                strategy_name=strategy,

                regime="high_vol_event",

                confidence=0.8,

            )

            assert params["order_type"] == "Market", f"{strategy} high_vol должен быть Market"

            assert params["post_only"] is False, "post_only отключен"

            assert params["maker_intent"] is False, "не maker"

            assert params["expected_commission"] == float(

                Decimal("0.0004")

            ), f"taker комиссия для {strategy}"

        print("✅ high_vol_event: все стратегии → Market taker")

    def test_low_confidence_reduces_ttl(self):
        """Test 5: Низкая уверенность (< 0.65) сокращает TTL вдвое"""

        # Normal confidence

        params_high = OrderPolicySelector.get_order_params(

            strategy_name="TrendPullback",

            regime="normal",

            confidence=0.8,

        )

        ttl_high = params_high["ttl_seconds"]

        # Low confidence

        params_low = OrderPolicySelector.get_order_params(

            strategy_name="TrendPullback",

            regime="normal",

            confidence=0.5,

        )

        ttl_low = params_low["ttl_seconds"]

        assert ttl_low < ttl_high, "TTL должен быть меньше при низкой уверенности"

        assert ttl_low == max(60, int(ttl_high * 0.5)), "TTL сокращён вдвое"

        print(f"✅ Low confidence: TTL сокращён {ttl_high}s → {ttl_low}s")

    def test_commission_rates(self):
        """Test 6: Комиссии maker 0.02%, taker 0.04%"""

        assert COMMISSION_RATES["maker"] == Decimal("0.0002")

        assert COMMISSION_RATES["taker"] == Decimal("0.0004")

        # Maker policy

        policy_maker = OrderPolicySelector.get_policy(

            strategy_name="TrendPullback",

            regime="normal",

            confidence=0.7,

        )

        assert policy_maker.expected_commission_rate() == Decimal("0.0002")

        # Taker policy

        policy_taker = OrderPolicySelector.get_policy(

            strategy_name="Breakout",

            regime="high_vol_event",

            confidence=0.7,

        )

        assert policy_taker.expected_commission_rate() == Decimal("0.0004")

        print("✅ Commission rates: maker=0.02%, taker=0.04%")

    def test_order_params_structure(self):
        """Test 7: Структура параметров ордера с required fields"""

        params = OrderPolicySelector.get_order_params(

            strategy_name="TrendPullback",

            regime="normal",

            confidence=0.75,

        )

        required_keys = [

            "order_type",

            "time_in_force",

            "post_only",

            "ttl_seconds",

            "maker_intent",

            "exec_type",

            "expected_commission",

        ]

        for key in required_keys:

            assert key in params, f"Missing required key: {key}"

        print("✅ Order params structure complete")

    def test_unknown_strategy_fallback(self):
        """Test 8: Неизвестная стратегия → fallback на консервативный maker"""

        params = OrderPolicySelector.get_order_params(

            strategy_name="UnknownStrategy",

            regime="normal",

            confidence=0.75,

        )

        assert params["order_type"] == "Limit"

        assert params["time_in_force"] == "GTC"

        assert params["post_only"] is True

        assert params["maker_intent"] is True

        print("✅ Unknown strategy: fallback к консервативному maker")

    def test_post_only_means_maker_intent(self):
        """Test 9: post_only=True всегда означает maker_intent=True"""

        policy = OrderPolicySelector.get_policy(

            strategy_name="Breakout",

            regime="normal",

            confidence=0.75,

        )

        if policy.post_only:

            assert policy.is_maker_intent() is True

        print("✅ post_only → maker_intent=True")

    def test_regime_modes(self):
        """Test 10: Все режимы могут быть обработаны"""

        regimes = ["trend_up", "trend_down", "range", "normal", "high_vol_event"]

        for regime in regimes:

            params = OrderPolicySelector.get_order_params(

                strategy_name="TrendPullback",

                regime=regime,

                confidence=0.7,

            )

            # Все режимы кроме high_vol_event → Maker

            if regime == "high_vol_event":

                assert params["order_type"] == "Market", f"{regime} должен быть Market"

            else:

                assert params["order_type"] == "Limit", f"{regime} должен быть Limit"

        print("✅ All regimes handled: trend_up/down, range, normal, high_vol_event")


class TestOrderPolicyLogging:

    """Тесты логирования параметров ордера"""

    def test_logging_fields_present(self):
        """Test 11: Все поля для логирования присутствуют"""

        params = OrderPolicySelector.get_order_params(

            strategy_name="Breakout",

            regime="normal",

            confidence=0.8,

        )

        log_fields = {

            "order_type": params["order_type"],

            "time_in_force": params["time_in_force"],

            "post_only": params["post_only"],

            "maker_intent": params["maker_intent"],

            "ttl_seconds": params["ttl_seconds"],

            "exec_type": params["exec_type"],

            "expected_commission": params["expected_commission"],

        }

        # Все поля должны быть для логирования

        log_message = (

            f"Order: {log_fields['order_type']} | "

            f"TTF={log_fields['time_in_force']} | "

            f"PostOnly={log_fields['post_only']} | "

            f"MakerIntent={log_fields['maker_intent']} | "

            f"TTL={log_fields['ttl_seconds']}s | "

            f"ExecType={log_fields['exec_type']} | "

            f"Commission={log_fields['expected_commission']:.4f}"

        )

        assert "Limit" in log_message

        assert "300" not in log_message  # Breakout имеет 180

        assert "True" in log_message

        print(f"✅ Logging: {log_message}")


if __name__ == "__main__":

    print("=" * 80)

    print("EXE-001 MAKER/TAKER POLICY TEST")

    print("=" * 80)

    try:

        test = TestMakerTakerPolicy()

        test.test_trend_pullback_normal_mode()

        test.test_breakout_normal_mode()

        test.test_mean_reversion_normal_mode()

        test.test_high_vol_event_all_strategies()

        test.test_low_confidence_reduces_ttl()

        test.test_commission_rates()

        test.test_order_params_structure()

        test.test_unknown_strategy_fallback()

        test.test_post_only_means_maker_intent()

        test.test_regime_modes()

        test2 = TestOrderPolicyLogging()

        test2.test_logging_fields_present()

        print("\n" + "=" * 80)

        print("Test Results:")

        print("   ✅ PASSED: TrendPullback maker policy")

        print("   ✅ PASSED: Breakout maker policy")

        print("   ✅ PASSED: MeanReversion maker policy")

        print("   ✅ PASSED: high_vol_event taker policy")

        print("   ✅ PASSED: Low confidence TTL reduction")

        print("   ✅ PASSED: Commission rates (maker 0.02%, taker 0.04%)")

        print("   ✅ PASSED: Order params structure")

        print("   ✅ PASSED: Unknown strategy fallback")

        print("   ✅ PASSED: post_only → maker_intent")

        print("   ✅ PASSED: All regime modes")

        print("   ✅ PASSED: Logging fields")

        print("\n🎉 ALL EXE-001 TESTS PASSED")

        print("\nDoD Validation:")

        print("   ✅ Определена логика выбора типа ордера (maker vs taker)")

        print("   ✅ post_only и TTL добавлены где уместно")

        print("   ✅ В логах: order_type, time_in_force, post_only, maker_intent")

        print("   ✅ Комиссии: maker 0.02%, taker 0.04%")

        print("=" * 80)

    except AssertionError as e:

        print(f"\n❌ TEST FAILED: {e}")

        raise

    except Exception as e:

        print(f"\n❌ ERROR: {e}")

        raise
