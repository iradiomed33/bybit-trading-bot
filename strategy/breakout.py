"""
Breakout + Liquidity Filter Strategy

Логика:
1. Определяем диапазон (range) - BB width узкий
2. Ждём пробоя границ диапазона
3. Подтверждение: объём, ликвидность в стакане приемлемая
4. Вход в направлении пробоя
"""

from typing import Dict, Any, Optional
import pandas as pd
from strategy.base_strategy import BaseStrategy
from logger import setup_logger

logger = setup_logger(__name__)


class BreakoutStrategy(BaseStrategy):
    """Стратегия пробоя диапазона с фильтром ликвидности"""

    def __init__(
        self,
        bb_width_threshold: float = 0.02,
        min_volume_zscore: float = 1.5,
        min_atr_percent_expansion: float = 1.2,  # ATR% должен быть > медианы на 20%
    ):
        """
        Args:
            bb_width_threshold: Макс. ширина BB для "узкого" диапазона
            min_volume_zscore: Мин. z-score объёма для подтверждения
            min_atr_percent_expansion: Минимальный коэффициент расширения ATR%
        """
        super().__init__("Breakout")
        self.bb_width_threshold = bb_width_threshold
        self.min_volume_zscore = min_volume_zscore
        self.min_atr_percent_expansion = min_atr_percent_expansion

    def generate_signal(
        self, df: pd.DataFrame, features: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Генерация сигнала"""
        if not self.is_enabled:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        # Проверяем наличие BB
        bb_cols = [col for col in df.columns if "BBU_" in col or "BBL_" in col]
        if not bb_cols:
            logger.warning(f"{self.name}: BB not calculated")
            return None

        # 1. Проверка узкого диапазона
        bb_width = latest.get("bb_width", 1.0)
        if bb_width > self.bb_width_threshold:
            logger.debug(f"{self.name}: Rejected - BB width too wide ({bb_width:.3f})")
            return None  # Диапазон слишком широкий

        # 2. Проверка пробоя
        close = latest["close"]
        prev_close = prev["close"]

        # Находим колонки BB
        bb_upper_col = [col for col in df.columns if "BBU_" in col][0]
        bb_lower_col = [col for col in df.columns if "BBL_" in col][0]

        bb_upper = latest[bb_upper_col]
        bb_lower = latest[bb_lower_col]
        prev_bb_upper = prev[bb_upper_col]
        prev_bb_lower = prev[bb_lower_col]

        # Пробой вверх
        if prev_close <= prev_bb_upper and close > bb_upper:
            # 3. Подтверждение объёмом
            volume_zscore = latest.get("volume_zscore", 0)
            if volume_zscore < self.min_volume_zscore:
                logger.debug(
                    f"{self.name}: Rejected - volume_low (zscore={volume_zscore:.2f})"
                )
                return None

            # 4. Фильтр расширения волатильности (ATR%)
            atr_percent = latest.get("atr_percent", 0)
            atr_percent_ma = df["atr_percent"].tail(20).mean()  # Средний ATR% за 20 свечей
            
            if atr_percent < (atr_percent_ma * self.min_atr_percent_expansion):
                logger.debug(
                    f"{self.name}: Rejected - vol_not_expanding "
                    f"(atr%={atr_percent:.3f} < median*{self.min_atr_percent_expansion}={atr_percent_ma * self.min_atr_percent_expansion:.3f})"
                )
                return None

            # 5. Фильтр ликвидности (из стакана)
            spread_percent = features.get("spread_percent", 100)
            if spread_percent >= 0.5:  # Спред >= 0.5%
                logger.debug(
                    f"{self.name}: Rejected - spread_too_wide ({spread_percent:.3f}%)"
                )
                return None

            atr = latest.get("atr", 0)
            stop_loss = bb_upper - (1.0 * atr)
            take_profit = close + (2.5 * atr)

            return {
                "signal": "long",
                "confidence": 0.75,
                "entry_price": close,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "reason": (
                    f"Breakout long: BB width={bb_width:.3f}, "
                    f"volume={volume_zscore:.1f}, atr%={atr_percent:.3f}"
                ),
                "metadata": {
                    "bb_width": bb_width,
                    "volume_zscore": volume_zscore,
                    "atr_percent": atr_percent,
                    "spread_percent": spread_percent,
                },
            }

        # Пробой вниз
        if prev_close >= prev_bb_lower and close < bb_lower:
            volume_zscore = latest.get("volume_zscore", 0)
            if volume_zscore < self.min_volume_zscore:
                logger.debug(
                    f"{self.name}: Rejected - volume_low (zscore={volume_zscore:.2f})"
                )
                return None

            # Фильтр расширения волатильности
            atr_percent = latest.get("atr_percent", 0)
            atr_percent_ma = df["atr_percent"].tail(20).mean()
            
            if atr_percent < (atr_percent_ma * self.min_atr_percent_expansion):
                logger.debug(
                    f"{self.name}: Rejected - vol_not_expanding "
                    f"(atr%={atr_percent:.3f} < median*{self.min_atr_percent_expansion}={atr_percent_ma * self.min_atr_percent_expansion:.3f})"
                )
                return None

            spread_percent = features.get("spread_percent", 100)
            if spread_percent >= 0.5:
                logger.debug(
                    f"{self.name}: Rejected - spread_too_wide ({spread_percent:.3f}%)"
                )
                return None

            atr = latest.get("atr", 0)
            stop_loss = bb_lower + (1.0 * atr)
            take_profit = close - (2.5 * atr)

            return {
                "signal": "short",
                "confidence": 0.75,
                "entry_price": close,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "reason": (
                    f"Breakout short: BB width={bb_width:.3f}, "
                    f"volume={volume_zscore:.1f}, atr%={atr_percent:.3f}"
                ),
                "metadata": {
                    "bb_width": bb_width,
                    "volume_zscore": volume_zscore,
                    "atr_percent": atr_percent,
                    "spread_percent": spread_percent,
                },
            }

        return None
