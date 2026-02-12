"""

Meta Layer: управление стратегиями, режимами рынка, арбитраж сигналов.


Компоненты:

1. Regime Switcher - определяет режим рынка

2. Signal Arbitration - приоритизирует конфликтующие сигналы

3. No-Trade Zones - блокирует торговлю при плохих условиях

4. Multi-timeframe confluence - проверяет согласованность на разных ТФ

"""


from typing import List, Dict, Any, Optional
import json

import pandas as pd

from strategy.base_strategy import BaseStrategy

from data.timeframe_cache import TimeframeCache
from strategy.regime_scorer import RegimeScorer

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


class WeightedStrategyRouter:
    """
    Task 2: Weighted Strategy Router
    
    Computes weighted scores for all strategy candidates based on:
    - Raw strategy confidence
    - Strategy weight (based on regime scores)
    - MTF multiplier (optional)
    
    Returns the highest-scoring candidate and logs all candidates with reasons.
    """
    
    def __init__(self, weights_config: Optional[Dict[str, Any]] = None):
        """
        Args:
            weights_config: Configuration for strategy weights
                {
                    "TrendPullback": {
                        "base": 1.0,
                        "regime_multipliers": {
                            "trend": 1.5,
                            "range": 0.5,
                            "high_volatility": 0.3,
                            "choppy": 0.2
                        }
                    },
                    ...
                }
        """
        self.weights_config = weights_config or self._get_default_weights()
        logger.info(f"WeightedStrategyRouter initialized with weights config")
    
    def _get_default_weights(self) -> Dict[str, Any]:
        """Default strategy weights based on regime"""
        return {
            "TrendPullback": {
                "base": 1.0,
                "regime_multipliers": {
                    "trend": 1.5,           # Favored in trend
                    "range": 0.5,           # Disfavored in range
                    "high_volatility": 0.7, # Moderate in high vol
                    "choppy": 0.3,          # Disfavored in chop
                    "neutral": 1.0
                }
            },
            "Breakout": {
                "base": 1.0,
                "regime_multipliers": {
                    "trend": 1.3,           # Good in trend (far from EMA)
                    "range": 1.4,           # Very good in range breakouts
                    "high_volatility": 0.5, # Risky in high vol
                    "choppy": 0.2,          # Very bad in choppy
                    "neutral": 1.0
                }
            },
            "MeanReversion": {
                "base": 1.0,
                "regime_multipliers": {
                    "trend": 0.3,           # Disfavored in trend
                    "range": 1.6,           # Strongly favored in range
                    "high_volatility": 0.4, # Risky in high vol
                    "choppy": 0.8,          # Moderate in choppy
                    "neutral": 1.0
                }
            }
        }
    
    def route_signals(
        self,
        candidates: List[Dict[str, Any]],
        regime_scores: Dict[str, float],
        regime: str,
        symbol: str,
        mtf_score: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Route signals using weighted scoring.
        
        Args:
            candidates: List of signal dicts from strategies
            regime_scores: Dict with trend_score, range_score, etc.
            regime: Dominant regime string
            symbol: Trading symbol
            mtf_score: Optional MTF confluence score
            
        Returns:
            {
                "selected": Optional[Dict],  # Best signal or None
                "all_candidates": List[Dict],  # All evaluated candidates
                "rejection_summary": Dict  # Counts of rejection reasons
            }
        """
        if not candidates:
            return {
                "selected": None,
                "all_candidates": [],
                "rejection_summary": {}
            }
        
        # Evaluate and score all candidates
        evaluated = []
        rejection_reasons = {}
        
        for candidate in candidates:
            strategy_name = candidate.get("strategy", "Unknown")
            raw_confidence = candidate.get("confidence", 0.0)
            direction = candidate.get("signal", "")
            
            # Calculate strategy weight
            strategy_weight = self._calculate_strategy_weight(
                strategy_name,
                regime_scores,
                regime
            )
            
            # Calculate MTF multiplier (1.0 if not available)
            mtf_multiplier = 1.0
            if mtf_score is not None:
                mtf_multiplier = 0.5 + (mtf_score * 0.5)  # Range: 0.5-1.0
            
            # Calculate final score
            final_score = raw_confidence * strategy_weight * mtf_multiplier
            
            # Add scoring metadata to candidate
            candidate["_scoring"] = {
                "raw_confidence": round(raw_confidence, 3),
                "strategy_weight": round(strategy_weight, 3),
                "mtf_multiplier": round(mtf_multiplier, 3),
                "final_score": round(final_score, 3)
            }
            
            evaluated.append(candidate)
            
            logger.debug(
                f"Candidate {strategy_name} {direction}: "
                f"raw_conf={raw_confidence:.3f}, weight={strategy_weight:.3f}, "
                f"mtf_mult={mtf_multiplier:.3f} → final={final_score:.3f}"
            )
        
        # Sort by final score (descending)
        evaluated.sort(key=lambda x: x["_scoring"]["final_score"], reverse=True)
        
        # Check for conflicts (long vs short)
        long_candidates = [c for c in evaluated if c.get("signal") == "long"]
        short_candidates = [c for c in evaluated if c.get("signal") == "short"]
        
        selected = None
        if long_candidates and short_candidates:
            # Conflict - reject all
            for c in evaluated:
                c["_rejection_reason"] = "signal_conflict"
            rejection_reasons["signal_conflict"] = len(evaluated)
            logger.warning(f"Signal conflict detected: {len(long_candidates)} long vs {len(short_candidates)} short")
        else:
            # No conflict - select highest score
            if evaluated:
                selected = evaluated[0]
                logger.info(
                    f"Selected {selected.get('strategy')} {selected.get('signal')} "
                    f"with final_score={selected['_scoring']['final_score']:.3f}"
                )
        
        return {
            "selected": selected,
            "all_candidates": evaluated,
            "rejection_summary": rejection_reasons
        }
    
    def _calculate_strategy_weight(
        self,
        strategy_name: str,
        regime_scores: Dict[str, float],
        regime: str
    ) -> float:
        """
        Calculate strategy weight based on regime.
        
        Weight = base * regime_multiplier
        
        Where regime_multiplier can be:
        - From regime string lookup (simple)
        - OR computed from regime scores (advanced)
        """
        config = self.weights_config.get(strategy_name, {})
        base = config.get("base", 1.0)
        
        # Get regime multiplier from config
        regime_multipliers = config.get("regime_multipliers", {})
        regime_mult = regime_multipliers.get(regime, 1.0)
        
        # Advanced: Could also blend based on regime_scores
        # For now, use simple regime lookup
        
        return base * regime_mult


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

    """
    Task 3: Enhanced Signal Hygiene + No-Trade Zones
    
    Проверка условий для запрета торговли с унифицированными фильтрами:
    - Max spread % check
    - Max ATR % check
    - Anomaly blocking (respects allow_anomaly_on_testnet)
    - Orderbook quality checks
    - Error count threshold
    
    All rejections have snake_case reason codes for observability.
    """
    
    def __init__(
        self,
        max_atr_pct: float = 14.0,
        max_spread_pct: float = 0.50,
        max_error_count: int = 5,
        allow_anomaly_on_testnet: bool = False,
        min_depth_imbalance: float = 0.99
    ):
        """
        Args:
            max_atr_pct: Максимальный ATR% для торговли
            max_spread_pct: Максимальный спред% для торговли
            max_error_count: Максимальное количество ошибок до блокировки
            allow_anomaly_on_testnet: Разрешить аномалии на testnet
            min_depth_imbalance: Минимальный depth imbalance (>= блокировка)
        """
        self.max_atr_pct = max_atr_pct
        self.max_spread_pct = max_spread_pct
        self.max_error_count = max_error_count
        self.allow_anomaly_on_testnet = allow_anomaly_on_testnet
        self.min_depth_imbalance = min_depth_imbalance
        
        logger.info(
            f"NoTradeZones initialized: max_atr_pct={max_atr_pct}, "
            f"max_spread_pct={max_spread_pct}, max_error_count={max_error_count}, "
            f"allow_anomaly_on_testnet={allow_anomaly_on_testnet}"
        )

    def is_trading_allowed(

        self, df: pd.DataFrame, features: Dict[str, Any], error_count: int = 0

    ) -> tuple[bool, Optional[str]]:
        """
        Проверить, разрешена ли торговля (Task 3: Unified filters).

        Returns:

            (allowed: bool, reason: str or None) - reason in snake_case

        """

        latest = df.iloc[-1]

        # Filter 1: Data anomaly check
        anomaly_result = self._check_anomaly(latest, features)
        if not anomaly_result[0]:
            return anomaly_result

        # Filter 2: Orderbook quality check
        orderbook_result = self._check_orderbook_quality(latest, features)
        if not orderbook_result[0]:
            return orderbook_result

        # Filter 3: Spread check (liquidity)
        spread_result = self._check_spread(latest, features)
        if not spread_result[0]:
            return spread_result

        # Filter 4: Depth imbalance check (optional, usually disabled for testnet)
        depth_result = self._check_depth_imbalance(latest, features)
        if not depth_result[0]:
            return depth_result

        # Filter 5: Error count check
        error_result = self._check_error_count(error_count)
        if not error_result[0]:
            return error_result

        # Filter 6: Extreme volatility check
        volatility_result = self._check_extreme_volatility(latest)
        if not volatility_result[0]:
            return volatility_result

        return True, None
    
    def _check_anomaly(
        self, 
        latest: pd.Series, 
        features: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Filter 1: Anomaly detection
        
        Reason codes:
        - anomaly_wick
        - anomaly_low_volume
        - anomaly_gap
        - anomaly_detected (generic)
        """
        has_anomaly = latest.get("has_anomaly", 0)
        
        if has_anomaly != 1:
            return True, None
        
        # Check if testnet exception applies
        is_testnet = bool(features.get("is_testnet", False))
        allow_on_testnet = self.allow_anomaly_on_testnet or bool(features.get("allow_anomaly_on_testnet", False))
        
        if is_testnet and allow_on_testnet:
            logger.debug("Anomaly detected but allowed on testnet")
            return True, None
        
        # Determine specific anomaly type if available
        anomaly_wick = latest.get("anomaly_wick", 0)
        anomaly_low_volume = latest.get("anomaly_low_volume", 0)
        anomaly_gap = latest.get("anomaly_gap", 0)
        
        if anomaly_wick == 1:
            return False, "anomaly_wick"
        elif anomaly_low_volume == 1:
            return False, "anomaly_low_volume"
        elif anomaly_gap == 1:
            return False, "anomaly_gap"
        else:
            return False, "anomaly_detected"
    
    def _check_orderbook_quality(
        self, 
        latest: pd.Series, 
        features: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Filter 2: Orderbook quality
        
        Reason code: orderbook_invalid
        """
        orderbook_invalid = features.get("orderbook_invalid", False) or latest.get("orderbook_invalid", False)
        
        if orderbook_invalid:
            deviation = features.get("orderbook_deviation_pct") or latest.get("orderbook_deviation_pct", 0)
            return False, f"orderbook_invalid|deviation={deviation:.2f}%"
        
        return True, None
    
    def _check_spread(
        self, 
        latest: pd.Series, 
        features: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Filter 3: Spread check (liquidity)
        
        Reason code: excessive_spread
        """
        spread_percent = features.get("spread_percent")
        if spread_percent is None:
            spread_percent = latest.get("spread_percent", 0)
        
        # Skip if spread is None (orderbook was invalid)
        if spread_percent is None:
            return True, None
        
        if spread_percent > self.max_spread_pct:
            return False, f"excessive_spread|{spread_percent:.2f}%>{self.max_spread_pct}%"
        
        return True, None
    
    def _check_depth_imbalance(
        self, 
        latest: pd.Series, 
        features: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Filter 4: Depth imbalance (optional)
        
        Reason code: depth_imbalance_extreme
        """
        depth_imbalance = features.get("depth_imbalance", 0)
        
        # Usually disabled for testnet (min_depth_imbalance >= 0.99)
        if abs(depth_imbalance) >= self.min_depth_imbalance:
            return False, f"depth_imbalance_extreme|{depth_imbalance:.2f}"
        
        return True, None
    
    def _check_error_count(
        self, 
        error_count: int
    ) -> tuple[bool, Optional[str]]:
        """
        Filter 5: Error count threshold
        
        Reason code: too_many_errors
        """
        if error_count > self.max_error_count:
            return False, f"too_many_errors|count={error_count}>{self.max_error_count}"
        
        return True, None
    
    def _check_extreme_volatility(
        self, 
        latest: pd.Series
    ) -> tuple[bool, Optional[str]]:
        """
        Filter 6: Extreme volatility
        
        Reason code: extreme_volatility
        """
        vol_regime = latest.get("vol_regime", 0)
        atr_percent = latest.get("atr_percent", 0)
        
        if vol_regime == 1 and atr_percent > self.max_atr_pct:
            return False, f"extreme_volatility|atr={atr_percent:.2f}%>{self.max_atr_pct}%"
        
        return True, None


class MetaLayer:

    """Центральный мета-слой для управления стратегиями"""

    def __init__(

        self,

        strategies: List[BaseStrategy],

        use_mtf: bool = True,

        mtf_score_threshold: float = 0.6,
        
        high_vol_event_atr_pct: float = 7.0,
        
        no_trade_zone_max_atr_pct: float = 14.0,
        
        no_trade_zone_max_spread_pct: float = 0.50,
        
        ema_router_config: Optional[Dict[str, Any]] = None,
        
        weights_config: Optional[Dict[str, Any]] = None,
        
        use_weighted_router: bool = True,

    ):
        """

        Args:

            strategies: Список стратегий

            use_mtf: Использовать multi-timeframe confluence checks

            mtf_score_threshold: Порог прохождения MTF-скоринга (0..1)
            
            high_vol_event_atr_pct: Порог ATR% для high_vol_event
            
            no_trade_zone_max_atr_pct: Максимальный ATR% для торговли
            
            no_trade_zone_max_spread_pct: Максимальный спред% для торговли
            
            ema_router_config: Конфигурация EMA-router для выбора pullback/breakout
            
            weights_config: Конфигурация весов стратегий для weighted router
            
            use_weighted_router: Использовать взвешенный роутер (Task 2)

        """

        self.strategies = strategies

        self.regime_switcher = RegimeSwitcher()
        
        self.regime_scorer = RegimeScorer()  # Task 1
        
        self.weighted_router = WeightedStrategyRouter(weights_config) if use_weighted_router else None

        self.arbitrator = SignalArbitrator()

        self.no_trade_zones = NoTradeZones(
            max_atr_pct=no_trade_zone_max_atr_pct,
            max_spread_pct=no_trade_zone_max_spread_pct
        )

        self.use_mtf = use_mtf

        self.mtf_score_threshold = mtf_score_threshold
        
        self.high_vol_event_atr_pct = high_vol_event_atr_pct
        
        self.use_weighted_router = use_weighted_router
        
        # EMA-router: выбор между pullback/breakout по расстоянию до EMA
        self.ema_router_config = ema_router_config or {}
        self._ema_route_state = None  # "near" | "far" | None (для гистерезиса)

        self.timeframe_cache = TimeframeCache() if use_mtf else None

        logger.info(

            f"MetaLayer initialized with {len(strategies)} strategies "

            f"(MTF: {use_mtf}, mtf_score_threshold={mtf_score_threshold}, "
            
            f"high_vol_event_atr_pct={high_vol_event_atr_pct}, "
            
            f"ema_router={'enabled' if self.ema_router_config.get('enabled') else 'disabled'})"

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

        # GUARD: Проверяем наличие symbol в features
        if not features:
            features = {}
        
        if "symbol" not in features or not features["symbol"]:
            logger.warning(
                "⚠️  Symbol missing in features! This should be guaranteed by caller. "
                "Adding UNKNOWN as fallback."
            )
            features["symbol"] = "UNKNOWN"

        # 1. No-trade zones

        trading_allowed, block_reason = self.no_trade_zones.is_trading_allowed(

            df, features, error_count

        )

        if not trading_allowed:

            signal_logger.log_signal_rejected(

                strategy_name="MetaLayer",

                symbol=features.get("symbol", "UNKNOWN"),

                direction="N/A",

                confidence=0.0,

                reasons=["no_trade_zone"],

                values={

                    "reason": block_reason,

                    "error_count": error_count,

                },

            )

            return None

        # 2. Определяем режим рынка

        regime = self.regime_switcher.detect_regime(
            df, 
            high_vol_atr_threshold=self.high_vol_event_atr_pct
        )
        
        # Task 1: Compute regime scores
        regime_scores = self.regime_scorer.compute_scores(df, features)

        # Логируем только при смене режима

        # 3. Включаем/выключаем стратегии по режиму (+ EMA-router)

        self._adjust_strategies_by_regime(regime, df)

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
            
            # Безопасное извлечение ema_distance_atr (NaN -> None для JSON)
            import math
            ema_dist_raw = latest.get("ema_distance_atr")
            if ema_dist_raw is not None and not (isinstance(ema_dist_raw, float) and (math.isnan(ema_dist_raw) or math.isinf(ema_dist_raw))):
                ema_dist = round(ema_dist_raw, 2)
            else:
                ema_dist = None

            signal_logger.log_debug_info(

                category="strategy_analysis",

                regime=regime,
                
                regime_scores=regime_scores,

                active_strategies=active_strategies_info,

                market_conditions={

                    "adx": round(latest.get("adx", latest.get("ADX_14", 0)), 2),

                    "close": round(latest.get("close", 0), 2),

                    "volume_z": round(latest.get("volume_zscore", 0), 2),

                    "atr": round(latest.get("atr", 0), 4),

                    "ema_distance_atr": ema_dist,

                    "ema_route_state": self._ema_route_state,

                },

            )
        
        # 5. Task 2: Use weighted router if enabled, otherwise use old arbitrator
        
        if self.use_weighted_router and self.weighted_router and signals:
            # Weighted routing with observability
            routing_result = self.weighted_router.route_signals(
                candidates=signals,
                regime_scores=regime_scores,
                regime=regime_scores.get("regime", regime),
                symbol=features.get("symbol", "UNKNOWN"),
                mtf_score=None  # Will be computed later if MTF enabled
            )
            
            final_signal = routing_result.get("selected")
            all_candidates = routing_result.get("all_candidates", [])
            
            # Task 8: Log all candidates with observability
            self._log_candidate_decisions(
                all_candidates=all_candidates,
                selected=final_signal,
                regime=regime,
                regime_scores=regime_scores,
                symbol=features.get("symbol", "UNKNOWN")
            )
            
            # If no signal selected due to conflict, log rejection
            if final_signal is None and signals:
                signal_logger.log_signal_rejected(
                    strategy_name="MetaLayer",
                    symbol=features.get("symbol", "UNKNOWN"),
                    direction="CONFLICT",
                    confidence=0.0,
                    reasons=["weighted_router_conflict"],
                    values={
                        "num_candidates": len(signals),
                        "rejection_summary": routing_result.get("rejection_summary", {})
                    },
                )
        else:
            # Old arbitrator path (backward compatibility)
            final_signal = self.arbitrator.arbitrate_signals(signals)
            
            # Old path conflict logging
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

    def _route_by_ema_distance(self, candidates: List[str], df: pd.DataFrame) -> List[str]:
        """
        EMA-router: выбор между pullback/breakout на основе расстояния до EMA.
        
        Логика:
        - Если цена близко к EMA (<= near_atr) → предпочитаем pullback
        - Если цена далеко от EMA (>= far_atr) → предпочитаем breakout
        - В середине → возвращаем всех кандидатов (или используем гистерезис)
        
        Args:
            candidates: Список кандидатов-стратегий для текущего режима
            df: DataFrame с индикаторами (должен содержать ema_distance_atr)
            
        Returns:
            Отфильтрованный список стратегий
        """
        import math
        
        # Если роутер выключен или нет кандидатов
        if not self.ema_router_config.get("enabled", False) or not candidates:
            return candidates
        
        # Получаем параметры
        near_atr = self.ema_router_config.get("near_atr", 0.7)
        far_atr = self.ema_router_config.get("far_atr", 1.2)
        hys = self.ema_router_config.get("hysteresis_atr", 0.1)
        near_strategies = set(self.ema_router_config.get("near_strategies", []))
        far_strategies = set(self.ema_router_config.get("far_strategies", []))
        
        # Получаем метрику
        if df is None or df.empty:
            return candidates
            
        latest = df.iloc[-1]
        ema_dist = latest.get("ema_distance_atr")
        
        # Деградация если метрика не готова
        if ema_dist is None or (isinstance(ema_dist, float) and (math.isnan(ema_dist) or math.isinf(ema_dist))):
            logger.debug("EMA-router: ema_distance_atr not available, returning all candidates")
            return candidates
        
        # Применяем гистерезис на основе последнего состояния
        near_threshold = near_atr
        far_threshold = far_atr
        
        if self._ema_route_state == "near":
            # Был near → требуем +hys чтобы переключиться на far
            far_threshold += hys
        elif self._ema_route_state == "far":
            # Был far → требуем -hys чтобы переключиться на near
            near_threshold -= hys
        
        # Принимаем решение
        if ema_dist <= near_threshold:
            self._ema_route_state = "near"
            filtered = [s for s in candidates if s in near_strategies]
            logger.debug(
                f"EMA-router: NEAR (ema_dist={ema_dist:.2f} <= {near_threshold:.2f}) "
                f"→ {filtered or candidates}"
            )
            return filtered or candidates  # Fallback если нет совпадений
        
        elif ema_dist >= far_threshold:
            self._ema_route_state = "far"
            filtered = [s for s in candidates if s in far_strategies]
            logger.debug(
                f"EMA-router: FAR (ema_dist={ema_dist:.2f} >= {far_threshold:.2f}) "
                f"→ {filtered or candidates}"
            )
            return filtered or candidates
        
        else:
            # Средняя зона - оставляем всех кандидатов или последнее состояние
            self._ema_route_state = None
            logger.debug(
                f"EMA-router: MID (ema_dist={ema_dist:.2f} in [{near_threshold:.2f}, {far_threshold:.2f}]) "
                f"→ all candidates"
            )
            return candidates

    def _log_candidate_decisions(
        self,
        all_candidates: List[Dict[str, Any]],
        selected: Optional[Dict[str, Any]],
        regime: str,
        regime_scores: Dict[str, float],
        symbol: str
    ):
        """
        Task 8: Log all candidates with observability.
        
        Structured JSON log per decision with:
        - All candidates (raw/scaled conf, weight, final_score, direction)
        - Rejected candidates with reasons
        - Selected signal with top factors
        """
        decision_log = {
            "symbol": symbol,
            "regime": regime,
            "regime_scores": regime_scores,
            "candidates": [],
            "selected_strategy": selected.get("strategy") if selected else None,
            "selected_direction": selected.get("signal") if selected else None,
            "selected_final_score": selected["_scoring"]["final_score"] if selected and "_scoring" in selected else None
        }
        
        # Log each candidate
        for candidate in all_candidates:
            scoring = candidate.get("_scoring", {})
            candidate_info = {
                "strategy": candidate.get("strategy"),
                "direction": candidate.get("signal"),
                "raw_confidence": scoring.get("raw_confidence"),
                "scaled_confidence": scoring.get("raw_confidence"),  # Will be updated in Task 4
                "strategy_weight": scoring.get("strategy_weight"),
                "final_score": scoring.get("final_score"),
                "rejection_reason": candidate.get("_rejection_reason"),
                "key_values": {
                    k: v for k, v in candidate.get("values", {}).items()
                    if k in ["adx", "ema_distance_atr", "volume_zscore", "atr_percent"]
                }
            }
            decision_log["candidates"].append(candidate_info)
        
        # Log via signal_logger
        signal_logger.log_debug_info(
            category="weighted_router_decision",
            **decision_log
        )
        
        logger.info(
            f"Weighted router decision: {len(all_candidates)} candidates, "
            f"selected={decision_log['selected_strategy']} {decision_log['selected_direction']}"
        )

    def _adjust_strategies_by_regime(self, regime: str, df: Optional[pd.DataFrame] = None):
        """Включить/выключить стратегии в зависимости от режима и EMA-router"""
        
        # Получаем кандидатов из конфига EMA-router (если есть) или используем старую логику
        if self.ema_router_config.get("enabled", False):
            regime_strategies = self.ema_router_config.get("regime_strategies", {})
            candidates = regime_strategies.get(regime, [])
            
            # Применяем EMA-router
            active_strategy_names = self._route_by_ema_distance(candidates, df)
        else:
            # Старая логика (обратная совместимость)
            active_strategy_names = self._get_legacy_strategy_names(regime)
        
        # Включаем/выключаем стратегии
        for strategy in self.strategies:

            if strategy.name in active_strategy_names:
                strategy.enable()
            else:
                strategy.disable()
    
    def _get_legacy_strategy_names(self, regime: str) -> List[str]:
        """Старая логика выбора стратегий по режиму (обратная совместимость)"""
        active = []

        if regime in ["trend_up", "trend_down"]:
            active.append("TrendPullback")
        
        if regime == "range":
            active.extend(["Breakout", "MeanReversion"])
        
        return active

    def _adjust_strategies_by_regime_old(self, regime: str):
        """DEPRECATED: старая версия, оставлена для справки"""

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
