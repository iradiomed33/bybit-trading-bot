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

        # STR-007: Режим входа (instant / retest)

        breakout_entry: str = "instant",

        retest_ttl_bars: int = 3,

        # STR-006: Squeeze → Expansion фильтры

        require_squeeze: bool = True,

        squeeze_percentile_threshold: float = 0.2,  # BB/ATR в нижних 20%

        require_expansion: bool = True,

        expansion_bars: int = 3,  # Рост за последние 3 бара

        require_volume: bool = True,  # ОБЯЗАТЕЛЬНО для DoD

        volume_percentile_threshold: float = 0.8,  # Топ 20%

        volume_ratio_threshold: float = 1.5,  # 1.5x от SMA(volume)

    ):
        """

        Args:

            bb_width_threshold: Макс. ширина BB для "узкого" диапазона

            min_volume_zscore: Мин. z-score объёма для подтверждения

            min_atr_percent_expansion: Минимальный коэффициент расширения ATR%

            breakout_entry: STR-007: Режим входа (instant / retest)

            retest_ttl_bars: STR-007: TTL ожидания ретеста (в барах)

            require_squeeze: STR-006: Требовать squeeze (BB/ATR в нижних percentile)

            squeeze_percentile_threshold: Порог percentile для squeeze (default 0.2)

            require_expansion: STR-006: Требовать expansion (рост BB/ATR)

            expansion_bars: Количество баров для проверки expansion

            require_volume: STR-006: Требовать подтверждение объёмом (ОБЯЗАТЕЛЬНО)

            volume_percentile_threshold: Порог percentile для объёма (default 0.8)

            volume_ratio_threshold: Минимальное отношение volume/SMA (default 1.5)

        """

        super().__init__("Breakout")

        if breakout_entry not in ("instant", "retest"):

            raise ValueError("breakout_entry must be 'instant' or 'retest'")

        self.bb_width_threshold = bb_width_threshold

        self.min_volume_zscore = min_volume_zscore

        self.min_atr_percent_expansion = min_atr_percent_expansion

        # STR-007

        self.breakout_entry = breakout_entry

        self.retest_ttl_bars = retest_ttl_bars

        self._retest_pending = None

        # STR-006

        self.require_squeeze = require_squeeze

        self.squeeze_percentile_threshold = squeeze_percentile_threshold

        self.require_expansion = require_expansion

        self.expansion_bars = expansion_bars

        self.require_volume = require_volume

        self.volume_percentile_threshold = volume_percentile_threshold

        self.volume_ratio_threshold = volume_ratio_threshold

    def generate_signal(

        self, df: pd.DataFrame, features: Dict[str, Any]

    ) -> Optional[Dict[str, Any]]:
        """Генерация сигнала"""

        if not self.is_enabled:

            return None

        latest = df.iloc[-1]

        prev = df.iloc[-2] if len(df) > 1 else latest

        symbol = features.get("symbol", "UNKNOWN")

        current_index = len(df) - 1

        # Проверяем наличие BB

        bb_cols = [col for col in df.columns if "BBU_" in col or "BBL_" in col]

        if not bb_cols:

            logger.warning(f"{self.name}: BB not calculated")

            return None

        # STR-007: Обработка ожидания ретеста (anti "вход на пике")

        if self.breakout_entry == "retest" and self._retest_pending:

            pending = self._retest_pending

            if pending.get("symbol") != symbol:

                self._retest_pending = None

            else:

                ttl_remaining = self.retest_ttl_bars - (current_index - pending["created_index"])

                if ttl_remaining < 0:

                    logger.info(

                        f"[STR-007] {self.name} retest отменён (TTL истёк) | Symbol={symbol}"

                    )

                    self._retest_pending = None

                else:

                    level = pending["level"]

                    direction = pending["direction"]

                    if direction == "long":

                        retest_confirmed = (latest.get("low", latest["close"]) <= level) and (

                            latest["close"] > level

                        )

                    else:

                        retest_confirmed = (latest.get("high", latest["close"]) >= level) and (

                            latest["close"] < level

                        )

                    if not retest_confirmed:

                        return None

                    # STR-006 volume check (mandatory) at entry

                    volume_pctl = latest.get("volume_percentile", 0.0)

                    volume_ratio = latest.get("volume_ratio", 0.0)

                    volume_ok = True

                    if self.require_volume:

                        volume_ok = (volume_pctl == 1.0) or (

                            volume_ratio >= self.volume_ratio_threshold

                        )

                        if not volume_ok:

                            logger.debug(f"[STR-007] {self.name}: volume rejected on retest")

                            return None

                    # Legacy filters on retest entry

                    volume_zscore = latest.get("volume_zscore", 0)

                    if volume_zscore < self.min_volume_zscore:

                        logger.debug(

                            f"{self.name}: Rejected - volume_low (zscore={volume_zscore:.2f})"

                        )

                        return None

                    atr_percent = latest.get("atr_percent", 0)

                    atr_percent_ma = df["atr_percent"].tail(20).mean()

                    threshold = atr_percent_ma * self.min_atr_percent_expansion

                    if atr_percent < (threshold - 1e-9):

                        logger.debug(

                            f"{self.name}: Rejected - vol_not_expanding "

                            f"(atr%={atr_percent:.3f} < median*{self.min_atr_percent_expansion}={threshold:.3f})"

                        )

                        return None

                    spread_percent = features.get("spread_percent", 100)

                    if spread_percent >= 0.5:

                        logger.debug(

                            f"{self.name}: Rejected - spread_too_wide ({spread_percent:.3f}%)"

                        )

                        return None

                    close = latest["close"]

                    atr = latest.get("atr", 0)

                    if direction == "long":

                        stop_loss = level - (1.0 * atr)

                        take_profit = close + (2.5 * atr)

                    else:

                        stop_loss = level + (1.0 * atr)

                        take_profit = close - (2.5 * atr)

                    squeeze_ok = pending.get("squeeze_ok", True)

                    expansion_ok = pending.get("expansion_ok", True)

                    bb_width_pctl = pending.get("bb_width_percentile")

                    atr_pctl = pending.get("atr_percentile")

                    bb_expansion = pending.get("bb_expansion")

                    atr_expansion = pending.get("atr_expansion")

                    reasons = []

                    if self.require_squeeze:

                        reasons.append("squeeze_ok")

                    if self.require_expansion:

                        reasons.append("expansion_ok")

                    if self.require_volume:

                        reasons.append("volume_ok")

                    reasons.append("retest_confirmed")

                    reasons.append("retest_entry")

                    reasons.append(f"breakout_{direction}")

                    values = {

                        "bb_width": latest.get("bb_width", None),

                        "volume_zscore": volume_zscore,

                        "atr_percent": atr_percent,

                        "spread_percent": spread_percent,

                        "squeeze_ok": squeeze_ok,

                        "expansion_ok": expansion_ok,

                        "volume_ok": volume_ok,

                        "bb_width_percentile": bb_width_pctl,

                        "atr_percentile": atr_pctl,

                        "bb_expansion": bb_expansion,

                        "atr_expansion": atr_expansion,

                        "volume_percentile": volume_pctl,

                        "volume_ratio": volume_ratio,

                        "breakout_entry": self.breakout_entry,

                        "retest_level": level,

                        "retest_ttl_remaining": ttl_remaining,

                        "retest_confirmed": True,

                        "retest_pending": False,

                    }

                    self._retest_pending = None

                    return {

                        "signal": direction,

                        "confidence": 0.75,

                        "reasons": reasons,

                        "values": values,

                        "entry_price": close,

                        "stop_loss": stop_loss,

                        "take_profit": take_profit,

                        "reason": (

                            f"Breakout {direction} (retest): level={level:.3f}, "

                            f"volume={volume_zscore:.1f}, atr%={atr_percent:.3f}"

                        ),

                        "metadata": {

                            "bb_width": latest.get("bb_width", None),

                            "volume_zscore": volume_zscore,

                            "atr_percent": atr_percent,

                            "spread_percent": spread_percent,

                            "squeeze_ok": (

                                squeeze_ok

                                if self.require_squeeze

                                or self.require_expansion

                                or self.require_volume

                                else None

                            ),

                            "expansion_ok": (

                                expansion_ok

                                if self.require_squeeze

                                or self.require_expansion

                                or self.require_volume

                                else None

                            ),

                            "volume_ok": (

                                volume_ok

                                if self.require_squeeze

                                or self.require_expansion

                                or self.require_volume

                                else None

                            ),

                        },

                    }

        # STR-006: Проверка squeeze (сжатие волатильности)

        bb_width_pctl = None

        atr_pctl = None

        squeeze_ok = True

        if self.require_squeeze:

            bb_width_pctl = latest.get("bb_width_percentile", 0.0)

            atr_pctl = latest.get("atr_percentile", 0.0)

            squeeze_ok = (bb_width_pctl == 1.0) or (atr_pctl == 1.0)

            if not squeeze_ok:

                logger.debug(f"[STR-006] {self.name}: squeeze rejected")

                return None

        # STR-006: Проверка expansion (расширение волатильности)

        bb_expansion = None

        atr_expansion = None

        expansion_ok = True

        if self.require_expansion:

            bb_expansion = latest.get("bb_expansion", 0.0)

            atr_expansion = latest.get("atr_expansion", 0.0)

            expansion_ok = (bb_expansion == 1.0) or (atr_expansion == 1.0)

            if not expansion_ok:

                logger.debug(f"[STR-006] {self.name}: expansion rejected")

                return None

        # STR-006: Проверка volume (требование подтверждения объёмом)

        volume_pctl = None

        volume_ratio = None

        volume_ok = True

        if self.require_volume:

            volume_pctl = latest.get("volume_percentile", 0.0)

            volume_ratio = latest.get("volume_ratio", 0.0)

            volume_ok = (volume_pctl == 1.0) or (volume_ratio >= self.volume_ratio_threshold)

            if not volume_ok:

                logger.debug(f"[STR-006] {self.name}: volume rejected")

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

                logger.debug(f"{self.name}: Rejected - volume_low (zscore={volume_zscore:.2f})")

                return None

            # 4. Фильтр расширения волатильности (ATR%)

            atr_percent = latest.get("atr_percent", 0)

            atr_percent_ma = df["atr_percent"].tail(20).mean()  # Средний ATR% за 20 свечей

            # Use epsilon for floating point comparison

            threshold = atr_percent_ma * self.min_atr_percent_expansion

            if atr_percent < (threshold - 1e-9):

                logger.debug(

                    f"{self.name}: Rejected - vol_not_expanding "

                    f"(atr%={atr_percent:.3f} < median*{self.min_atr_percent_expansion}={threshold:.3f})"

                )

                return None

            # 5. Фильтр ликвидности (из стакана)

            spread_percent = features.get("spread_percent", 100)

            if spread_percent >= 0.5:  # Спред >= 0.5%

                logger.debug(f"{self.name}: Rejected - spread_too_wide ({spread_percent:.3f}%)")

                return None

            if self.breakout_entry == "retest":

                self._retest_pending = {

                    "direction": "long",

                    "level": bb_upper,

                    "created_index": current_index,

                    "symbol": symbol,

                    "squeeze_ok": squeeze_ok,

                    "expansion_ok": expansion_ok,

                    "bb_width_percentile": bb_width_pctl,

                    "atr_percentile": atr_pctl,

                    "bb_expansion": bb_expansion,

                    "atr_expansion": atr_expansion,

                }

                logger.info(

                    f"[STR-007] {self.name} retest ожидается (LONG) | level={bb_upper:.3f} | Symbol={symbol}"

                )

                return None

            atr = latest.get("atr", 0)

            stop_loss = bb_upper - (1.0 * atr)

            take_profit = close + (2.5 * atr)

            reasons = []

            if self.require_squeeze:

                reasons.append("squeeze_ok")

            if self.require_expansion:

                reasons.append("expansion_ok")

            if self.require_volume:

                reasons.append("volume_ok")

            reasons.append("instant_entry")

            reasons.append("breakout_long")

            values = {

                "bb_width": bb_width,

                "volume_zscore": volume_zscore,

                "atr_percent": atr_percent,

                "spread_percent": spread_percent,

                "squeeze_ok": squeeze_ok,

                "expansion_ok": expansion_ok,

                "volume_ok": volume_ok,

                "bb_width_percentile": bb_width_pctl,

                "atr_percentile": atr_pctl,

                "bb_expansion": bb_expansion,

                "atr_expansion": atr_expansion,

                "volume_percentile": volume_pctl,

                "volume_ratio": volume_ratio,

                "breakout_entry": self.breakout_entry,

                "retest_level": None,

                "retest_ttl_remaining": None,

                "retest_confirmed": False,

                "retest_pending": False,

            }

            return {

                "signal": "long",

                "confidence": 0.75,

                "reasons": reasons,

                "values": values,

                "entry_price": close,

                "stop_loss": stop_loss,

                "take_profit": take_profit,

                "reason": (

                    f"Breakout long: BB width={bb_width:.3f}, "

                    f"volume={volume_zscore:.1f}, atr%={atr_percent:.3f}"

                    + (

                        f" | STR-006: squeeze_ok={squeeze_ok}, expansion_ok={expansion_ok}, volume_ok={volume_ok}"

                        if (self.require_squeeze or self.require_expansion or self.require_volume)

                        else ""

                    )

                ),

                "metadata": {

                    "bb_width": bb_width,

                    "volume_zscore": volume_zscore,

                    "atr_percent": atr_percent,

                    "spread_percent": spread_percent,

                    "squeeze_ok": (

                        squeeze_ok

                        if self.require_squeeze or self.require_expansion or self.require_volume

                        else None

                    ),

                    "expansion_ok": (

                        expansion_ok

                        if self.require_squeeze or self.require_expansion or self.require_volume

                        else None

                    ),

                    "volume_ok": (

                        volume_ok

                        if self.require_squeeze or self.require_expansion or self.require_volume

                        else None

                    ),

                },

            }

        # Пробой вниз

        if prev_close >= prev_bb_lower and close < bb_lower:

            volume_zscore = latest.get("volume_zscore", 0)

            if volume_zscore < self.min_volume_zscore:

                logger.debug(f"{self.name}: Rejected - volume_low (zscore={volume_zscore:.2f})")

                return None

            # Фильтр расширения волатильности

            atr_percent = latest.get("atr_percent", 0)

            atr_percent_ma = df["atr_percent"].tail(20).mean()

            # Use epsilon for floating point comparison

            threshold = atr_percent_ma * self.min_atr_percent_expansion

            if atr_percent < (threshold - 1e-9):

                logger.debug(

                    f"{self.name}: Rejected - vol_not_expanding "

                    f"(atr%={atr_percent:.3f} < median*{self.min_atr_percent_expansion}={threshold:.3f})"

                )

                return None

            spread_percent = features.get("spread_percent", 100)

            if spread_percent >= 0.5:

                logger.debug(f"{self.name}: Rejected - spread_too_wide ({spread_percent:.3f}%)")

                return None

            if self.breakout_entry == "retest":

                self._retest_pending = {

                    "direction": "short",

                    "level": bb_lower,

                    "created_index": current_index,

                    "symbol": symbol,

                    "squeeze_ok": squeeze_ok,

                    "expansion_ok": expansion_ok,

                    "bb_width_percentile": bb_width_pctl,

                    "atr_percentile": atr_pctl,

                    "bb_expansion": bb_expansion,

                    "atr_expansion": atr_expansion,

                }

                logger.info(

                    f"[STR-007] {self.name} retest ожидается (SHORT) | level={bb_lower:.3f} | Symbol={symbol}"

                )

                return None

            atr = latest.get("atr", 0)

            stop_loss = bb_lower + (1.0 * atr)

            take_profit = close - (2.5 * atr)

            # STR-006 metrics for response

            squeeze_ok = True

            expansion_ok = True

            volume_ok = True

            if self.require_squeeze or self.require_expansion or self.require_volume:

                bb_width_pctl = latest.get("bb_width_percentile", 0.0)

                atr_pctl = latest.get("atr_percentile", 0.0)

                bb_expansion = latest.get("bb_expansion", 0.0)

                atr_expansion = latest.get("atr_expansion", 0.0)

                volume_pctl = latest.get("volume_percentile", 0.0)

                volume_ratio = latest.get("volume_ratio", 0.0)

            reasons = []

            if self.require_squeeze:

                reasons.append("squeeze_ok")

            if self.require_expansion:

                reasons.append("expansion_ok")

            if self.require_volume:

                reasons.append("volume_ok")

            reasons.append("instant_entry")

            reasons.append("breakout_short")

            values = {

                "bb_width": bb_width,

                "volume_zscore": volume_zscore,

                "atr_percent": atr_percent,

                "spread_percent": spread_percent,

                "squeeze_ok": squeeze_ok,

                "expansion_ok": expansion_ok,

                "volume_ok": volume_ok,

                "bb_width_percentile": bb_width_pctl,

                "atr_percentile": atr_pctl,

                "bb_expansion": bb_expansion,

                "atr_expansion": atr_expansion,

                "volume_percentile": volume_pctl,

                "volume_ratio": volume_ratio,

                "breakout_entry": self.breakout_entry,

                "retest_level": None,

                "retest_ttl_remaining": None,

                "retest_confirmed": False,

                "retest_pending": False,

            }

            return {

                "signal": "short",

                "confidence": 0.75,

                "reasons": reasons,

                "values": values,

                "entry_price": close,

                "stop_loss": stop_loss,

                "take_profit": take_profit,

                "reason": (

                    f"Breakout short: BB width={bb_width:.3f}, "

                    f"volume={volume_zscore:.1f}, atr%={atr_percent:.3f}"

                    + (

                        f" | STR-006: squeeze_ok={squeeze_ok}, expansion_ok={expansion_ok}, volume_ok={volume_ok}"

                        if (self.require_squeeze or self.require_expansion or self.require_volume)

                        else ""

                    )

                ),

                "metadata": {

                    "bb_width": bb_width,

                    "volume_zscore": volume_zscore,

                    "atr_percent": atr_percent,

                    "spread_percent": spread_percent,

                    "squeeze_ok": (

                        squeeze_ok

                        if self.require_squeeze or self.require_expansion or self.require_volume

                        else None

                    ),

                    "expansion_ok": (

                        expansion_ok

                        if self.require_squeeze or self.require_expansion or self.require_volume

                        else None

                    ),

                    "volume_ok": (

                        volume_ok

                        if self.require_squeeze or self.require_expansion or self.require_volume

                        else None

                    ),

                },

            }

        return None
