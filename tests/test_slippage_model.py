"""

Тесты для EXE-003: Slippage Model


DoD проверки:

1. Слиппедж применяется корректно (в BPS)

2. ATR множитель работает

3. Volume множитель работает

4. Impact на P&L реалистичный

5. Без слиппеджа, с реалистичным слиппеджем, с высоким слиппеджем - разные результаты

"""


import pytest

from decimal import Decimal

from execution.slippage_model import SlippageModel, create_slippage_model, SLIPPAGE_PRESETS


class TestSlippageModelBasic:

    """Базовые расчеты слиппеджа"""

    def test_base_slippage_calculation(self):
        """Базовый расчет слиппеджа"""

        model = SlippageModel(base_slippage_bps=Decimal("2"))

        qty = Decimal("1.0")

        price = Decimal("50000")

        slippage, details = model.calculate_slippage(qty=qty, entry_price=price)

        # Ожидаем: 50000 * 1.0 * (2 / 10000) = 10 USDT

        assert slippage == Decimal("10")

        assert details["base_slippage_bps"] == 2.0

        assert details["notional"] == 50000.0

    def test_slippage_scales_with_qty(self):
        """Слиппедж масштабируется с количеством"""

        model = SlippageModel(base_slippage_bps=Decimal("2"))

        # Малое количество

        slippage_small, _ = model.calculate_slippage(

            qty=Decimal("0.5"), entry_price=Decimal("50000")

        )

        # Большое количество

        slippage_large, _ = model.calculate_slippage(

            qty=Decimal("2.0"), entry_price=Decimal("50000")

        )

        assert slippage_large == slippage_small * 4

    def test_slippage_scales_with_price(self):
        """Слиппедж масштабируется с ценой"""

        model = SlippageModel(base_slippage_bps=Decimal("2"))

        # Низкая цена

        slippage_low, _ = model.calculate_slippage(qty=Decimal("1.0"), entry_price=Decimal("10000"))

        # Высокая цена

        slippage_high, _ = model.calculate_slippage(

            qty=Decimal("1.0"), entry_price=Decimal("100000")

        )

        assert slippage_high == slippage_low * 10


class TestSlippageMultipliers:

    """Тесты для множителей слиппеджа"""

    def test_volatility_multiplier_increases_slippage(self):
        """Высокая волатильность увеличивает слиппедж"""

        model = SlippageModel(

            base_slippage_bps=Decimal("2"),

            volatility_factor_enabled=True,

            volume_factor_enabled=False,

        )

        qty = Decimal("1.0")

        price = Decimal("50000")

        # Низкая волатильность (ATR = средний ATR)

        slippage_low_vol, details_low = model.calculate_slippage(

            qty=qty,

            entry_price=price,

            atr=Decimal("1000"),

            atr_sma=Decimal("1000"),

        )

        # Высокая волатильность (ATR = 2x средний ATR)

        slippage_high_vol, details_high = model.calculate_slippage(

            qty=qty,

            entry_price=price,

            atr=Decimal("2000"),

            atr_sma=Decimal("1000"),

        )

        assert slippage_high_vol > slippage_low_vol

        assert details_high["effective_slippage_bps"] > details_low["effective_slippage_bps"]

    def test_volume_multiplier_increases_slippage(self):
        """Низкий объем увеличивает слиппедж"""

        model = SlippageModel(

            base_slippage_bps=Decimal("2"),

            volatility_factor_enabled=False,

            volume_factor_enabled=True,

        )

        qty = Decimal("1.0")

        price = Decimal("50000")

        # Высокий объем (volume = средний volume)

        slippage_high_vol, details_high = model.calculate_slippage(

            qty=qty,

            entry_price=price,

            volume=Decimal("1000000"),

            avg_volume=Decimal("1000000"),

        )

        # Низкий объем (volume = 50% среднего)

        slippage_low_vol, details_low = model.calculate_slippage(

            qty=qty,

            entry_price=price,

            volume=Decimal("500000"),

            avg_volume=Decimal("1000000"),

        )

        assert slippage_low_vol > slippage_high_vol

        assert details_low["effective_slippage_bps"] > details_high["effective_slippage_bps"]

    def test_both_multipliers_combine(self):
        """Оба множителя комбинируются"""

        model = SlippageModel(

            base_slippage_bps=Decimal("2"),

            volatility_factor_enabled=True,

            volume_factor_enabled=True,

        )

        qty = Decimal("1.0")

        price = Decimal("50000")

        # Плохие условия: высокая волатильность + низкий объем

        slippage_bad, details_bad = model.calculate_slippage(

            qty=qty,

            entry_price=price,

            atr=Decimal("2000"),

            atr_sma=Decimal("1000"),

            volume=Decimal("500000"),

            avg_volume=Decimal("1000000"),

        )

        # Хорошие условия: низкая волатильность + высокий объем

        slippage_good, details_good = model.calculate_slippage(

            qty=qty,

            entry_price=price,

            atr=Decimal("1000"),

            atr_sma=Decimal("1000"),

            volume=Decimal("1000000"),

            avg_volume=Decimal("1000000"),

        )

        assert slippage_bad > slippage_good

        assert details_bad["volatility_multiplier"] * details_bad["volume_multiplier"] > 1.0


class TestApplySlippageToPrice:

    """Применение слиппеджа к цене"""

    def test_buy_slippage_increases_price(self):
        """При покупке слиппедж повышает цену"""

        model = SlippageModel(base_slippage_bps=Decimal("2"))

        price = Decimal("50000")

        qty = Decimal("1.0")

        slipped_price, details = model.apply_slippage_to_price(price=price, qty=qty, is_buy=True)

        assert slipped_price > price

        assert details["slipped_price"] > 50000

    def test_sell_slippage_decreases_price(self):
        """При продаже слиппедж понижает цену"""

        model = SlippageModel(base_slippage_bps=Decimal("2"))

        price = Decimal("50000")

        qty = Decimal("1.0")

        slipped_price, details = model.apply_slippage_to_price(price=price, qty=qty, is_buy=False)

        assert slipped_price < price

        assert details["slipped_price"] < 50000

    def test_slippage_impact_in_bps(self):
        """Слиппедж выражен в BPS в деталях"""

        model = SlippageModel(base_slippage_bps=Decimal("2"))

        price = Decimal("50000")

        qty = Decimal("1.0")

        slipped_price, details = model.apply_slippage_to_price(price=price, qty=qty, is_buy=True)

        # Impact должен быть ~2 bps

        impact_bps = details["price_impact_bps"]

        assert 1.5 < impact_bps < 2.5


class TestPnLImpact:

    """Влияние слиппеджа на P&L"""

    def test_slippage_reduces_profit(self):
        """Слиппедж уменьшает прибыль"""

        model = SlippageModel(base_slippage_bps=Decimal("2"))

        # Длинная позиция: вход @ 50000, выход @ 51000 (2% прибыль)

        entry_qty = Decimal("1.0")

        entry_price = Decimal("50000")

        exit_qty = Decimal("1.0")

        exit_price = Decimal("51000")

        impact = model.get_slippage_impact_on_pnl(

            entry_qty=entry_qty,

            entry_price=entry_price,

            exit_qty=exit_qty,

            exit_price=exit_price,

        )

        gross_pnl = Decimal("1000")  # (51000 - 50000) * 1

        total_slippage = Decimal(str(impact["total_slippage"]))

        assert total_slippage > 0

        assert impact["slippage_impact_pct"] > 0

    def test_high_slippage_kills_small_trades(self):
        """Высокий слиппедж убивает малые торговли"""

        model_high = SlippageModel(base_slippage_bps=Decimal("50"))  # 50 bps

        # Малая прибыль (0.5%)

        entry_qty = Decimal("1.0")

        entry_price = Decimal("50000")

        exit_qty = Decimal("1.0")

        exit_price = Decimal("50250")  # +0.5%

        impact = model_high.get_slippage_impact_on_pnl(

            entry_qty=entry_qty,

            entry_price=entry_price,

            exit_qty=exit_qty,

            exit_price=exit_price,

        )

        # Слиппедж потребляет большую часть прибыли

        assert impact["slippage_impact_pct"] > 50


class TestPresets:

    """Тест preset конфигураций"""

    def test_none_preset_has_zero_slippage(self):
        """None preset = нет слиппеджа"""

        model = create_slippage_model("none")

        slippage, _ = model.calculate_slippage(qty=Decimal("1.0"), entry_price=Decimal("50000"))

        assert slippage == Decimal("0")

    def test_realistic_preset_has_slippage(self):
        """Realistic preset имеет слиппедж"""

        model = create_slippage_model("realistic")

        slippage, _ = model.calculate_slippage(qty=Decimal("1.0"), entry_price=Decimal("50000"))

        assert slippage > 0

    def test_high_preset_more_slippage_than_minimal(self):
        """High preset > minimal preset"""

        model_minimal = create_slippage_model("minimal")

        model_high = create_slippage_model("high")

        slippage_minimal, _ = model_minimal.calculate_slippage(

            qty=Decimal("1.0"), entry_price=Decimal("50000")

        )

        slippage_high, _ = model_high.calculate_slippage(

            qty=Decimal("1.0"), entry_price=Decimal("50000")

        )

        assert slippage_high > slippage_minimal


class TestSlippageComparison:

    """Сравнение сценариев слиппеджа"""

    def test_different_presets_produce_different_results(self):
        """Разные presets дают разные результаты"""

        entry_qty = Decimal("10.0")

        entry_price = Decimal("50000")

        exit_qty = Decimal("10.0")

        exit_price = Decimal("51000")

        results = {}

        for preset in SLIPPAGE_PRESETS.keys():

            model = create_slippage_model(preset)

            impact = model.get_slippage_impact_on_pnl(

                entry_qty=entry_qty,

                entry_price=entry_price,

                exit_qty=exit_qty,

                exit_price=exit_price,

            )

            results[preset] = impact

        # None не должен иметь слиппеджа

        assert results["none"]["total_slippage"] == 0

        # Остальные должны иметь слиппедж

        assert results["minimal"]["total_slippage"] > 0

        assert results["realistic"]["total_slippage"] > results["minimal"]["total_slippage"]

        assert results["high"]["total_slippage"] > results["realistic"]["total_slippage"]


if __name__ == "__main__":

    pytest.main([__file__, "-v"])
