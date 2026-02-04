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
from signal_logger import get_signal_logger

logger = setup_logger(__name__)
signal_logger = get_signal_logger()


class TrendPullbackStrategy(BaseStrategy):
    """Стратегия входа на откате в тренде"""

    def __init__(self, min_adx: float = 15.0, pullback_percent: float = 0.5):
        """
        Args:
            min_adx: Минимальный ADX для тренда (снижено с 25 для тестнета)
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
        symbol = features.get('symbol', 'UNKNOWN')

        # Проверяем наличие нужных признаков
        required_cols = ["close", "ema_20", "ema_50", "ADX_14", "atr", "volume_zscore"]
        if not all(col in df.columns for col in required_cols):
            logger.warning(f"{self.name}: Missing required features")
            return None

        # 1. Проверка тренда (ADX)
        adx = latest.get("ADX_14", 0)
        adx_passed = adx >= self.min_adx
        signal_logger.log_filter_check(
            filter_name="ADX (Trend Strength)",
            symbol=symbol,
            passed=adx_passed,
            value=adx,
            threshold=self.min_adx
        )
        if not adx_passed:
            return None  # Нет тренда

        ema_20 = latest["ema_20"]
        ema_50 = latest["ema_50"]
        close = latest["close"]

        # Определяем направление тренда
        is_uptrend = ema_20 > ema_50
        is_downtrend = ema_20 < ema_50
        trend_passed = is_uptrend or is_downtrend
        
        signal_logger.log_filter_check(
            filter_name="EMA Alignment (Trend Direction)",
            symbol=symbol,
            passed=trend_passed,
            value={
                "ema_20": round(ema_20, 2),
                "ema_50": round(ema_50, 2),
                "is_uptrend": is_uptrend,
                "is_downtrend": is_downtrend
            }
        )
        if not trend_passed:
            return None

        # 2. Проверка отката (ATR)
        atr = latest.get("atr", 0)
        if atr == 0:
            signal_logger.log_filter_check(
                filter_name="ATR (Volatility)",
                symbol=symbol,
                passed=False,
                value=atr,
                threshold=">0"
            )
            return None

        # Long: цена откатилась к EMA20 или чуть ниже
        if is_uptrend:
            distance_to_ema = (close - ema_20) / atr
            pullback_passed = -0.5 <= distance_to_ema <= 0.2
            
            signal_logger.log_filter_check(
                filter_name="Pullback to EMA (Entry Zone)",
                symbol=symbol,
                passed=pullback_passed,
                value=round(distance_to_ema, 2),
                threshold="[-0.5, 0.2] ATRs"
            )
            
            if pullback_passed:
                # 3. Подтверждение: объём увеличился
                volume_zscore = latest.get("volume_zscore", 0)
                volume_passed = volume_zscore > 1.0
                
                signal_logger.log_filter_check(
                    filter_name="Volume Confirmation",
                    symbol=symbol,
                    passed=volume_passed,
                    value=round(volume_zscore, 2),
                    threshold=">1.0 (std devs)"
                )
                
                if volume_passed:
                    # 4. Структура: не в аномалии
                    has_anomaly = latest.get("has_anomaly", 0)
                    anomaly_passed = has_anomaly == 0
                    
                    signal_logger.log_filter_check(
                        filter_name="Anomaly Detection",
                        symbol=symbol,
                        passed=anomaly_passed,
                        value=has_anomaly,
                        threshold="0 (no anomaly)"
                    )
                    
                    if anomaly_passed:
                        # ✅ ВСЕ УСЛОВИЯ ПРОЙДЕНЫ - ГЕНЕРИРУЕМ СИГНАЛ
                        stop_loss = ema_20 - (1.5 * atr)
                        take_profit = close + (3 * atr)
                        confidence = min(adx / 50.0, 1.0)

                        signal_logger.log_signal_generated(
                            strategy_name=self.name,
                            symbol=symbol,
                            direction="BUY",
                            confidence=confidence,
                            price=close,
                            adx=adx,
                            ema_ratio=round(ema_20 / ema_50, 4),
                            pullback_depth=round(distance_to_ema, 2),
                            volume_z_score=round(volume_zscore, 2)
                        )

                        return {
                            "signal": "long",
                            "confidence": confidence,
                            "entry_price": close,
                            "stop_loss": stop_loss,
                            "take_profit": take_profit,
                            "reason": f"Uptrend pullback: ADX={adx:.1f}, EMA20/EMA50={ema_20/ema_50:.4f}",
                            "strategy": self.name,
                            "metadata": {
                                "adx": adx,
                                "distance_to_ema": distance_to_ema,
                                "volume_zscore": volume_zscore,
                            },
                        }

        # Short: цена откатилась к EMA20 сверху
        if is_downtrend:
            distance_to_ema = (ema_20 - close) / atr
            pullback_passed = -0.5 <= distance_to_ema <= 0.2
            
            signal_logger.log_filter_check(
                filter_name="Pullback to EMA (Entry Zone)",
                symbol=symbol,
                passed=pullback_passed,
                value=round(distance_to_ema, 2),
                threshold="[-0.5, 0.2] ATRs"
            )
            
            if pullback_passed:
                volume_zscore = latest.get("volume_zscore", 0)
                volume_passed = volume_zscore > 1.0
                
                signal_logger.log_filter_check(
                    filter_name="Volume Confirmation",
                    symbol=symbol,
                    passed=volume_passed,
                    value=round(volume_zscore, 2),
                    threshold=">1.0 (std devs)"
                )
                
                if volume_passed:
                    has_anomaly = latest.get("has_anomaly", 0)
                    anomaly_passed = has_anomaly == 0
                    
                    signal_logger.log_filter_check(
                        filter_name="Anomaly Detection",
                        symbol=symbol,
                        passed=anomaly_passed,
                        value=has_anomaly,
                        threshold="0 (no anomaly)"
                    )
                    
                    if anomaly_passed:
                        # ✅ ВСЕ УСЛОВИЯ ПРОЙДЕНЫ - ГЕНЕРИРУЕМ СИГНАЛ
                        stop_loss = ema_20 + (1.5 * atr)
                        take_profit = close - (3 * atr)
                        confidence = min(adx / 50.0, 1.0)

                        signal_logger.log_signal_generated(
                            strategy_name=self.name,
                            symbol=symbol,
                            direction="SELL",
                            confidence=confidence,
                            price=close,
                            adx=adx,
                            ema_ratio=round(ema_20 / ema_50, 4),
                            pullback_depth=round(distance_to_ema, 2),
                            volume_z_score=round(volume_zscore, 2)
                        )

                        return {
                            "signal": "short",
                            "confidence": confidence,
                            "entry_price": close,
                            "stop_loss": stop_loss,
                            "take_profit": take_profit,
                            "reason": f"Downtrend pullback: ADX={adx:.1f}, EMA20/EMA50={ema_20/ema_50:.4f}",
                            "strategy": self.name,
                            "metadata": {
                                "adx": adx,
                                "distance_to_ema": distance_to_ema,
                                "volume_zscore": volume_zscore,
                            },
                        }

        return None
