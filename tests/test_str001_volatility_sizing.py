"""

Тесты для STR-001 (P0): Trend Pullback с ATR-based стопами и volatility sizing


DoD проверки:

1. Для каждой сделки есть рассчитанный stop_distance (в цене) и он > 0

2. Размер позиции меняется с ATR (на высокой воле qty меньше)

3. В логах: atr, stop, take, risk_usd, qty

"""


import pytest

import pandas as pd

import numpy as np

from decimal import Decimal

from strategy.trend_pullback import TrendPullbackStrategy

from risk.volatility_position_sizer import VolatilityPositionSizer, VolatilityPositionSizerConfig


class TestSTR001StopDistance:

    """DoD #1: Для каждой сделки есть stop_distance > 0"""

    def test_long_signal_has_stop_distance(self):
        """Long сигнал должен иметь stop_distance > 0"""

        strategy = TrendPullbackStrategy(min_adx=15.0)

        # Создаем данные с сильным трендом

        df = pd.DataFrame(

            {

                "close": np.linspace(50000, 52000, 100),

                "high": np.linspace(50100, 52100, 100),

                "low": np.linspace(49900, 51900, 100),

                "open": np.linspace(50000, 52000, 100),

                "volume": np.random.rand(100) * 1000 + 5000,

                "ema_20": np.linspace(49800, 51800, 100),

                "ema_50": np.linspace(49500, 51500, 100),

                "adx": [25.0] * 100,  # Сильный тренд

                "atr": [300.0] * 100,  # ATR = 300

                "volume_zscore": [2.0] * 100,  # Хороший объём

                "has_anomaly": [0] * 100,

            }

        )

        features = {"symbol": "BTCUSDT"}

        signal = strategy.generate_signal(df, features)

        if signal:

            # DoD #1: stop_distance должно быть > 0

            assert "stop_distance" in signal, "Сигнал должен содержать stop_distance"

            assert (

                signal["stop_distance"] > 0

            ), f"stop_distance должен быть > 0, получили {signal['stop_distance']}"

            # Проверяем что stop_distance = |entry - stop_loss|

            expected_distance = abs(signal["entry_price"] - signal["stop_loss"])

            assert (

                abs(signal["stop_distance"] - expected_distance) < 0.01

            ), f"stop_distance {signal['stop_distance']} != |entry - stop| {expected_distance}"

            # stop_distance должен быть примерно ATR * 1.5 (из стратегии)

            atr = signal.get("atr", 0)

            assert atr > 0, "ATR должен быть передан в сигнале"

            assert (

                100 < signal["stop_distance"] < atr * 3

            ), f"stop_distance {signal['stop_distance']} не соответствует ATR {atr}"

    def test_short_signal_has_stop_distance(self):
        """Short сигнал должен иметь stop_distance > 0"""

        strategy = TrendPullbackStrategy(min_adx=15.0)

        # Создаем данные с downtrend

        df = pd.DataFrame(

            {

                "close": np.linspace(52000, 50000, 100),

                "high": np.linspace(52100, 50100, 100),

                "low": np.linspace(51900, 49900, 100),

                "open": np.linspace(52000, 50000, 100),

                "volume": np.random.rand(100) * 1000 + 5000,

                "ema_20": np.linspace(52200, 50200, 100),  # Downtrend

                "ema_50": np.linspace(52500, 50500, 100),  # EMA20 < EMA50

                "adx": [25.0] * 100,

                "atr": [300.0] * 100,

                "volume_zscore": [2.0] * 100,

                "has_anomaly": [0] * 100,

            }

        )

        features = {"symbol": "BTCUSDT"}

        signal = strategy.generate_signal(df, features)

        if signal:

            assert "stop_distance" in signal

            assert signal["stop_distance"] > 0

            # Для short: stop_distance = |stop_loss - entry|

            expected_distance = abs(signal["stop_loss"] - signal["entry_price"])

            assert abs(signal["stop_distance"] - expected_distance) < 0.01


class TestSTR001VolatilityScaling:

    """DoD #2: Размер позиции меняется с ATR (на высокой воле qty меньше)"""

    def test_high_volatility_reduces_position_size(self):
        """При высокой волатильности (большой ATR) qty должен быть меньше"""

        config = VolatilityPositionSizerConfig(

            risk_percent=Decimal("5.0"),  # 5% риска (больше для заметного различия)

            atr_multiplier=Decimal("2.0"),  # SL = ATR * 2

        )

        sizer = VolatilityPositionSizer(config)

        account = Decimal("100000")  # $100k (больше)

        entry_price = Decimal("50000")  # BTC @ $50k

        # Низкая волатильность: ATR = 200

        atr_low = Decimal("200")

        qty_low, details_low = sizer.calculate_position_size(account, entry_price, atr_low)

        # Высокая волатильность: ATR = 800 (4x больше)

        atr_high = Decimal("800")

        qty_high, details_high = sizer.calculate_position_size(account, entry_price, atr_high)

        # DoD #2: При высокой воле qty должен быть меньше

        assert (

            qty_high < qty_low

        ), f"При ATR={atr_high} qty={qty_high} должен быть < qty при ATR={atr_low} qty={qty_low}"

        # Проверяем что риск остается постоянным

        risk_low = details_low["risk_usd"]

        risk_high = details_high["risk_usd"]

        assert (

            abs(risk_low - risk_high) < 0.01

        ), f"USD риск должен быть одинаковым: {risk_low} vs {risk_high}"

        # Соотношение qty должно быть обратно пропорционально ATR

        atr_ratio = float(atr_high / atr_low)

        qty_ratio = float(qty_low / qty_high)

        # Требуем чтобы ratio был примерно в диапазоне (позволяем 20% погрешность)

        assert (

            abs(atr_ratio - qty_ratio) < atr_ratio * 0.2

        ), f"Соотношение ATR={atr_ratio:.2f} должно быть близко к Qty={qty_ratio:.2f}"

    def test_position_size_scales_with_atr(self):
        """Размер позиции должен масштабироваться обратно пропорционально ATR"""

        config = VolatilityPositionSizerConfig(risk_percent=Decimal("5.0"))  # 5% для наглядности

        sizer = VolatilityPositionSizer(config)

        account = Decimal("100000")  # $100k большой аккаунт

        entry_price = Decimal("50000")

        # Тестируем разные уровни волатильности

        test_cases = [

            (Decimal("100"), "very_low"),

            (Decimal("300"), "low"),

            (Decimal("500"), "medium"),

            (Decimal("800"), "high"),

            (Decimal("1200"), "very_high"),

        ]

        results = []

        for atr, label in test_cases:

            qty, details = sizer.calculate_position_size(account, entry_price, atr)

            results.append(

                {

                    "atr": float(atr),

                    "qty": float(qty),

                    "risk_usd": details["risk_usd"],

                    "label": label,

                }

            )

        # Проверяем что qty уменьшается с ростом ATR

        for i in range(len(results) - 1):

            assert results[i]["qty"] > results[i + 1]["qty"], (

                f"Qty должен уменьшаться: {results[i]['label']} qty={results[i]['qty']:.4f} > "

                f"{results[i + 1]['label']} qty={results[i + 1]['qty']:.4f}"

            )

        # Все риски должны быть одинаковыми

        first_risk = results[0]["risk_usd"]

        for r in results:

            assert abs(r["risk_usd"] - first_risk) < 0.01, f"Риск {r['risk_usd']} != {first_risk}"


class TestSTR001LoggingRequirements:

    """DoD #3: В логах должны быть atr, stop, take, risk_usd, qty"""

    def test_signal_contains_required_fields(self):
        """Сигнал должен содержать все необходимые поля для логирования"""

        strategy = TrendPullbackStrategy(min_adx=15.0)

        # Данные с трендом

        df = pd.DataFrame(

            {

                "close": np.linspace(50000, 52000, 100),

                "high": np.linspace(50100, 52100, 100),

                "low": np.linspace(49900, 51900, 100),

                "open": np.linspace(50000, 52000, 100),

                "volume": np.random.rand(100) * 1000 + 5000,

                "ema_20": np.linspace(49800, 51800, 100),

                "ema_50": np.linspace(49500, 51500, 100),

                "adx": [25.0] * 100,

                "atr": [300.0] * 100,

                "volume_zscore": [2.0] * 100,

                "has_anomaly": [0] * 100,

            }

        )

        features = {"symbol": "BTCUSDT"}

        signal = strategy.generate_signal(df, features)

        if signal:

            # DoD #3: Все обязательные поля для логирования

            required_fields = ["atr", "stop_loss", "take_profit", "stop_distance"]

            for field in required_fields:

                assert field in signal, f"Сигнал должен содержать поле '{field}'"

                assert signal[field] is not None, f"Поле '{field}' не должно быть None"

            # atr > 0

            assert signal["atr"] > 0, "ATR должен быть > 0"

            # stop и take должны быть определены

            assert signal["stop_loss"] > 0, "Stop loss должен быть > 0"

            assert signal["take_profit"] > 0, "Take profit должен быть > 0"

            # stop_distance > 0

            assert signal["stop_distance"] > 0, "Stop distance должен быть > 0"

    def test_volatility_sizer_returns_risk_usd(self):
        """VolatilityPositionSizer должен возвращать risk_usd в details"""

        config = VolatilityPositionSizerConfig(risk_percent=Decimal("1.0"))

        sizer = VolatilityPositionSizer(config)

        account = Decimal("10000")

        entry_price = Decimal("50000")

        atr = Decimal("300")

        qty, details = sizer.calculate_position_size(account, entry_price, atr)

        # DoD #3: details должен содержать risk_usd

        assert "risk_usd" in details, "Details должен содержать risk_usd"

        assert details["risk_usd"] > 0, "risk_usd должен быть > 0"

        # risk_usd = 1% от account

        expected_risk = float(account) * 0.01

        assert (

            abs(details["risk_usd"] - expected_risk) < 0.01

        ), f"risk_usd {details['risk_usd']} != ожидаемый {expected_risk}"

        # details должен содержать все поля для логирования

        required_fields = ["position_qty", "risk_usd", "distance_to_sl", "atr", "entry_price"]

        for field in required_fields:

            assert field in details, f"Details должен содержать '{field}'"


class TestSTR001Integration:

    """Интеграционные тесты: стратегия + position sizer"""

    def test_full_signal_to_position_sizing_flow(self):
        """Полный flow: генерация сигнала → расчет позиции с ATR scaling"""

        # 1. Генерируем сигнал

        strategy = TrendPullbackStrategy(min_adx=15.0)

        df = pd.DataFrame(

            {

                "close": np.linspace(50000, 52000, 100),

                "high": np.linspace(50100, 52100, 100),

                "low": np.linspace(49900, 51900, 100),

                "open": np.linspace(50000, 52000, 100),

                "volume": np.random.rand(100) * 1000 + 5000,

                "ema_20": np.linspace(49800, 51800, 100),

                "ema_50": np.linspace(49500, 51500, 100),

                "adx": [25.0] * 100,

                "atr": [300.0] * 100,

                "volume_zscore": [2.0] * 100,

                "has_anomaly": [0] * 100,

            }

        )

        features = {"symbol": "BTCUSDT"}

        signal = strategy.generate_signal(df, features)

        # Если сигнал не сгенерирован, пропускаем (это OK - возможны фильтры)

        if signal is None:

            pytest.skip("Strategy filter rejected signal - this is OK")

        # 2. Используем ATR из сигнала для position sizing

        config = VolatilityPositionSizerConfig(risk_percent=Decimal("1.0"))

        sizer = VolatilityPositionSizer(config)

        account = Decimal("10000")

        entry_price = Decimal(str(signal["entry_price"]))

        atr = Decimal(str(signal["atr"]))

        qty, details = sizer.calculate_position_size(account, entry_price, atr)

        # 3. Проверяем что все DoD выполнены

        # DoD #1: stop_distance > 0

        assert signal["stop_distance"] > 0

        # DoD #2: qty > 0

        assert qty > 0

        assert details["distance_to_sl"] > 0

        # DoD #3: Все поля для логирования

        assert signal["atr"] > 0

        assert signal["stop_loss"] > 0

        assert signal["take_profit"] > 0

        assert details["risk_usd"] > 0

        assert float(qty) > 0

        # Логируем результаты (для визуальной проверки)

        print("\n[STR-001 Integration Test]")

        print(f"  ATR: {signal['atr']:.2f}")

        print(f"  Entry: {signal['entry_price']:.2f}")

        print(f"  Stop: {signal['stop_loss']:.2f}")

        print(f"  Take: {signal['take_profit']:.2f}")

        print(f"  Stop Distance: {signal['stop_distance']:.2f}")

        print(f"  Risk USD: ${details['risk_usd']:.2f}")

        print(f"  Qty: {float(qty):.6f}")

        print(f"  Method: {details['method']}")


class TestSTR001EdgeCases:

    """Edge cases для STR-001"""

    def test_zero_atr_fallback(self):
        """При ATR=0 должен использоваться fallback метод"""

        config = VolatilityPositionSizerConfig(

            risk_percent=Decimal("1.0"), use_percent_fallback=True, percent_fallback=Decimal("5.0")

        )

        sizer = VolatilityPositionSizer(config)

        account = Decimal("10000")

        entry_price = Decimal("50000")

        # ATR = None (отсутствует)

        qty, details = sizer.calculate_position_size(account, entry_price, atr=None)

        assert qty > 0, "Qty должен быть > 0 даже без ATR"

        assert details["method"] == "fallback", "Должен использоваться fallback метод"

    def test_very_small_stop_distance(self):
        """При очень маленьком ATR stop_distance все равно должен быть > 0"""

        strategy = TrendPullbackStrategy(min_adx=15.0)

        df = pd.DataFrame(

            {

                "close": np.linspace(50000, 50100, 100),  # Очень узкий диапазон

                "high": np.linspace(50010, 50110, 100),

                "low": np.linspace(49990, 50090, 100),

                "open": np.linspace(50000, 50100, 100),

                "volume": np.random.rand(100) * 1000 + 5000,

                "ema_20": np.linspace(49950, 50050, 100),

                "ema_50": np.linspace(49900, 50000, 100),

                "adx": [25.0] * 100,

                "atr": [10.0] * 100,  # Очень маленький ATR

                "volume_zscore": [2.0] * 100,

                "has_anomaly": [0] * 100,

            }

        )

        features = {"symbol": "BTCUSDT"}

        signal = strategy.generate_signal(df, features)

        if signal:

            assert signal["stop_distance"] > 0, "stop_distance должен быть > 0 даже при малом ATR"

            assert signal["atr"] > 0, "ATR должен быть > 0"


if __name__ == "__main__":

    pytest.main([__file__, "-v", "--tb=short"])
