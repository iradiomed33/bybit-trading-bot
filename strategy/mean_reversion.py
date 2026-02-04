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
    ):
        """
        Args:
            vwap_distance_threshold: Мин. отклонение от VWAP (%)
            rsi_oversold: RSI уровень перепроданности
            rsi_overbought: RSI уровень перекупленности
        """
        super().__init__("MeanReversion")
        self.vwap_distance_threshold = vwap_distance_threshold
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought

    def generate_signal(
        self, df: pd.DataFrame, features: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Генерация сигнала"""
        if not self.is_enabled:
            return None

        latest = df.iloc[-1]

        # 1. КРИТИЧНО: только при низкой волатильности
        vol_regime = latest.get("vol_regime", 0)
        if vol_regime != -1:  # -1 = low volatility
            return None

        # 2. Проверка отклонения от VWAP
        vwap_distance = latest.get("vwap_distance", 0)
        rsi = latest.get("rsi", 50)
        close = latest["close"]
        vwap = latest.get("vwap", close)

        # Long: цена сильно ниже VWAP и RSI перепродан
        if vwap_distance < -self.vwap_distance_threshold and rsi < self.rsi_oversold:
            atr = latest.get("atr", 0)
            stop_loss = close - (1.0 * atr)  # Tight stop
            take_profit = vwap  # Цель = возврат к VWAP

            return {
                "signal": "long",
                "confidence": 0.6,  # Ниже чем у трендовых
                "entry_price": close,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "reason": f"Mean reversion long: VWAP dist={vwap_distance:.2f}%, RSI={rsi:.1f}",
                "metadata": {
                    "vwap_distance": vwap_distance,
                    "rsi": rsi,
                    "vol_regime": vol_regime,
                },
            }

        # Short: цена сильно выше VWAP и RSI перекуплен
        if vwap_distance > self.vwap_distance_threshold and rsi > self.rsi_overbought:
            atr = latest.get("atr", 0)
            stop_loss = close + (1.0 * atr)
            take_profit = vwap

            return {
                "signal": "short",
                "confidence": 0.6,
                "entry_price": close,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "reason": f"Mean reversion short: VWAP dist={vwap_distance:.2f}%, RSI={rsi:.1f}",
                "metadata": {
                    "vwap_distance": vwap_distance,
                    "rsi": rsi,
                    "vol_regime": vol_regime,
                },
            }

        return None
