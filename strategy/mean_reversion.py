"""
Mean Reversion Strategy (только при низкой волатильности)

Логика:
1. Проверяем режим волатильности (должен быть LOW)
2. Цена отклонилась от VWAP/SMA
3. RSI в зоне перепроданности/перекупленности
4. Вход на возврат к среднему с tight stop
"""

from typing import Dict, Any, Optional
import pandas as pd
from strategy.base_strategy import BaseStrategy
from logger import setup_logger

logger = setup_logger(__name__)


class MeanReversionStrategy(BaseStrategy):
    """Стратегия возврата к среднему (только при низкой волатильности)"""

    def __init__(
        self,
        vwap_distance_threshold: float = 2.0,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        max_adx_for_entry: float = 25.0,  # Запрет входа при ADX > 25 (сильный тренд)
    ):
        """
        Args:
            vwap_distance_threshold: Мин. отклонение от VWAP (%)
            rsi_oversold: RSI уровень перепроданности
            rsi_overbought: RSI уровень перекупленности
            max_adx_for_entry: Максимальный ADX для допуска входа (защита от тренда)
        """
        super().__init__("MeanReversion")
        self.vwap_distance_threshold = vwap_distance_threshold
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.max_adx_for_entry = max_adx_for_entry

    def generate_signal(
        self, df: pd.DataFrame, features: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Генерация сигнала"""
        if not self.is_enabled:
            return None

        latest = df.iloc[-1]

        # 1. Фильтр волатильности: только low-vol или range режим
        vol_regime = latest.get("vol_regime", 0)
        if vol_regime != -1:  # -1 = low volatility
            logger.debug(
                f"{self.name}: Rejected - vol_regime={vol_regime} (only -1/low allowed)"
            )
            return None

        # 2. Фильтр тренда: запрет на вход против сильного тренда (ADX > 25)
        adx = latest.get("adx", latest.get("ADX_14", 0))  # Fallback compatibility
        if adx > self.max_adx_for_entry:
            logger.debug(
                f"{self.name}: Rejected - trend_too_strong (ADX={adx:.2f} > {self.max_adx_for_entry})"
            )
            return None

        # 3. Проверка направления EMA (не входим сильно против тренда)
        ema_20 = latest.get("ema_20", 0)
        ema_50 = latest.get("ema_50", 0)
        close = latest["close"]

        # 4. Проверка отклонения от VWAP
        vwap_distance = latest.get("vwap_distance", 0)
        rsi = latest.get("rsi", 50)
        vwap = latest.get("vwap", close)

        # Long: цена сильно ниже VWAP, RSI перепродан, и не слишком сильный downtrend
        if vwap_distance < -self.vwap_distance_threshold and rsi < self.rsi_oversold:
            # Дополнительный фильтр: не входим если цена слишком далеко ниже EMA50
            if close < ema_50 * 0.95:  # Цена более чем на 5% ниже EMA50 = сильный downtrend
                logger.debug(
                    f"{self.name}: Rejected - price_too_far_below_ema50 "
                    f"(close={close:.2f} < ema50*0.95={ema_50 * 0.95:.2f})"
                )
                return None

            atr = latest.get("atr", 0)
            stop_loss = close - (1.0 * atr)  # Tight stop
            take_profit = vwap  # Цель = возврат к VWAP

            return {
                "signal": "long",
                "confidence": 0.6,  # Ниже чем у трендовых
                "entry_price": close,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "reason": (
                    f"Mean reversion long: VWAP dist={vwap_distance:.2f}%, RSI={rsi:.1f}, "
                    f"ADX={adx:.2f}"
                ),
                "metadata": {
                    "vwap_distance": vwap_distance,
                    "rsi": rsi,
                    "adx": adx,
                    "vol_regime": vol_regime,
                },
            }

        # Short: цена сильно выше VWAP, RSI перекуплен, и не слишком сильный uptrend
        if vwap_distance > self.vwap_distance_threshold and rsi > self.rsi_overbought:
            # Дополнительный фильтр: не входим если цена слишком далеко выше EMA50
            if close > ema_50 * 1.05:  # Цена более чем на 5% выше EMA50 = сильный uptrend
                logger.debug(
                    f"{self.name}: Rejected - price_too_far_above_ema50 "
                    f"(close={close:.2f} > ema50*1.05={ema_50 * 1.05:.2f})"
                )
                return None

            atr = latest.get("atr", 0)
            stop_loss = close + (1.0 * atr)
            take_profit = vwap

            return {
                "signal": "short",
                "confidence": 0.6,
                "entry_price": close,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "reason": (
                    f"Mean reversion short: VWAP dist={vwap_distance:.2f}%, RSI={rsi:.1f}, "
                    f"ADX={adx:.2f}"
                ),
                "metadata": {
                    "vwap_distance": vwap_distance,
                    "rsi": rsi,
                    "adx": adx,
                    "vol_regime": vol_regime,
                },
            }

        return None
