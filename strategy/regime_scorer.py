"""
Market Regime Scorer: оценка режима рынка через непрерывные метрики (0..1).

Компоненты:
- trend_score: сила тренда (ADX, EMA alignment)
- range_score: вероятность флэта (низкий ADX, узкие BB)
- volatility_score: уровень волатильности (ATR%)
- chop_score: степень "пилы"/шума (Choppiness Index или proxy)

Используется в MetaLayer для взвешенного выбора стратегий.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import pandas as pd
import numpy as np
from logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class RegimeScores:
    """Результат оценки режима рынка"""
    
    trend_score: float          # 0..1, где 1 = сильный тренд
    range_score: float          # 0..1, где 1 = явный флэт/диапазон
    volatility_score: float     # 0..1, где 1 = высокая волатильность
    chop_score: float           # 0..1, где 1 = сильная пила/шум
    
    # Дополнительные метаданные
    regime_label: str           # "trend_up" | "trend_down" | "range" | "high_vol" | "choppy" | "unknown"
    confidence: float           # Уверенность в определении режима (0..1)
    reasons: List[str]          # Причины/факторы
    values: Dict[str, Any]      # Сырые значения индикаторов
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь для логирования"""
        return {
            "trend_score": round(self.trend_score, 3),
            "range_score": round(self.range_score, 3),
            "volatility_score": round(self.volatility_score, 3),
            "chop_score": round(self.chop_score, 3),
            "regime_label": self.regime_label,
            "confidence": round(self.confidence, 3),
            "reasons": self.reasons,
            "values": self.values,
        }


class RegimeScorer:
    """Вычисление режимов рынка через multi-factor scoring"""
    
    def __init__(
        self,
        adx_trend_min: float = 25.0,
        adx_trend_max: float = 50.0,
        adx_range_max: float = 20.0,
        bb_width_range_max: float = 0.03,
        atr_pct_high: float = 3.0,
        atr_pct_extreme: float = 7.0,
    ):
        """
        Args:
            adx_trend_min: Минимальный ADX для начала тренда
            adx_trend_max: Максимальный ADX для нормализации (выше = 1.0)
            adx_range_max: Максимальный ADX для range режима
            bb_width_range_max: Максимальная ширина BB для range
            atr_pct_high: ATR% для начала высокой волатильности
            atr_pct_extreme: ATR% для экстремальной волатильности (1.0)
        """
        self.adx_trend_min = adx_trend_min
        self.adx_trend_max = adx_trend_max
        self.adx_range_max = adx_range_max
        self.bb_width_range_max = bb_width_range_max
        self.atr_pct_high = atr_pct_high
        self.atr_pct_extreme = atr_pct_extreme
        
        logger.info(
            f"RegimeScorer initialized: "
            f"ADX(trend={adx_trend_min}-{adx_trend_max}, range<={adx_range_max}), "
            f"BB_width(range<={bb_width_range_max}), "
            f"ATR%(high={atr_pct_high}, extreme={atr_pct_extreme})"
        )
    
    def score_regime(
        self,
        df: pd.DataFrame,
        features: Optional[Dict[str, Any]] = None
    ) -> RegimeScores:
        """
        Вычислить scores для всех компонентов режима.
        
        Args:
            df: DataFrame с OHLCV и индикаторами
            features: Дополнительные features (orderflow, etc.)
        
        Returns:
            RegimeScores с заполненными метриками
        """
        if df is None or df.empty:
            return self._neutral_scores("empty_dataframe")
        
        latest = df.iloc[-1]
        
        # Извлекаем индикаторы (с защитой от отсутствия)
        adx = self._safe_get(latest, ["adx", "ADX_14"], 0.0)
        atr_percent = self._safe_get(latest, ["atr_percent"], 0.0)
        bb_width = self._safe_get(latest, ["bb_width"], 0.0)
        bb_width_pct_change = self._safe_get(latest, ["bb_width_pct_change"], 0.0)
        atr_slope = self._safe_get(latest, ["atr_slope"], 0.0)
        ema_20 = self._safe_get(latest, ["ema_20"], 0.0)
        ema_50 = self._safe_get(latest, ["ema_50"], 0.0)
        close = self._safe_get(latest, ["close"], 0.0)
        volume_zscore = self._safe_get(latest, ["volume_zscore"], 0.0)
        
        # Orderflow features (опционально)
        spread_percent = None
        depth_imbalance = None
        if features:
            spread_percent = features.get("spread_percent", latest.get("spread_percent"))
            depth_imbalance = features.get("depth_imbalance", latest.get("depth_imbalance"))
        
        # Проверка критически важных индикаторов
        if ema_20 == 0 or ema_50 == 0 or close == 0:
            return self._neutral_scores("missing_critical_indicators")
        
        # === SCORING COMPONENTS ===
        
        # 1. Trend Score (0..1)
        trend_score = self._calculate_trend_score(
            adx, ema_20, ema_50, close, bb_width_pct_change
        )
        
        # 2. Range Score (0..1)
        range_score = self._calculate_range_score(
            adx, bb_width, bb_width_pct_change, atr_slope
        )
        
        # 3. Volatility Score (0..1)
        volatility_score = self._calculate_volatility_score(atr_percent)
        
        # 4. Chop Score (0..1) - proxy через комбинацию факторов
        chop_score = self._calculate_chop_score(
            adx, bb_width_pct_change, atr_slope, volume_zscore
        )
        
        # === DETERMINE REGIME LABEL ===
        regime_label, confidence, reasons = self._determine_regime_label(
            trend_score, range_score, volatility_score, chop_score,
            ema_20, ema_50, close
        )
        
        # === COLLECT VALUES ===
        values = {
            "adx": round(adx, 2),
            "atr_percent": round(atr_percent, 3),
            "bb_width": round(bb_width, 4),
            "bb_width_pct_change": round(bb_width_pct_change, 4),
            "atr_slope": round(atr_slope, 3),
            "ema_20": round(ema_20, 2),
            "ema_50": round(ema_50, 2),
            "close": round(close, 2),
            "volume_zscore": round(volume_zscore, 2),
        }
        
        if spread_percent is not None:
            values["spread_percent"] = round(spread_percent, 3)
        if depth_imbalance is not None:
            values["depth_imbalance"] = round(depth_imbalance, 3)
        
        return RegimeScores(
            trend_score=trend_score,
            range_score=range_score,
            volatility_score=volatility_score,
            chop_score=chop_score,
            regime_label=regime_label,
            confidence=confidence,
            reasons=reasons,
            values=values,
        )
    
    def _calculate_trend_score(
        self,
        adx: float,
        ema_20: float,
        ema_50: float,
        close: float,
        bb_width_pct_change: float
    ) -> float:
        """
        Вычислить силу тренда (0..1).
        
        Компоненты:
        - ADX (нормализованный)
        - Согласованность EMA (20 vs 50)
        - Расширение BB
        """
        # ADX component (нормализация от adx_trend_min до adx_trend_max)
        adx_component = self._normalize(
            adx, self.adx_trend_min, self.adx_trend_max
        )
        
        # EMA alignment (0 = нет разделения, 1 = сильное разделение)
        ema_diff_pct = abs(ema_20 - ema_50) / ema_50 if ema_50 > 0 else 0
        ema_component = min(ema_diff_pct / 0.05, 1.0)  # 5% = max
        
        # BB expansion (положительное изменение = тренд)
        bb_component = max(0, min(bb_width_pct_change / 0.2, 1.0))  # 20% change = max
        
        # Веса: ADX 50%, EMA 30%, BB 20%
        trend_score = (
            0.5 * adx_component +
            0.3 * ema_component +
            0.2 * bb_component
        )
        
        return min(max(trend_score, 0.0), 1.0)
    
    def _calculate_range_score(
        self,
        adx: float,
        bb_width: float,
        bb_width_pct_change: float,
        atr_slope: float
    ) -> float:
        """
        Вычислить вероятность флэта/range (0..1).
        
        Компоненты:
        - Низкий ADX
        - Узкие/сужающиеся BB
        - Стабильный ATR
        """
        # Low ADX component (обратная нормализация)
        adx_component = 1.0 - self._normalize(adx, 0, self.adx_range_max)
        
        # Narrow BB (0 = широкие, 1 = узкие)
        bb_component = 1.0 - self._normalize(bb_width, 0, self.bb_width_range_max)
        
        # Contracting BB (отрицательное изменение = сужение)
        bb_change_component = max(0, min(-bb_width_pct_change / 0.2, 1.0))
        
        # Stable ATR (низкий наклон)
        atr_component = 1.0 - min(abs(atr_slope) / 1.0, 1.0)
        
        # Веса: ADX 40%, BB_width 30%, BB_change 20%, ATR 10%
        range_score = (
            0.4 * adx_component +
            0.3 * bb_component +
            0.2 * bb_change_component +
            0.1 * atr_component
        )
        
        return min(max(range_score, 0.0), 1.0)
    
    def _calculate_volatility_score(self, atr_percent: float) -> float:
        """
        Вычислить уровень волатильности (0..1).
        
        Нормализация от atr_pct_high до atr_pct_extreme.
        """
        return self._normalize(atr_percent, self.atr_pct_high, self.atr_pct_extreme)
    
    def _calculate_chop_score(
        self,
        adx: float,
        bb_width_pct_change: float,
        atr_slope: float,
        volume_zscore: float
    ) -> float:
        """
        Вычислить степень "пилы" (choppy market) (0..1).
        
        Proxy через:
        - Низкий ADX (нет направления)
        - Нестабильная волатильность (высокий |atr_slope|)
        - Переменная активность (высокий |volume_zscore|)
        - Нестабильная BB
        """
        # Low ADX (отсутствие тренда)
        adx_component = 1.0 - self._normalize(adx, 0, 25.0)
        
        # Unstable volatility (высокий наклон ATR)
        atr_component = min(abs(atr_slope) / 2.0, 1.0)
        
        # Erratic volume
        volume_component = min(abs(volume_zscore) / 3.0, 1.0)
        
        # Unstable BB (частые изменения знака или высокая амплитуда)
        bb_component = min(abs(bb_width_pct_change) / 0.3, 1.0)
        
        # Веса: ADX 40%, ATR 30%, Volume 20%, BB 10%
        chop_score = (
            0.4 * adx_component +
            0.3 * atr_component +
            0.2 * volume_component +
            0.1 * bb_component
        )
        
        return min(max(chop_score, 0.0), 1.0)
    
    def _determine_regime_label(
        self,
        trend_score: float,
        range_score: float,
        volatility_score: float,
        chop_score: float,
        ema_20: float,
        ema_50: float,
        close: float
    ) -> tuple[str, float, List[str]]:
        """
        Определить категориальный режим и confidence на основе scores.
        
        Returns:
            (regime_label, confidence, reasons)
        """
        reasons = []
        
        # Приоритет 1: High volatility
        if volatility_score >= 0.7:
            return "high_vol", volatility_score, ["extreme_volatility"]
        
        # Приоритет 2: Choppy market (пила)
        if chop_score >= 0.6:
            return "choppy", chop_score, ["high_noise", "no_clear_direction"]
        
        # Приоритет 3: Trend vs Range
        if trend_score > range_score:
            # Определяем направление
            if ema_20 > ema_50 and close > ema_50:
                regime = "trend_up"
                reasons.append("strong_adx")
                reasons.append("ema_aligned_up")
            elif ema_20 < ema_50 and close < ema_50:
                regime = "trend_down"
                reasons.append("strong_adx")
                reasons.append("ema_aligned_down")
            else:
                # Тренд есть, но нет полной согласованности
                regime = "trend_up" if ema_20 > ema_50 else "trend_down"
                reasons.append("partial_trend")
            
            confidence = trend_score
            return regime, confidence, reasons
        
        elif range_score >= 0.5:
            # Range режим
            reasons.append("low_adx")
            reasons.append("narrow_bb")
            return "range", range_score, reasons
        
        else:
            # Неопределённый режим (low scores everywhere)
            return "unknown", 0.5, ["mixed_signals"]
    
    @staticmethod
    def _normalize(value: float, min_val: float, max_val: float) -> float:
        """Нормализовать значение в диапазон [0, 1]"""
        if max_val <= min_val:
            return 0.0 if value < max_val else 1.0
        
        normalized = (value - min_val) / (max_val - min_val)
        return min(max(normalized, 0.0), 1.0)
    
    @staticmethod
    def _safe_get(row: pd.Series, keys: List[str], default: float) -> float:
        """Безопасное получение значения из Series с fallback"""
        for key in keys:
            value = row.get(key)
            if value is not None and not (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
                return float(value)
        return default
    
    @staticmethod
    def _neutral_scores(reason: str) -> RegimeScores:
        """Вернуть нейтральные scores при недостатке данных"""
        logger.warning(f"RegimeScorer: Returning neutral scores due to: {reason}")
        return RegimeScores(
            trend_score=0.0,
            range_score=0.0,
            volatility_score=0.0,
            chop_score=0.0,
            regime_label="unknown",
            confidence=0.0,
            reasons=[reason],
            values={},
        )
