"""
Trend-Following Pullback Strategy

Логика:
1. Определяем направление тренда (EMA, ADX)
2. Ждём отката к уровню поддержки/сопротивления
3. Подтверждение: объём, структура, momentum
4. Вход по тренду с tight stop
"""

from typing import Dict, Any, Optional
import pandas as pd
from strategy.base_strategy import BaseStrategy
from logger import setup_logger

logger = setup_logger(__name__)


class TrendPullbackStrategy(BaseStrategy):
    """Стратегия входа на откате в тренде"""

    def __init__(self, min_adx: float = 25.0, pullback_percent: float = 0.5):
        """
        Args:
            min_adx: Минимальный ADX для тренда
            pullback_percent: Глубина отката (% от ATR)
        """
        super().__init__("TrendPullback")
        self.min_adx = min_adx
        self.pullback_percent = pullback_percent

    def generate_signal(
        self, df: pd.DataFrame, features: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Генерация сигнала"""
        if not self.is_enabled:
            return None

        # Берём последнюю строку
        latest = df.iloc[-1]

        # Проверяем наличие нужных признаков
        required_cols = ["close", "ema_20", "ema_50", "ADX_14", "atr", "volume_zscore"]
        if not all(col in df.columns for col in required_cols):
            logger.warning(f"{self.name}: Missing required features")
            return None

        # 1. Проверка тренда
        adx = latest.get("ADX_14", 0)
        if adx < self.min_adx:
            return None  # Нет тренда

        ema_20 = latest["ema_20"]
        ema_50 = latest["ema_50"]
        close = latest["close"]

        # Uptrend: EMA20 > EMA50, цена выше EMA20
        is_uptrend = ema_20 > ema_50
        # Downtrend: EMA20 < EMA50, цена ниже EMA20
        is_downtrend = ema_20 < ema_50

        if not (is_uptrend or is_downtrend):
            return None

        # 2. Проверка отката
        atr = latest.get("atr", 0)
        if atr == 0:
            return None

        # Long: цена откатилась к EMA20 или чуть ниже
        if is_uptrend:
            distance_to_ema = (close - ema_20) / atr
            # Откат: цена близко к EMA20 (в пределах 0.5 ATR)
            if -0.5 <= distance_to_ema <= 0.2:
                # 3. Подтверждение: объём увеличился
                volume_zscore = latest.get("volume_zscore", 0)
                if volume_zscore > 1.0:  # Объём выше среднего
                    # 4. Структура: не в аномалии
                    has_anomaly = latest.get("has_anomaly", 0)
                    if has_anomaly == 0:
                        # Генерируем LONG сигнал
                        stop_loss = ema_20 - (1.5 * atr)  # Стоп под EMA20
                        take_profit = close + (3 * atr)  # R:R = 1:2

                        return {
                            "signal": "long",
                            "confidence": min(adx / 50.0, 1.0),  # Уверенность от ADX
                            "entry_price": close,
                            "stop_loss": stop_loss,
                            "take_profit": take_profit,
                            "reason": f"Trend pullback long: ADX={adx:.1f}, pullback to EMA20",
                            "metadata": {
                                "adx": adx,
                                "distance_to_ema": distance_to_ema,
                                "volume_zscore": volume_zscore,
                            },
                        }

        # Short: цена откатилась к EMA20 сверху
        if is_downtrend:
            distance_to_ema = (ema_20 - close) / atr
            if -0.5 <= distance_to_ema <= 0.2:
                volume_zscore = latest.get("volume_zscore", 0)
                if volume_zscore > 1.0:
                    has_anomaly = latest.get("has_anomaly", 0)
                    if has_anomaly == 0:
                        stop_loss = ema_20 + (1.5 * atr)
                        take_profit = close - (3 * atr)

                        return {
                            "signal": "short",
                            "confidence": min(adx / 50.0, 1.0),
                            "entry_price": close,
                            "stop_loss": stop_loss,
                            "take_profit": take_profit,
                            "reason": f"Trend pullback short: ADX={adx:.1f}, pullback to EMA20",
                            "metadata": {
                                "adx": adx,
                                "distance_to_ema": distance_to_ema,
                                "volume_zscore": volume_zscore,
                            },
                        }

        return None
