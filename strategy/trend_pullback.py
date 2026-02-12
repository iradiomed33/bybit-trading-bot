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

    def __init__(

        self,

        min_adx: float = 15.0,

        pullback_percent: float = 0.5,

        # STR-002: Liquidation wick filter config

        enable_liquidation_filter: bool = True,

        liquidation_cooldown_bars: int = 3,

        liquidation_atr_multiplier: float = 2.5,

        liquidation_wick_ratio: float = 0.7,

        liquidation_volume_pctl: float = 95.0,

        # STR-003: Entry confirmation mode

        entry_mode: str = "confirm_close",

        limit_ttl_bars: int = 3,

        # Configurable entry zone and volume thresholds

        entry_zone_atr_low: float = -0.5,

        entry_zone_atr_high: float = 0.2,

        volume_z_threshold: float = 1.0,

    ):
        """

        Args:

            min_adx: Минимальный ADX для тренда (снижено с 25 для тестнета)

            pullback_percent: Глубина отката (% от ATR)

            enable_liquidation_filter: STR-002: Включить фильтр ликвидационных свечей

            liquidation_cooldown_bars: STR-002: Cooldown период после ликвидационной свечи (N баров)

            liquidation_atr_multiplier: STR-002: Множитель ATR для определения большого диапазона

            liquidation_wick_ratio: STR-002: Порог отношения тени к телу

            liquidation_volume_pctl: STR-002: Перцентиль объёма для всплеска

            entry_mode: STR-003: Режим входа - 'immediate' (старый), 'confirm_close' (подтверждение закрытием), 'limit_retest' (лимитка на уровне)

            limit_ttl_bars: STR-003: TTL для лимитных заявок (в барах)

            entry_zone_atr_low: Нижняя граница entry zone (в ATRs от EMA)

            entry_zone_atr_high: Верхняя граница entry zone (в ATRs от EMA)

            volume_z_threshold: Минимальный z-score объёма для подтверждения

        """

        super().__init__("TrendPullback")

        self.min_adx = min_adx

        self.pullback_percent = pullback_percent

        # STR-002: Liquidation filter config

        self.enable_liquidation_filter = enable_liquidation_filter

        self.liquidation_cooldown_bars = liquidation_cooldown_bars

        self.liquidation_atr_multiplier = liquidation_atr_multiplier

        self.liquidation_wick_ratio = liquidation_wick_ratio

        self.liquidation_volume_pctl = liquidation_volume_pctl

        # STR-003: Entry confirmation config

        if entry_mode not in ["immediate", "confirm_close", "limit_retest"]:

            raise ValueError(

                f"Invalid entry_mode: {entry_mode}. Must be 'immediate', 'confirm_close', or 'limit_retest'"

            )

        self.entry_mode = entry_mode

        self.limit_ttl_bars = limit_ttl_bars

        # Configurable entry zone and volume thresholds

        self.entry_zone_atr_low = entry_zone_atr_low

        self.entry_zone_atr_high = entry_zone_atr_high

        self.volume_z_threshold = volume_z_threshold

    def generate_signal(

        self, df: pd.DataFrame, features: Dict[str, Any]

    ) -> Optional[Dict[str, Any]]:
        """Генерация сигнала"""

        if not self.is_enabled:

            return None

        # Берём последнюю строку

        latest = df.iloc[-1]

        symbol = features.get("symbol", "UNKNOWN")

        # Проверяем наличие нужных признаков (используем канонические имена)

        required_cols = ["close", "ema_20", "ema_50", "adx", "atr", "volume_zscore"]

        if not all(col in df.columns for col in required_cols):

            logger.warning(

                f"{self.name}: Missing required features: {[c for c in required_cols if c not in df.columns]}"

            )

            return None

        # 1. Проверка тренда (ADX) - используем каноническое имя "adx"

        adx = latest.get("adx", 0)

        adx_passed = adx >= self.min_adx

        signal_logger.log_filter_check(

            filter_name="ADX (Trend Strength)",

            symbol=symbol,

            passed=adx_passed,

            value=adx,

            threshold=self.min_adx,

        )

        if not adx_passed:

            return None  # Нет тренда

        # STR-002: Проверка фильтра ликвидационных свечей

        if self.enable_liquidation_filter:

            liquidation_detected = self._check_liquidation_cooldown(df, symbol)

            if liquidation_detected:

                return None  # Cooldown период после ликвидационной свечи

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

                "is_downtrend": is_downtrend,

            },

        )

        if not trend_passed:

            return None

        # 2. Проверка отката (ATR)

        atr = latest.get("atr", 0)

        if pd.isna(atr) or atr <= 0:

            signal_logger.log_filter_check(

                filter_name="ATR (Volatility)",

                symbol=symbol,

                passed=False,

                value=atr if not pd.isna(atr) else "NaN",

                threshold=">0",

            )

            return None

        # Long: цена откатилась к EMA20 или чуть ниже

        if is_uptrend:

            distance_to_ema = (close - ema_20) / atr

            pullback_passed = self.entry_zone_atr_low <= distance_to_ema <= self.entry_zone_atr_high

            threshold_str = f"[{self.entry_zone_atr_low}, {self.entry_zone_atr_high}] ATRs"

            signal_logger.log_filter_check(

                filter_name="Pullback to EMA (Entry Zone)",

                symbol=symbol,

                passed=pullback_passed,

                value=round(distance_to_ema, 2),

                threshold=threshold_str,

            )

            if pullback_passed:

                # 3. Подтверждение: объём увеличился

                volume_zscore = latest.get("volume_zscore", 0)

                volume_passed = volume_zscore > self.volume_z_threshold

                signal_logger.log_filter_check(

                    filter_name="Volume Confirmation",

                    symbol=symbol,

                    passed=volume_passed,

                    value=round(volume_zscore, 2),

                    threshold=f">{self.volume_z_threshold} (std devs)",

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

                        threshold="0 (no anomaly)",

                    )

                    if anomaly_passed:

                        # STR-003: Проверка подтверждения входа

                        entry_confirmed, confirmation_details = self._check_entry_confirmation(

                            df, symbol, is_long=True, ema_level=ema_20

                        )

                        signal_logger.log_filter_check(

                            filter_name=f"Entry Confirmation (STR-003: {self.entry_mode})",

                            symbol=symbol,

                            passed=entry_confirmed,

                            value=confirmation_details,

                            threshold="Rejection pattern or limit setup",

                        )

                        if not entry_confirmed:

                            logger.info(

                                "[STR-003] Signal rejected: no_entry_confirmation | "

                                f"Symbol={symbol} | Mode={self.entry_mode} | Details={confirmation_details}"

                            )

                            return None

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

                            volume_z_score=round(volume_zscore, 2),

                        )

                        reasons = [

                            "trend_adx_ok",

                            "ema_alignment_ok",

                            "pullback_zone_ok",

                            "volume_confirmed",

                            "no_anomaly",

                        ]

                        values = {

                            "adx": round(adx, 2),

                            "ema_20": round(ema_20, 2),

                            "ema_50": round(ema_50, 2),

                            "ema_ratio": round(ema_20 / ema_50, 4),

                            "distance_to_ema_atr": round(distance_to_ema, 4),

                            "volume_zscore": round(volume_zscore, 2),

                            "atr": round(atr, 4),

                            "close": round(close, 2),

                        }

                        # STR-003: Add confirmation details to signal

                        signal_data = {

                            "signal": "long",

                            "confidence": confidence,

                            "entry_price": close,

                            "stop_loss": stop_loss,

                            "take_profit": take_profit,

                            "atr": atr,  # STR-001: Явно передаем ATR для volatility sizing

                            "stop_distance": abs(

                                close - stop_loss

                            ),  # STR-001 DoD: stop_distance > 0

                            "reasons": reasons,

                            "values": values,

                            "reason": "; ".join(reasons),

                            "strategy": self.name,

                            "metadata": values,

                            "entry_mode": self.entry_mode,  # STR-003

                            "confirmation": confirmation_details,  # STR-003

                        }

                        # STR-003: Add limit order details if in limit_retest mode

                        if self.entry_mode == "limit_retest":

                            signal_data["limit_order"] = True

                            signal_data["target_price"] = confirmation_details["target_price"]

                            signal_data["ttl_bars"] = self.limit_ttl_bars

                        return signal_data

        # Short: цена откатилась к EMA20 сверху

        if is_downtrend:

            distance_to_ema = (ema_20 - close) / atr

            pullback_passed = self.entry_zone_atr_low <= distance_to_ema <= self.entry_zone_atr_high

            threshold_str = f"[{self.entry_zone_atr_low}, {self.entry_zone_atr_high}] ATRs"

            signal_logger.log_filter_check(

                filter_name="Pullback to EMA (Entry Zone)",

                symbol=symbol,

                passed=pullback_passed,

                value=round(distance_to_ema, 2),

                threshold=threshold_str,

            )

            if pullback_passed:

                volume_zscore = latest.get("volume_zscore", 0)

                volume_passed = volume_zscore > self.volume_z_threshold

                signal_logger.log_filter_check(

                    filter_name="Volume Confirmation",

                    symbol=symbol,

                    passed=volume_passed,

                    value=round(volume_zscore, 2),

                    threshold=f">{self.volume_z_threshold} (std devs)",

                )

                if volume_passed:

                    has_anomaly = latest.get("has_anomaly", 0)

                    anomaly_passed = has_anomaly == 0

                    signal_logger.log_filter_check(

                        filter_name="Anomaly Detection",

                        symbol=symbol,

                        passed=anomaly_passed,

                        value=has_anomaly,

                        threshold="0 (no anomaly)",

                    )

                    if anomaly_passed:

                        # STR-003: Проверка подтверждения входа

                        entry_confirmed, confirmation_details = self._check_entry_confirmation(

                            df, symbol, is_long=False, ema_level=ema_20

                        )

                        signal_logger.log_filter_check(

                            filter_name=f"Entry Confirmation (STR-003: {self.entry_mode})",

                            symbol=symbol,

                            passed=entry_confirmed,

                            value=confirmation_details,

                            threshold="Rejection pattern or limit setup",

                        )

                        if not entry_confirmed:

                            logger.info(

                                "[STR-003] Signal rejected: no_entry_confirmation | "

                                f"Symbol={symbol} | Mode={self.entry_mode} | Details={confirmation_details}"

                            )

                            return None

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

                            volume_z_score=round(volume_zscore, 2),

                        )

                        reasons = [

                            "trend_adx_ok",

                            "ema_alignment_ok",

                            "pullback_zone_ok",

                            "volume_confirmed",

                            "no_anomaly",

                        ]

                        values = {

                            "adx": round(adx, 2),

                            "ema_20": round(ema_20, 2),

                            "ema_50": round(ema_50, 2),

                            "ema_ratio": round(ema_20 / ema_50, 4),

                            "distance_to_ema_atr": round(distance_to_ema, 4),

                            "volume_zscore": round(volume_zscore, 2),

                            "atr": round(atr, 4),

                            "close": round(close, 2),

                        }

                        # STR-003: Add confirmation details to signal

                        signal_data = {

                            "signal": "short",

                            "confidence": confidence,

                            "entry_price": close,

                            "stop_loss": stop_loss,

                            "take_profit": take_profit,

                            "atr": atr,  # STR-001: Явно передаем ATR для volatility sizing

                            "stop_distance": abs(

                                stop_loss - close

                            ),  # STR-001 DoD: stop_distance > 0

                            "reasons": reasons,

                            "values": values,

                            "reason": "; ".join(reasons),

                            "strategy": self.name,

                            "metadata": values,

                            "entry_mode": self.entry_mode,  # STR-003

                            "confirmation": confirmation_details,  # STR-003

                        }

                        # STR-003: Add limit order details if in limit_retest mode

                        if self.entry_mode == "limit_retest":

                            signal_data["limit_order"] = True

                            signal_data["target_price"] = confirmation_details["target_price"]

                            signal_data["ttl_bars"] = self.limit_ttl_bars

                        return signal_data

        return None

    def _check_entry_confirmation(

        self, df: pd.DataFrame, symbol: str, is_long: bool, ema_level: float

    ):
        """

        STR-003: Проверка подтверждения входа


        Args:

            df: DataFrame с данными

            symbol: Символ

            is_long: True для LONG, False для SHORT

            ema_level: Уровень EMA для проверки


        Returns:

            (confirmed: bool, details: dict)

        """

        if self.entry_mode == "immediate":

            # Старая логика: вход сразу при касании уровня

            return True, {"mode": "immediate", "confirmed": True}

        if len(df) < 2:

            # Недостаточно данных для проверки подтверждения

            return False, {

                "mode": self.entry_mode,

                "confirmed": False,

                "reason": "insufficient_data",

            }

        current = df.iloc[-1]

        previous = df.iloc[-2]

        current_close = current["close"]

        prev_close = previous["close"]

        if self.entry_mode == "confirm_close":

            # LONG: предыдущая свеча закрылась ниже EMA, текущая - выше (rejection)

            # SHORT: предыдущая свеча закрылась выше EMA, текущая - ниже (rejection)

            if is_long:

                prev_below = prev_close < ema_level

                current_above = current_close > ema_level

                confirmed = prev_below and current_above

                details = {

                    "mode": "confirm_close",

                    "confirmed": confirmed,

                    "direction": "LONG",

                    "prev_close": round(prev_close, 2),

                    "current_close": round(current_close, 2),

                    "ema_level": round(ema_level, 2),

                    "prev_below_ema": prev_below,

                    "current_above_ema": current_above,

                }

            else:  # SHORT

                prev_above = prev_close > ema_level

                current_below = current_close < ema_level

                confirmed = prev_above and current_below

                details = {

                    "mode": "confirm_close",

                    "confirmed": confirmed,

                    "direction": "SHORT",

                    "prev_close": round(prev_close, 2),

                    "current_close": round(current_close, 2),

                    "ema_level": round(ema_level, 2),

                    "prev_above_ema": prev_above,

                    "current_below_ema": current_below,

                }

            return confirmed, details

        elif self.entry_mode == "limit_retest":

            # Режим лимитки: генерируем сигнал для лимитной заявки на уровне EMA

            # Execution layer должен поставить лимитку и отслеживать TTL

            details = {

                "mode": "limit_retest",

                "confirmed": True,  # Всегда подтверждаем для генерации лимитки

                "limit_order": True,

                "target_price": round(ema_level, 2),

                "ttl_bars": self.limit_ttl_bars,

                "current_close": round(current_close, 2),

            }

            return True, details

        # Неизвестный режим (не должно происходить из-за валидации в __init__)

        return False, {"mode": self.entry_mode, "confirmed": False, "reason": "unknown_mode"}

    def _check_liquidation_cooldown(self, df: pd.DataFrame, symbol: str) -> bool:
        """

        STR-002: Проверяет наличие ликвидационных свечей в последних N барах.


        Args:

            df: DataFrame с данными

            symbol: Символ для логирования


        Returns:

            True если обнаружена ликвидационная свеча в cooldown периоде

        """

        if "liquidation_wick" not in df.columns:

            # Если колонка отсутствует, фильтр не применяется

            return False

        # Проверяем последние N баров (включая текущий)

        lookback = min(self.liquidation_cooldown_bars, len(df))

        recent_bars = df.iloc[-lookback:]

        # Есть ли ликвидационная свеча в этом диапазоне?

        liquidation_count = recent_bars["liquidation_wick"].sum()

        if liquidation_count > 0:

            # Находим индекс последней ликвидационной свечи

            liq_indices = recent_bars[recent_bars["liquidation_wick"] == 1].index

            last_liq_idx = liq_indices[-1]

            bars_since_liq = len(df) - (df.index.get_loc(last_liq_idx) + 1)

            # Получаем данные о свече для логирования

            liq_candle = df.loc[last_liq_idx]

            candle_range_atr = liq_candle.get("candle_range_atr", 0)

            wick_ratio = liq_candle.get("wick_ratio", 0)

            signal_logger.log_filter_check(

                filter_name="Liquidation Wick Cooldown (STR-002)",

                symbol=symbol,

                passed=False,

                value={

                    "bars_since_liquidation": bars_since_liq,

                    "cooldown_bars": self.liquidation_cooldown_bars,

                    "candle_range_atr": round(candle_range_atr, 2),

                    "wick_ratio": round(wick_ratio, 2),

                },

                threshold=f"Cooldown={self.liquidation_cooldown_bars} bars",

            )

            # DoD: Логируем rejection с причиной "liquidation_wick_filter"

            logger.warning(

                "[STR-002] Signal rejected: liquidation_wick_filter | "

                f"Symbol={symbol} | Bars since liquidation={bars_since_liq}/{self.liquidation_cooldown_bars} | "

                f"Candle range={candle_range_atr:.2f}x ATR | Wick ratio={wick_ratio:.2f}"

            )

            return True

        # Нет ликвидационных свечей в cooldown периоде

        signal_logger.log_filter_check(

            filter_name="Liquidation Wick Cooldown (STR-002)",

            symbol=symbol,

            passed=True,

            value="No liquidation wicks detected",

            threshold=f"Last {self.liquidation_cooldown_bars} bars",

        )

        return False
