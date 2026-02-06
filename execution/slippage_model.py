"""

EXE-003: Slippage Model - реалистичный расчет проскальзывания


Модель проскальзывания учитывает:

1. Базовое проскальзывание (slippage_bps)

2. Волатильность (ATR-зависимое)

3. Ликвидность (volume-зависимое)


Формула:

slippage = base_slippage_bps * (1 + volatility_factor + volume_factor)


Применяется отдельно от комиссии:

- Комиссия: фиксированная % от notional

- Слиппедж: переменный % в зависимости от условий

"""


from decimal import Decimal

from typing import Dict, Optional, Tuple

import logging


logger = logging.getLogger(__name__)


class SlippageModel:

    """

    Калькулятор проскальзывания для paper trading и backtest.


    Параметры:

        base_slippage_bps: Базовое проскальзывание в basis points (по умолчанию 2 bps = 0.0002)

        volatility_factor_enabled: Учитывать волатильность (ATR)

        volume_factor_enabled: Учитывать ликвидность (volume)

    """

    def __init__(

        self,

        base_slippage_bps: Decimal = Decimal("2"),  # 2 bps = 0.0002

        volatility_factor_enabled: bool = True,

        volume_factor_enabled: bool = True,

    ):
        """

        Инициализировать модель проскальзывания.


        Args:

            base_slippage_bps: Базовое проскальзывание в basis points (1 bps = 0.0001)

            volatility_factor_enabled: Включить волатильность-зависимый слиппедж

            volume_factor_enabled: Включить объем-зависимый слиппедж

        """

        self.base_slippage_bps = Decimal(str(base_slippage_bps))

        self.volatility_factor_enabled = volatility_factor_enabled

        self.volume_factor_enabled = volume_factor_enabled

        logger.info(

            f"SlippageModel initialized: base={self.base_slippage_bps} bps, "

            f"volatility={volatility_factor_enabled}, volume={volume_factor_enabled}"

        )

    def calculate_slippage(

        self,

        qty: Decimal,

        entry_price: Decimal,

        atr: Optional[Decimal] = None,

        atr_sma: Optional[Decimal] = None,

        volume: Optional[Decimal] = None,

        avg_volume: Optional[Decimal] = None,

    ) -> Tuple[Decimal, Dict]:
        """

        Расчитать проскальзывание для сделки.


        Args:

            qty: Количество

            entry_price: Цена входа

            atr: Текущий ATR

            atr_sma: Средний ATR (долгосрочный)

            volume: Текущий объем

            avg_volume: Средний объем


        Returns:

            (slippage_amount, details_dict)


        Пример:

            slippage, details = model.calculate_slippage(

                qty=Decimal("1.0"),

                entry_price=Decimal("50000"),

                atr=Decimal("1500"),

                atr_sma=Decimal("1200"),

                volume=Decimal("1000000"),

                avg_volume=Decimal("2000000"),

            )

            # slippage = 100 USDT (0.0002 * 50000 * 1.0)

        """

        notional = qty * entry_price

        # Начисляем с базового проскальзывания

        slippage_bps = self.base_slippage_bps

        # Добавляем волатильность-зависимый множитель

        volatility_multiplier = Decimal("1")

        if self.volatility_factor_enabled and atr and atr_sma:

            # Если ATR > средний ATR, слиппедж больше

            # volatility_multiplier = 1 + (ATR - ATR_SMA) / ATR_SMA

            volatility_multiplier = Decimal("1") + (atr - atr_sma) / atr_sma

            volatility_multiplier = max(volatility_multiplier, Decimal("1"))  # min 1x

        # Добавляем ликвидность-зависимый множитель

        volume_multiplier = Decimal("1")

        if self.volume_factor_enabled and volume and avg_volume:

            # Если volume < средний volume, слиппедж больше

            # volume_multiplier = 1 + (avg_volume - volume) / avg_volume

            volume_multiplier = Decimal("1") + (avg_volume - volume) / avg_volume

            volume_multiplier = max(volume_multiplier, Decimal("1"))  # min 1x

        # Финальный расчет

        total_multiplier = volatility_multiplier * volume_multiplier

        effective_slippage_bps = slippage_bps * total_multiplier

        # Преобразуем bps в абсолютное значение

        # 1 bps = 0.0001 = 1/10000

        slippage_ratio = effective_slippage_bps / Decimal("10000")

        slippage_amount = notional * slippage_ratio

        details = {

            "base_slippage_bps": float(self.base_slippage_bps),

            "effective_slippage_bps": float(effective_slippage_bps),

            "volatility_multiplier": float(volatility_multiplier),

            "volume_multiplier": float(volume_multiplier),

            "notional": float(notional),

            "slippage_amount": float(slippage_amount),

        }

        logger.debug(

            f"Slippage calculated: {slippage_amount:.4f} USDT "

            f"({effective_slippage_bps:.2f} bps) on {notional:.2f} notional"

        )

        return slippage_amount, details

    def apply_slippage_to_price(

        self,

        price: Decimal,

        qty: Decimal,

        is_buy: bool,

        atr: Optional[Decimal] = None,

        atr_sma: Optional[Decimal] = None,

        volume: Optional[Decimal] = None,

        avg_volume: Optional[Decimal] = None,

    ) -> Tuple[Decimal, Dict]:
        """

        Применить проскальзывание к цене (покупка дороже, продажа дешевле).


        Args:

            price: Базовая цена

            qty: Количество

            is_buy: True = покупка (цена растет), False = продажа (цена падает)

            atr, atr_sma, volume, avg_volume: Параметры для расчета множителей


        Returns:

            (slipped_price, details)


        Пример:

            # При покупке слиппедж повышает цену

            buy_price, details = model.apply_slippage_to_price(

                price=Decimal("50000"),

                qty=Decimal("1.0"),

                is_buy=True,

            )

            # buy_price может быть 50010 (на 0.02% больше)


            # При продаже слиппедж понижает цену

            sell_price, details = model.apply_slippage_to_price(

                price=Decimal("51000"),

                qty=Decimal("1.0"),

                is_buy=False,

            )

            # sell_price может быть 50990 (на 0.02% меньше)

        """

        slippage_amount, details = self.calculate_slippage(

            qty=qty,

            entry_price=price,

            atr=atr,

            atr_sma=atr_sma,

            volume=volume,

            avg_volume=avg_volume,

        )

        # Преобразуем абсолютное значение проскальзывания в цену

        slippage_per_unit = slippage_amount / qty

        if is_buy:

            # При покупке цена выше (хуже для нас)

            slipped_price = price + slippage_per_unit

        else:

            # При продаже цена ниже (хуже для нас)

            slipped_price = price - slippage_per_unit

        details["slipped_price"] = float(slipped_price)

        details["price_impact_bps"] = float(abs(slipped_price - price) / price * Decimal("10000"))

        return slipped_price, details

    def get_slippage_impact_on_pnl(

        self,

        entry_qty: Decimal,

        entry_price: Decimal,

        exit_qty: Decimal,

        exit_price: Decimal,

        atr: Optional[Decimal] = None,

        atr_sma: Optional[Decimal] = None,

        volume: Optional[Decimal] = None,

        avg_volume: Optional[Decimal] = None,

    ) -> Dict:
        """

        Получить полное влияние слиппеджа на P&L (entry + exit).


        Args:

            entry_qty: Количество при входе

            entry_price: Цена входа

            exit_qty: Количество при выходе

            exit_price: Цена выхода

            atr, atr_sma, volume, avg_volume: Параметры множителей


        Returns:

            Dict с detalями:

                - entry_slippage: проскальзывание при входе

                - exit_slippage: проскальзывание при выходе

                - total_slippage: общее проскальзывание

                - impact_on_pnl: влияние на P&L (в процентах)

        """

        entry_slippage, entry_details = self.calculate_slippage(

            qty=entry_qty,

            entry_price=entry_price,

            atr=atr,

            atr_sma=atr_sma,

            volume=volume,

            avg_volume=avg_volume,

        )

        exit_slippage, exit_details = self.calculate_slippage(

            qty=exit_qty,

            entry_price=exit_price,

            atr=atr,

            atr_sma=atr_sma,

            volume=volume,

            avg_volume=avg_volume,

        )

        total_slippage = entry_slippage + exit_slippage

        gross_pnl = (exit_price - entry_price) * exit_qty

        # Если gross_pnl = 0, избегаем деления на 0

        if gross_pnl == 0:

            impact_pct = Decimal("100") if total_slippage > 0 else Decimal("0")

        else:

            impact_pct = (total_slippage / abs(gross_pnl)) * Decimal("100")

        return {

            "entry_slippage": float(entry_slippage),

            "exit_slippage": float(exit_slippage),

            "total_slippage": float(total_slippage),

            "gross_pnl": float(gross_pnl),

            "slippage_impact_pct": float(impact_pct),

            "entry_details": entry_details,

            "exit_details": exit_details,

        }


# Preset конфигурации

SLIPPAGE_PRESETS = {

    "none": {

        "base_slippage_bps": Decimal("0"),

        "volatility_factor_enabled": False,

        "volume_factor_enabled": False,

    },

    "minimal": {

        "base_slippage_bps": Decimal("1"),

        "volatility_factor_enabled": False,

        "volume_factor_enabled": False,

    },

    "realistic": {

        "base_slippage_bps": Decimal("2"),

        "volatility_factor_enabled": True,

        "volume_factor_enabled": True,

    },

    "high": {

        "base_slippage_bps": Decimal("5"),

        "volatility_factor_enabled": True,

        "volume_factor_enabled": True,

    },

}


def create_slippage_model(preset: str = "realistic") -> SlippageModel:
    """

    Создать SlippageModel на основе preset.


    Args:

        preset: 'none', 'minimal', 'realistic', 'high'


    Returns:

        SlippageModel instance

    """

    if preset not in SLIPPAGE_PRESETS:

        raise ValueError(f"Unknown preset: {preset}. Available: {list(SLIPPAGE_PRESETS.keys())}")

    config = SLIPPAGE_PRESETS[preset]

    return SlippageModel(**config)
