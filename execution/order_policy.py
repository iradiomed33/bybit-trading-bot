"""

EXE-001 Order Types и Maker/Taker Politik


Определяет логику выбора типа ордера (Limit vs Market/IOC) 

и параметров (post_only, TTL) в зависимости от стратегии и рыночных условий.


Цель: минимизировать потери на комиссиях, спредах и adverse fills.

"""


from enum import Enum

from typing import Dict, Any, Optional

from dataclasses import dataclass

from decimal import Decimal


class OrderExecType(Enum):

    """Тип исполнения ордера"""

    MAKER = "maker"  # Лимитка, надеемся на пассивное заполнение

    TAKER = "taker"  # Маркет или IOC, активно заполняем

    IOC = "ioc"  # Immediate-or-Cancel (best effort)


class TimeInForce(Enum):

    """Правила времени жизни ордера"""

    GTC = "GTC"  # Good-Till-Cancel (виснет до отмены)

    IOC = "IOC"  # Immediate-Or-Cancel (заполнись или отмени)

    FOK = "FOK"  # Fill-Or-Kill (всё или ничего)

    PostOnly = "PostOnly"  # Только maker, иначе отмени (не допускай taker)


@dataclass
class OrderPolicy:

    """Политика ордера для стратегии"""

    exec_type: OrderExecType

    time_in_force: TimeInForce

    post_only: bool = False  # Принимаем только maker fill

    ttl_seconds: Optional[int] = None  # TTL для лимитки (если задан, отменяем через N сек)

    maker_commission: Decimal = Decimal("0.0002")  # 0.02% для maker

    taker_commission: Decimal = Decimal("0.0004")  # 0.04% для taker

    def expected_commission_rate(self) -> Decimal:
        """Ожидаемая комиссия для расчётов"""

        if self.exec_type == OrderExecType.MAKER:

            return self.maker_commission

        else:

            return self.taker_commission

    def is_maker_intent(self) -> bool:
        """True если стремимся быть maker"""

        return self.exec_type == OrderExecType.MAKER or self.post_only


class OrderPolicySelector:

    """Выбирает политику ордера в зависимости от стратегии и условий"""

    # Политики по умолчанию для каждой стратегии

    DEFAULT_POLICIES = {

        "TrendPullback": {

            "normal": OrderPolicy(

                exec_type=OrderExecType.MAKER,

                time_in_force=TimeInForce.GTC,

                post_only=True,

                ttl_seconds=300,  # 5 минут

            ),

            "high_vol": OrderPolicy(

                exec_type=OrderExecType.TAKER,

                time_in_force=TimeInForce.IOC,

                post_only=False,

                ttl_seconds=None,  # IOC не нужен TTL

            ),

        },

        "Breakout": {

            "normal": OrderPolicy(

                exec_type=OrderExecType.MAKER,

                time_in_force=TimeInForce.PostOnly,

                post_only=True,

                ttl_seconds=180,  # 3 минуты для пробоя

            ),

            "high_vol": OrderPolicy(

                exec_type=OrderExecType.TAKER,

                time_in_force=TimeInForce.FOK,  # Fill-Or-Kill для гарантированного входа

                post_only=False,

                ttl_seconds=None,

            ),

        },

        "MeanReversion": {

            "normal": OrderPolicy(

                exec_type=OrderExecType.MAKER,

                time_in_force=TimeInForce.GTC,

                post_only=True,

                ttl_seconds=600,  # 10 минут для mean reversion

            ),

            "high_vol": OrderPolicy(

                exec_type=OrderExecType.TAKER,

                time_in_force=TimeInForce.IOC,

                post_only=False,

                ttl_seconds=None,

            ),

        },

    }

    @classmethod
    def get_policy(

        cls,

        strategy_name: str,

        regime: str = "normal",

        confidence: float = 0.75,

    ) -> OrderPolicy:
        """

        Выбрать политику ордера для стратегии и режима.


        Args:

            strategy_name: Имя стратегии (TrendPullback, Breakout, MeanReversion)

            regime: Режим рынка (normal, range, trend_up, trend_down, high_vol_event)

            confidence: Уверенность сигнала (0..1)


        Returns:

            OrderPolicy с параметрами ордера

        """

        # Для high_vol_event всегда TAKER (быстрое исполнение)

        if regime == "high_vol_event":

            regime_key = "high_vol"

        else:

            regime_key = "normal"

        # Получаем базовую политику

        if strategy_name not in cls.DEFAULT_POLICIES:

            # Fallback на консервативный maker если стратегия неизвестна

            return OrderPolicy(

                exec_type=OrderExecType.MAKER,

                time_in_force=TimeInForce.GTC,

                post_only=True,

                ttl_seconds=300,

            )

        policy = cls.DEFAULT_POLICIES[strategy_name].get(

            regime_key, cls.DEFAULT_POLICIES[strategy_name]["normal"]

        )

        # Корректируем TTL по уверенности: низкая уверенность → короче TTL

        if policy.ttl_seconds and confidence < 0.65:

            policy.ttl_seconds = max(60, int(policy.ttl_seconds * 0.5))

        return policy

    @classmethod
    def get_order_params(

        cls,

        strategy_name: str,

        regime: str = "normal",

        confidence: float = 0.75,

    ) -> Dict[str, Any]:
        """

        Получить параметры ордера в формате для API.


        Returns:

            Dict с keys: order_type, time_in_force, post_only, ttl_seconds, maker_intent

        """

        policy = cls.get_policy(strategy_name, regime, confidence)

        return {

            "order_type": "Limit" if policy.exec_type == OrderExecType.MAKER else "Market",

            "time_in_force": policy.time_in_force.value,

            "post_only": policy.post_only,

            "ttl_seconds": policy.ttl_seconds,

            "maker_intent": policy.is_maker_intent(),

            "exec_type": policy.exec_type.value,

            "expected_commission": float(policy.expected_commission_rate()),

        }


# Рекомендуемые комиссии по режиму

COMMISSION_RATES = {

    "maker": Decimal("0.0002"),  # 0.02% maker

    "taker": Decimal("0.0004"),  # 0.04% taker (bybit standard)

}
