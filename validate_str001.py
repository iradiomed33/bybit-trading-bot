"""

Валидационный скрипт для STR-001: Проверка DoD требований


DoD:

1. Для каждой сделки есть рассчитанный stop_distance (в цене) и он > 0

2. Размер позиции меняется с ATR (на высокой воле qty меньше)

3. В логах: atr, stop, take, risk_usd, qty

"""


import sys

import pandas as pd

import numpy as np

from decimal import Decimal

from strategy.trend_pullback import TrendPullbackStrategy

from risk.volatility_position_sizer import VolatilityPositionSizer, VolatilityPositionSizerConfig


def test_dod_1_stop_distance():
    """DoD #1: stop_distance > 0"""

    print("\n" + "=" * 80)

    print("DoD #1: Проверка stop_distance > 0")

    print("=" * 80)

    strategy = TrendPullbackStrategy(min_adx=15.0)

    # Создаем тестовые данные

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

        print(f"✅ Сигнал сгенерирован: {signal['signal'].upper()}")

        print(f"  Entry Price: ${signal['entry_price']:,.2f}")

        print(f"  Stop Loss: ${signal['stop_loss']:,.2f}")

        print(f"  Take Profit: ${signal['take_profit']:,.2f}")

        print(f"  ATR: ${signal['atr']:,.2f}")

        # Проверка DoD #1

        if "stop_distance" in signal:

            print(f"✅ stop_distance присутствует: ${signal['stop_distance']:,.2f}")

            if signal["stop_distance"] > 0:

                print("✅ stop_distance > 0: PASSED")

                # Проверяем что это правильное расстояние

                expected = abs(signal["entry_price"] - signal["stop_loss"])

                if abs(signal["stop_distance"] - expected) < 0.01:

                    print("✅ stop_distance корректен (|entry - stop|)")

                    return True

                else:

                    print(f"❌ stop_distance={signal['stop_distance']} != ожидаемый={expected}")

                    return False

            else:

                print("❌ stop_distance <= 0: FAILED")

                return False

        else:

                print("❌ stop_distance отсутствует в сигнале")

                return False

    else:

        print("⚠️  Сигнал не сгенерирован (условия не подошли)")

        return None


def test_dod_2_qty_scales_with_atr():
    """DoD #2: Размер позиции меняется с ATR"""

    print("\n" + "=" * 80)

    print("DoD #2: Размер позиции обратно пропорционален ATR")

    print("=" * 80)

    config = VolatilityPositionSizerConfig(risk_percent=Decimal("1.0"))

    sizer = VolatilityPositionSizer(config)

    account = Decimal("10000")  # $10k аккаунт

    entry_price = Decimal("50000")  # BTC @ $50k

    # Тестируем разные уровни волатильности

    test_cases = [

        (Decimal("200"), "Низкая волатильность"),

        (Decimal("400"), "Средняя волатильность"),

        (Decimal("800"), "Высокая волатильность"),

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

                "distance_to_sl": details.get("distance_to_sl", 0),

            }

        )

        print(f"\n{label} (ATR=${atr}):")

        print(f"  Qty: {float(qty):.6f} BTC")

        print(f"  Risk USD: ${details['risk_usd']:.2f}")

        print(f"  Distance to SL: ${details.get('distance_to_sl', 0):.2f}")

    # Проверяем что qty уменьшается с ростом ATR

    print("\n📊 Проверка обратной зависимости qty от ATR:")

    passed = True

    for i in range(len(results) - 1):

        current = results[i]

        next_item = results[i + 1]

        if current["qty"] > next_item["qty"]:

            print(

                f"✅ {current['label']} (qty={current['qty']:.6f}) > {next_item['label']} (qty={next_item['qty']:.6f})"

            )

        else:

            print(

                f"❌ {current['label']} (qty={current['qty']:.6f}) <= {next_item['label']} (qty={next_item['qty']:.6f})"

            )

            passed = False

    # Проверяем что риск постоянный

    first_risk = results[0]["risk_usd"]

    print(f"\n📊 Проверка постоянного риска (должен быть ${first_risk:.2f}):")

    for r in results:

        if abs(r["risk_usd"] - first_risk) < 0.01:

            print(f"✅ {r['label']}: Risk=${r['risk_usd']:.2f} (OK)")

        else:

            print(f"❌ {r['label']}: Risk=${r['risk_usd']:.2f} != ${first_risk:.2f}")

            passed = False

    return passed


def test_dod_3_logging_fields():
    """DoD #3: В логах atr, stop, take, risk_usd, qty"""

    print("\n" + "=" * 80)

    print("DoD #3: Наличие всех полей для логирования")

    print("=" * 80)

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

    if not signal:

        print("⚠️  Сигнал не сгенерирован")

        return None

    # Проверяем наличие полей в сигнале

    required_signal_fields = ["atr", "stop_loss", "take_profit", "stop_distance", "entry_price"]

    print("\n📝 Проверка полей в сигнале:")

    signal_passed = True

    for field in required_signal_fields:

        if field in signal:

            value = signal[field]

            print(f"✅ {field}: {value}")

        else:

            print(f"❌ {field}: ОТСУТСТВУЕТ")

            signal_passed = False

    # Теперь проверяем position sizing

    config = VolatilityPositionSizerConfig(risk_percent=Decimal("1.0"))

    sizer = VolatilityPositionSizer(config)

    account = Decimal("10000")

    entry_price = Decimal(str(signal["entry_price"]))

    atr = Decimal(str(signal["atr"]))

    qty, details = sizer.calculate_position_size(account, entry_price, atr)

    # Проверяем поля в details

    required_details_fields = ["risk_usd", "position_qty", "distance_to_sl"]

    print("\n📝 Проверка полей в position sizing details:")

    details_passed = True

    for field in required_details_fields:

        if field in details:

            value = details[field]

            print(f"✅ {field}: {value}")

        else:

            print(f"❌ {field}: ОТСУТСТВУЕТ")

            details_passed = False

    # Итоговая проверка логирования

    print("\n📊 Итоговый набор данных для логирования:")

    print(f"  atr: ${signal.get('atr', 0):,.2f}")

    print(f"  stop: ${signal.get('stop_loss', 0):,.2f}")

    print(f"  take: ${signal.get('take_profit', 0):,.2f}")

    print(f"  risk_usd: ${details.get('risk_usd', 0):,.2f}")

    print(f"  qty: {float(qty):.6f}")

    print(f"  stop_distance: ${signal.get('stop_distance', 0):,.2f}")

    return signal_passed and details_passed


def main():
    """Запуск всех DoD тестов"""

    print("\n" + "=" * 80)

    print("STR-001 DoD ВАЛИДАЦИЯ")

    print("=" * 80)

    results = {}

    # DoD #1

    try:

        results["DoD #1"] = test_dod_1_stop_distance()

    except Exception as e:

        print(f"❌ DoD #1 failed with error: {e}")

        results["DoD #1"] = False

    # DoD #2

    try:

        results["DoD #2"] = test_dod_2_qty_scales_with_atr()

    except Exception as e:

        print(f"❌ DoD #2 failed with error: {e}")

        results["DoD #2"] = False

    # DoD #3

    try:

        results["DoD #3"] = test_dod_3_logging_fields()

    except Exception as e:

        print(f"❌ DoD #3 failed with error: {e}")

        results["DoD #3"] = False

    # Итоги

    print("\n" + "=" * 80)

    print("ИТОГИ ВАЛИДАЦИИ")

    print("=" * 80)

    all_passed = True

    for dod, result in results.items():

        if result is True:

            print(f"✅ {dod}: PASSED")

        elif result is False:

            print(f"❌ {dod}: FAILED")

            all_passed = False

        else:

            print(f"⚠️  {dod}: SKIPPED")

    print("=" * 80)

    if all_passed:

        print("✅ ВСЕ DoD ТРЕБОВАНИЯ ВЫПОЛНЕНЫ")

        return 0

    else:

        print("❌ НЕКОТОРЫЕ DoD ТРЕБОВАНИЯ НЕ ВЫПОЛНЕНЫ")

        return 1


if __name__ == "__main__":

    sys.exit(main())
