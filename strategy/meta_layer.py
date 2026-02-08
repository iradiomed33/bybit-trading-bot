"""

Meta Layer: управление стратегиями, режимами рынка, арбитраж сигналов.


Компоненты:

1. Regime Switcher - определяет режим рынка

2. Signal Arbitration - приоритизирует конфликтующие сигналы

3. No-Trade Zones - блокирует торговлю при плохих условиях

4. Multi-timeframe confluence - проверяет согласованность на разных ТФ

"""


from typing import List, Dict, Any, Optional

import pandas as pd

from strategy.base_strategy import BaseStrategy

from data.timeframe_cache import TimeframeCache

from logger import setup_logger

from signal_logger import get_signal_logger


logger = setup_logger(__name__)

signal_logger = get_signal_logger()


class RegimeSwitcher:

    """Определение режима рынка на основе multi-factor анализа


    META-002: Расширенная детекция режимов по набору признаков:

    1. ADX - сила тренда

    2. BB width / ATR - волатильность и её тренд

    3. HTF EMA направление - тренд/контртренд

    4. Высокая волатильность - специальный режим с cooldown

    """

    @staticmethod
    def detect_regime(

        df: pd.DataFrame,

        adx_trend_threshold: float = 25.0,

        adx_range_threshold: float = 20.0,

        bb_width_range_threshold: float = 0.03,

        atr_slope_threshold: float = 0.5,

        high_vol_atr_threshold: float = 3.0,

    ) -> str:
        """

        Определить текущий режим рынка по multi-factor модели.


        META-002: Режимы:

        - "trend_up": ADX > threshold, EMA20 > EMA50, BB расширяется вверх

        - "trend_down": ADX > threshold, EMA20 < EMA50, BB расширяется вниз

        - "range": Low ADX, узкие/сужающиеся BB, ATR стабилен

        - "high_vol_event": ATR% > 3% (включает cooldown, снижение риска)

        - "unknown": не определено


        Args:

            adx_trend_threshold: Порог ADX для сильного тренда (по умолчанию 25)

            adx_range_threshold: Порог ADX для range режима (по умолчанию 20)

            bb_width_range_threshold: Порог ширины BB для range (по умолчанию 0.03)

            atr_slope_threshold: Порог наклона ATR (по умолчанию 0.5)

            high_vol_atr_threshold: Порог ATR% для high_vol_event (по умолчанию 3.0)


        Returns:

            "trend_up" | "trend_down" | "range" | "high_vol_event" | "unknown"

        """

        if df is None or df.empty:

            logger.warning("RegimeSwitcher: Empty dataframe")

            return "unknown"

        latest = df.iloc[-1]

        # Компонент 1: ADX

        adx = latest.get("adx", latest.get("ADX_14", 0))

        # Компонент 2: BB width и ATR для волатильности

        bb_width = latest.get("bb_width", 1.0)

        bb_width_pct_change = latest.get("bb_width_pct_change", 0.0)

        atr_slope = latest.get("atr_slope", 0.0)

        atr_percent = latest.get("atr_percent", 0.0)

        # Компонент 3: HTF EMA направление

        ema_20 = latest.get("ema_20", 0)

        ema_50 = latest.get("ema_50", 0)

        close = latest.get("close", 0)

        if ema_20 == 0 or ema_50 == 0:

            logger.warning("RegimeSwitcher: Missing EMA values")

            return "unknown"

        # META-002: HIGH_VOL_EVENT - highest priority (включает cooldown)

        if atr_percent > high_vol_atr_threshold:

            logger.info(

                f"RegimeSwitcher: HIGH_VOL_EVENT detected (ATR%={atr_percent:.2f}% > {high_vol_atr_threshold}%) "

                f"| ADX={adx:.1f} | Cooldown enabled"

            )

            return "high_vol_event"

        # Старый vol_regime фильтр (для обратной совместимости)

        vol_regime = latest.get("vol_regime", 0)

        if vol_regime == 1 and atr_percent > 2.0:

            logger.debug(f"RegimeSwitcher: high_vol from vol_regime (ATR%={atr_percent:.2f}%)")

            return "high_vol_event"

        # META-002: RANGE режим - все три условия

        is_low_adx = adx < adx_range_threshold

        is_bb_narrow_or_contracting = (bb_width < bb_width_range_threshold) or (

            bb_width_pct_change < 0

        )

        is_atr_stable = atr_slope < atr_slope_threshold

        if is_low_adx and is_bb_narrow_or_contracting and is_atr_stable:

            logger.debug(

                f"RegimeSwitcher: RANGE detected | ADX={adx:.1f} < {adx_range_threshold} | "

                f"BB_width={bb_width:.4f} (change={bb_width_pct_change:.2%}) | ATR_slope={atr_slope:.2f}"

            )

            return "range"

        # META-002: TREND - сильный ADX + согласованность EMA и направления BB

        is_strong_adx = adx > adx_trend_threshold

        is_ema_up = ema_20 > ema_50

        is_ema_down = ema_20 < ema_50

        is_bb_expanding = bb_width_pct_change > 0

        close_above_ema50 = close > ema_50

        close_below_ema50 = close < ema_50

        if is_strong_adx:

            # TREND_UP: EMA20 > EMA50, цена > EMA50, BB расширяется

            if is_ema_up and close_above_ema50 and is_bb_expanding:

                logger.debug(

                    f"RegimeSwitcher: TREND_UP detected | ADX={adx:.1f} | EMA20={ema_20:.0f} > EMA50={ema_50:.0f} | "

                    f"close={close:.0f} > EMA50 | BB_expanding={bb_width_pct_change:.2%}"

                )

                return "trend_up"

            # TREND_DOWN: EMA20 < EMA50, цена < EMA50, BB расширяется

            if is_ema_down and close_below_ema50 and is_bb_expanding:

                logger.debug(

                    f"RegimeSwitcher: TREND_DOWN detected | ADX={adx:.1f} | EMA20={ema_20:.0f} < EMA50={ema_50:.0f} | "

                    f"close={close:.0f} < EMA50 | BB_expanding={bb_width_pct_change:.2%}"

                )

                return "trend_down"

            # Тренд но без полной согласованности - возвращаем по направлению EMA

            if is_ema_up:

                logger.debug(

                    f"RegimeSwitcher: TREND_UP (partial) | ADX={adx:.1f} (strong) | EMA20={ema_20:.0f} > EMA50={ema_50:.0f}"

                )

                return "trend_up"

            else:

                logger.debug(

                    f"RegimeSwitcher: TREND_DOWN (partial) | ADX={adx:.1f} (strong) | EMA20={ema_20:.0f} < EMA50={ema_50:.0f}"

                )

                return "trend_down"

        # Неопределённый режим (средний ADX, не соответствует criteria)

        logger.debug(

            f"RegimeSwitcher: UNKNOWN regime | ADX={adx:.1f} (mid-range) | "

            f"EMA20={ema_20:.0f} vs EMA50={ema_50:.0f} | BB_width={bb_width:.4f}"

        )

        return "unknown"


class SignalArbitrator:

    """Арбитраж конфликтующих сигналов"""

    @staticmethod
    def arbitrate_signals(signals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """

        Выбрать лучший сигнал из списка.


        Правила:

        1. Если только один - берём его

        2. Если несколько в одну сторону - берём с макс. confidence

        3. Если противоречащие - блокируем все


        Args:

            signals: Список сигналов от разных стратегий


        Returns:

            Выбранный сигнал или None

        """

        if not signals:

            return None

        if len(signals) == 1:

            return signals[0]

        # Группируем по направлению

        long_signals = [s for s in signals if s["signal"] == "long"]

        short_signals = [s for s in signals if s["signal"] == "short"]

        close_signals = [s for s in signals if s["signal"] == "close"]

        # Конфликт: есть и long и short

        if long_signals and short_signals:

            logger.warning("Signal conflict: both long and short signals present - blocking all")

            return None

        # Выбираем лучший из одного направления

        if long_signals:

            best = max(long_signals, key=lambda s: s["confidence"])

            logger.info(

                f"Selected LONG signal: {best['reason']} (confidence={best['confidence']:.2f})"

            )

            return best

        if short_signals:

            best = max(short_signals, key=lambda s: s["confidence"])

            logger.info(

                f"Selected SHORT signal: {best['reason']} (confidence={best['confidence']:.2f})"

            )

            return best

        if close_signals:

            return close_signals[0]

        return None


class NoTradeZones:

    """Проверка условий для запрета торговли"""

    @staticmethod
    def is_trading_allowed(

        df: pd.DataFrame, features: Dict[str, Any], error_count: int = 0

    ) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """

        Проверить, разрешена ли торговля.


        Returns:

            (allowed: bool, reason: str or None, details: dict or None)

        """

        # Для проверки качества данных используем последнюю ЗАКРЫТУЮ свечу (iloc[-2]),
        # а не текущую формирующуюся (iloc[-1]), т.к. формирующаяся свеча может иметь
        # очень малое тело (doji) и нормальные тени, что ведет к ложным срабатываниям
        if len(df) < 2:
            # Если меньше 2 свечей, используем последнюю (нет выбора)
            candle_for_quality_check = df.iloc[-1]
        else:
            # Используем последнюю закрытую свечу
            candle_for_quality_check = df.iloc[-2]
        
        latest = df.iloc[-1]  # Для других проверок (волатильность) используем текущую

        # 1. Аномалия данных

        has_anomaly = candle_for_quality_check.get("has_anomaly", 0)

        if has_anomaly == 1:
            # Собираем детали о том, какие именно аномалии сработали
            anomaly_details = {}
            if candle_for_quality_check.get("anomaly_wick", 0) == 1:
                anomaly_details["anomaly_wick"] = 1
            if candle_for_quality_check.get("anomaly_low_volume", 0) == 1:
                anomaly_details["anomaly_low_volume"] = 1
            if candle_for_quality_check.get("anomaly_gap", 0) == 1:
                anomaly_details["anomaly_gap"] = 1
            
            return False, "Data anomaly detected", anomaly_details

        # 2. Плохая ликвидность (широкий спред)

        # На тестовой сети спред может быть очень большим из-за малого объёма

        # Поэтому проверяем только экстремальные значения (> 10%)

        spread_percent = features.get("spread_percent", 0)

        if spread_percent > 10.0:  # Спред > 10% - это явно ошибка данных или запредельный спред

            return False, f"Excessive spread: {spread_percent:.2f}%", {"spread_percent": spread_percent}

        # 3. Низкая глубина стакана

        # На тестовой сети стакан может быть очень дисбалансирован из-за малого объема торговли

        # Поэтому отключаем эту проверку для testnet или проверяем только критические значения (> 0.99)

        depth_imbalance = features.get("depth_imbalance", 0)

        # Закомментировано: слишком строго для тестовой сети

        # if abs(depth_imbalance) > 0.99:

        #     return False, f"Orderbook imbalance: {depth_imbalance:.2f}"

        # 4. Серия ошибок (передаётся извне)

        if error_count > 5:  # Смягчено с 3

            return False, f"Too many errors: {error_count}", {"error_count": error_count}

        # 5. Экстремальная волатильность

        vol_regime = latest.get("vol_regime", 0)

        atr_percent = latest.get("atr_percent", 0)

        if vol_regime == 1 and atr_percent > 10.0:  # ATR > 10% (смягчено с 5%)

            return False, f"Extreme volatility: ATR={atr_percent:.2f}%", {"vol_regime": vol_regime, "atr_percent": atr_percent}

        return True, None, None


class MetaLayer:

    """Центральный мета-слой для управления стратегиями"""

    def __init__(

        self,

        strategies: List[BaseStrategy],

        use_mtf: bool = True,

        mtf_score_threshold: float = 0.6,

    ):
        """

        Args:

            strategies: Список стратегий

            use_mtf: Использовать multi-timeframe confluence checks

            mtf_score_threshold: Порог прохождения MTF-скоринга (0..1)

        """

        self.strategies = strategies

        self.regime_switcher = RegimeSwitcher()

        self.arbitrator = SignalArbitrator()

        self.no_trade_zones = NoTradeZones()

        self.use_mtf = use_mtf

        self.mtf_score_threshold = mtf_score_threshold

        self.timeframe_cache = TimeframeCache() if use_mtf else None

        logger.info(

            f"MetaLayer initialized with {len(strategies)} strategies "

            f"(MTF: {use_mtf}, mtf_score_threshold={mtf_score_threshold})"

        )

    def get_signal(

        self, df: pd.DataFrame, features: Dict[str, Any], error_count: int = 0

    ) -> Optional[Dict[str, Any]]:
        """

        Получить финальный торговый сигнал.


        Args:

            df: DataFrame с данными и признаками

            features: Дополнительные признаки

            error_count: Количество недавних ошибок


        Returns:

            Финальный сигнал или None

        """

        # 1. No-trade zones

        trading_allowed, block_reason, block_details = self.no_trade_zones.is_trading_allowed(

            df, features, error_count

        )

        if not trading_allowed:
            
            # Объединяем reason и детали аномалий в values
            values = {
                "reason": block_reason,
                "error_count": error_count,
            }
            
            # Добавляем детали аномалий, если они есть
            if block_details:
                values.update(block_details)

            signal_logger.log_signal_rejected(

                strategy_name="MetaLayer",

                symbol=features.get("symbol", "UNKNOWN"),

                direction="N/A",

                confidence=0.0,

                reasons=["no_trade_zone"],

                values=values,

            )

            return None

        # 2. Определяем режим рынка

        regime = self.regime_switcher.detect_regime(df)

        # Логируем только при смене режима

        # 3. Включаем/выключаем стратегии по режиму

        self._adjust_strategies_by_regime(regime)

        # 4. Собираем сигналы от всех активных стратегий

        signals = []

        active_strategies_info = []

        for strategy in self.strategies:

            if strategy.is_enabled:

                active_strategies_info.append(strategy.name)

                signal = strategy.generate_signal(df, features)

                if signal:

                    normalized = self._normalize_signal(signal, strategy.name)

                    signals.append(normalized)

                    logger.info(

                        f"Signal from {strategy.name}: {normalized['signal']} "

                        f"(conf={normalized['confidence']:.2f})"

                    )

        # Если ни одна стратегия не дала сигнала - логируем отладку

        if not signals:

            latest = df.iloc[-1]

            signal_logger.log_debug_info(

                category="strategy_analysis",

                regime=regime,

                active_strategies=active_strategies_info,

                market_conditions={

                    "adx": round(latest.get("adx", latest.get("ADX_14", 0)), 2),

                    "close": round(latest.get("close", 0), 2),

                    "volume_z": round(latest.get("volume_zscore", 0), 2),

                    "atr": round(latest.get("atr", 0), 4),

                },

            )

        # 5. Арбитраж сигналов

        final_signal = self.arbitrator.arbitrate_signals(signals)

        if final_signal is None and signals:

            signal_logger.log_signal_rejected(

                strategy_name="MetaLayer",

                symbol=features.get("symbol", "UNKNOWN"),

                direction="CONFLICT",

                confidence=0.0,

                reasons=["meta_conflict"],

                values={

                    "signals": [

                        {

                            "strategy": s.get("strategy"),

                            "signal": s.get("signal"),

                            "confidence": s.get("confidence"),

                            "reasons": s.get("reasons", []),

                        }

                        for s in signals

                    ]

                },

            )

        if final_signal:

            final_signal["regime"] = regime

            # 6. Multi-timeframe confluence check (опционально)

            if self.use_mtf and self.timeframe_cache:

                # Получаем данные из кэша

                df_1m = self.timeframe_cache.get_latest("1")

                df_5m = self.timeframe_cache.get_latest("5")

                df_15m = self.timeframe_cache.get_latest("15")

                mtf_result = self.timeframe_cache.check_confluence(

                    final_signal.get("signal"), df_1m, df_5m, df_15m

                )

                mtf_score = mtf_result.get("score", 0.0)

                mtf_details = mtf_result.get("details", {})

                mtf_components = mtf_result.get("components", {})

                score_passed = mtf_score >= self.mtf_score_threshold

                # Логируем мета-фильтр как отдельный фильтр с порогом

                signal_logger.log_filter_check(

                    filter_name="mtf_confluence",

                    symbol=features.get("symbol", "UNKNOWN"),

                    passed=score_passed,

                    value=round(mtf_score, 3),

                    threshold=self.mtf_score_threshold,

                    direction=final_signal.get("signal"),

                    components=mtf_components,

                )

                # Обогащаем сигнал информацией о скоринге MTF

                values = final_signal.get("values") or {}

                values["mtf_score"] = mtf_score

                values["mtf_score_threshold"] = self.mtf_score_threshold

                values["mtf_details"] = mtf_details

                final_signal["values"] = values

                reasons = final_signal.get("reasons") or []

                reasons.append("mtf_score")

                final_signal["reasons"] = reasons

                if not score_passed:

                    signal_logger.log_signal_rejected(

                        strategy_name="MetaLayer",

                        symbol=features.get("symbol", "UNKNOWN"),

                        direction=final_signal.get("signal", "unknown"),

                        confidence=final_signal.get("confidence", 0.0),

                        reasons=["mtf_score_below_threshold"],

                        values=final_signal.get("values", {}),

                        source_strategy=final_signal.get("strategy"),

                    )

                    return None

                final_signal["mtf_confirmed"] = True

                final_signal["mtf_score"] = mtf_score

                final_signal["mtf_score_threshold"] = self.mtf_score_threshold

        return final_signal

    @staticmethod
    def _normalize_signal(signal: Dict[str, Any], strategy_name: str) -> Dict[str, Any]:

        reasons = signal.get("reasons")

        if reasons is None:

            legacy_reason = signal.get("reason")

            reasons = [legacy_reason] if legacy_reason else []

        values = signal.get("values")

        if values is None:

            values = signal.get("metadata") or {}

        normalized = dict(signal)

        normalized["strategy"] = strategy_name

        normalized["reasons"] = list(reasons) if reasons else []

        normalized["values"] = values

        normalized["reason"] = signal.get("reason") or "; ".join(normalized["reasons"])

        return normalized

    def update_timeframe_data(self, timeframe: str, candle: Dict[str, Any]) -> None:
        """

        Обновить данные таймфрейма в кэше.


        Args:

            timeframe: Таймфрейм (1, 5, 15, 60, 240, D)

            candle: Данные свечи

        """

        if self.use_mtf and self.timeframe_cache:

            self.timeframe_cache.add_candle(timeframe, candle)

    def _adjust_strategies_by_regime(self, regime: str):
        """Включить/выключить стратегии в зависимости от режима"""

        for strategy in self.strategies:

            # TrendPullback - только в трендах

            if strategy.name == "TrendPullback":

                if regime in ["trend_up", "trend_down"]:

                    strategy.enable()

                else:

                    strategy.disable()

            # Breakout - лучше работает в диапазонах

            elif strategy.name == "Breakout":

                if regime == "range":

                    strategy.enable()

                else:

                    strategy.disable()

            # MeanReversion - ТОЛЬКО при низкой волатильности

            elif strategy.name == "MeanReversion":

                if regime == "range":  # И vol_regime == -1 проверяется внутри стратегии

                    strategy.enable()

                else:

                    strategy.disable()
