"""

Multi-timeframe cache для хранения данных разных таймфреймов.


Используется для фильтрации сигналов на основе согласованности разных ТФ.

"""


import pandas as pd

from typing import Dict, Optional, Any

from logger import setup_logger


logger = setup_logger(__name__)


class TimeframeCache:

    """Кэш данных для разных таймфреймов"""

    def __init__(self):
        """Инициализация кэша"""

        self.cache: Dict[str, pd.DataFrame] = {}

        logger.info("TimeframeCache initialized")

    def add_candle(self, timeframe: str, candle: Dict) -> None:
        """

        Добавить свечу в кэш для конкретного таймфрейма.


        Args:

            timeframe: Таймфрейм (1, 5, 15, 60, 240, D и т.д.)

            candle: Данные свечи (open, high, low, close, volume и т.д.)

        """

        if timeframe not in self.cache:

            self.cache[timeframe] = pd.DataFrame()

        df = self.cache[timeframe]

        # Если свеча уже существует, обновляем её (в случае обновлений)

        if len(df) > 0 and df.iloc[-1]["timestamp"] == candle.get("timestamp"):

            df.iloc[-1] = candle

        else:

            # Добавляем новую свечу

            df = pd.concat([df, pd.DataFrame([candle])], ignore_index=True)

        # Ограничиваем размер кэша (последние 500 свечей)

        if len(df) > 500:

            df = df.iloc[-500:]

        self.cache[timeframe] = df

    def get_latest(self, timeframe: str) -> Optional[Dict]:
        """

        Получить последнюю свечу для таймфрейма.


        Args:

            timeframe: Таймфрейм


        Returns:

            Данные последней свечи или None

        """

        if timeframe not in self.cache or len(self.cache[timeframe]) == 0:

            return None

        return self.cache[timeframe].iloc[-1].to_dict()

    def get_dataframe(self, timeframe: str) -> Optional[pd.DataFrame]:
        """

        Получить весь DataFrame для таймфрейма.


        Args:

            timeframe: Таймфрейм


        Returns:

            DataFrame или None

        """

        return self.cache.get(timeframe)

    def check_confluence(

        self,

        signal_direction: Optional[str],

        timeframe_1m: Optional[Dict],

        timeframe_5m: Optional[Dict],

        timeframe_15m: Optional[Dict],

    ) -> Dict[str, Any]:
        """

        Рассчитать скоринговую оценку согласованности разных ТФ.


        Весовая модель (сумма ≤ 1.0):

        - 1m тренд против/за сигнал: вес 0.5

        - 5m тренд (если есть): вес 0.3 (при отсутствии даём нейтральный вес 0.15)

        - 15m волатильность-фильтр: вес 0.2 (при отсутствии нейтральный вес 0.1)


        Args:

            signal_direction: "long" или "short" для сопоставления тренда

            timeframe_1m: Данные 1m свечи

            timeframe_5m: Данные 5m свечи (опционально)

            timeframe_15m: Данные 15m свечи (опционально)


        Returns:

            dict с итоговым score и детализацией компонентов

        """

        breakdown: Dict[str, Any] = {}

        if not timeframe_1m:

            logger.debug("MTF Check: No 1m data available")

            return {"score": 0.0, "components": {}, "details": breakdown}

        def trend_label(close_value: float, ema_value: float) -> str:

            if close_value > ema_value:

                return "up"

            if close_value < ema_value:

                return "down"

            return "flat"

        def trend_score(trend: str, direction: Optional[str], weight: float) -> float:

            if direction is None:

                return weight * 0.5

            if direction == "long":

                if trend == "up":

                    return weight

                if trend == "flat":

                    return weight * 0.5

                return 0.0

            if direction == "short":

                if trend == "down":

                    return weight

                if trend == "flat":

                    return weight * 0.5

                return 0.0

            return 0.0

        # 1m trend component

        close_1m = timeframe_1m.get("close", 0)

        ema_20_1m = timeframe_1m.get("ema_20", close_1m)

        trend_1m = trend_label(close_1m, ema_20_1m)

        score_1m = trend_score(trend_1m, signal_direction, 0.5)

        breakdown["trend_1m"] = {"trend": trend_1m, "close": close_1m, "ema": ema_20_1m}

        logger.debug(

            f"MTF Check: 1m trend={trend_1m.upper()} (close={close_1m:.2f}, ema={ema_20_1m:.2f}) | score={score_1m:.2f}"

        )

        # 5m trend component (optional)

        score_5m = 0.0

        trend_5m = None

        if timeframe_5m:

            close_5m = timeframe_5m.get("close", 0)

            ema_20_5m = timeframe_5m.get("ema_20", close_5m)

            trend_5m = trend_label(close_5m, ema_20_5m)

            score_5m = trend_score(trend_5m, signal_direction, 0.3)

            logger.debug(f"MTF Check: 5m trend={trend_5m.upper()} | score={score_5m:.2f}")

            breakdown["trend_5m"] = {"trend": trend_5m, "close": close_5m, "ema": ema_20_5m}

        else:

            score_5m = 0.15  # нейтральный вклад при отсутствии данных

            breakdown["trend_5m"] = {"trend": None, "close": None, "ema": None}

            logger.debug("MTF Check: No 5m data (neutral score applied)")

        # 15m volatility component (optional)

        score_vol = 0.0

        vol_regime = None

        atr_percent = None

        if timeframe_15m:

            vol_regime = timeframe_15m.get("vol_regime", 0)

            atr_percent = timeframe_15m.get("atr_percent", 0)

            if vol_regime == 1 and atr_percent is not None and atr_percent > 3.0:

                score_vol = 0.0

                logger.debug(

                    f"MTF Check: 15m HIGH VOL (atr%={atr_percent:.2f}) | score={score_vol:.2f}"

                )

            else:

                score_vol = 0.2

                logger.debug(

                    f"MTF Check: 15m volatility acceptable (atr%={atr_percent}) | score={score_vol:.2f}"

                )

        else:

            score_vol = 0.1  # нейтральный вклад при отсутствии данных

            logger.debug("MTF Check: No 15m data (neutral volatility score applied)")

        breakdown["vol_15m"] = {"vol_regime": vol_regime, "atr_percent": atr_percent}

        total_score = min(1.0, round(score_1m + score_5m + score_vol, 3))

        breakdown["components"] = {

            "trend_1m": round(score_1m, 3),

            "trend_5m": round(score_5m, 3),

            "volatility_15m": round(score_vol, 3),

        }

        logger.debug(f"MTF Check: total_score={total_score:.3f} | direction={signal_direction}")

        return {"score": total_score, "components": breakdown["components"], "details": breakdown}

    def clear(self) -> None:
        """Очистить весь кэш"""

        self.cache.clear()

        logger.info("Timeframe cache cleared")
