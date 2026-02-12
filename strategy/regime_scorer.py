"""
Market Regime Scorer: Computes regime scores from market data.

Task 1 of EPIC: Improve strategy selection
- Computes regime scores: trend_score, range_score, volatility_score, chop_score
- Uses existing indicators: ADX, ATR/ATR%, BB width, structure, volume_zscore, etc.
- Provides fallback when columns are missing with reason codes
"""

from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from logger import setup_logger

logger = setup_logger(__name__)


class RegimeScorer:
    """
    Computes market regime scores for intelligent strategy weighting.
    
    Scores range from 0.0 to 1.0:
    - trend_score: Higher when ADX strong, EMA aligned, directional movement
    - range_score: Higher when ADX low, BB narrow, price oscillating
    - volatility_score: Higher when ATR% elevated, BB expanding
    - chop_score: Higher when price is choppy/sideways (inverse of trend)
    """
    
    def __init__(self):
        self.logger = logger
        
    def compute_scores(
        self,
        df: pd.DataFrame,
        features: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Compute all regime scores from dataframe and features.
        
        Args:
            df: DataFrame with OHLCV + indicators
            features: Optional pre-computed features dict
            
        Returns:
            {
                "trend_score": float (0-1),
                "range_score": float (0-1),
                "volatility_score": float (0-1),
                "chop_score": float (0-1),
                "regime": str,  # dominant regime
                "missing_columns": List[str],
                "fallback_reason": Optional[str]
            }
        """
        if df is None or df.empty or len(df) < 10:
            return self._fallback_scores("empty_or_insufficient_data")
            
        latest = df.iloc[-1]
        
        # Track missing columns for observability
        missing = []
        
        # Extract indicators with fallbacks
        adx = self._get_value(latest, ["adx", "ADX_14"], missing)
        atr_percent = self._get_value(latest, ["atr_percent"], missing)
        bb_width = self._get_value(latest, ["bb_width"], missing)
        bb_width_pct_change = self._get_value(latest, ["bb_width_pct_change"], missing)
        ema_20 = self._get_value(latest, ["ema_20"], missing)
        ema_50 = self._get_value(latest, ["ema_50"], missing)
        close = self._get_value(latest, ["close"], missing)
        volume_zscore = self._get_value(latest, ["volume_zscore"], missing)
        spread_percent = self._get_value(latest, ["spread_percent"], missing)
        ema_distance_atr = self._get_value(latest, ["ema_distance_atr"], missing)
        depth_imbalance = self._get_value(latest, ["depth_imbalance"], missing)
        
        # If critical indicators missing, return fallback
        if adx is None or atr_percent is None:
            reason = f"missing_critical_indicators: {missing}"
            return self._fallback_scores(reason)
        
        # Compute individual scores
        trend_score = self._compute_trend_score(
            adx=adx,
            ema_20=ema_20,
            ema_50=ema_50,
            close=close,
            volume_zscore=volume_zscore,
            ema_distance_atr=ema_distance_atr
        )
        
        range_score = self._compute_range_score(
            adx=adx,
            bb_width=bb_width,
            bb_width_pct_change=bb_width_pct_change,
            ema_distance_atr=ema_distance_atr,
            atr_percent=atr_percent
        )
        
        volatility_score = self._compute_volatility_score(
            atr_percent=atr_percent,
            bb_width_pct_change=bb_width_pct_change,
            spread_percent=spread_percent
        )
        
        chop_score = self._compute_chop_score(
            adx=adx,
            bb_width=bb_width,
            ema_distance_atr=ema_distance_atr
        )
        
        # Determine dominant regime
        regime = self._determine_regime(trend_score, range_score, volatility_score, chop_score)
        
        result = {
            "trend_score": round(trend_score, 3),
            "range_score": round(range_score, 3),
            "volatility_score": round(volatility_score, 3),
            "chop_score": round(chop_score, 3),
            "regime": regime,
            "missing_columns": missing,
            "fallback_reason": None
        }
        
        self.logger.debug(
            f"RegimeScorer: trend={trend_score:.2f} range={range_score:.2f} "
            f"vol={volatility_score:.2f} chop={chop_score:.2f} → {regime}"
        )
        
        return result
    
    def _compute_trend_score(
        self,
        adx: Optional[float],
        ema_20: Optional[float],
        ema_50: Optional[float],
        close: Optional[float],
        volume_zscore: Optional[float],
        ema_distance_atr: Optional[float]
    ) -> float:
        """
        Trend score: 0 (no trend) to 1 (strong trend)
        
        Components:
        - ADX strength (>25 is strong trend)
        - EMA alignment (20>50 or 20<50)
        - Volume support (z-score > 0)
        - Distance from EMA (momentum)
        """
        score = 0.0
        
        # ADX component (0-0.4)
        if adx is not None:
            # Normalize ADX: 0-15 → 0, 15-25 → linear, 25+ → 0.4
            if adx < 15:
                adx_score = 0.0
            elif adx < 25:
                adx_score = (adx - 15) / 10 * 0.4
            else:
                adx_score = 0.4
            score += adx_score
        
        # EMA alignment component (0-0.3)
        if ema_20 is not None and ema_50 is not None and ema_20 != 0 and ema_50 != 0:
            ema_diff_pct = abs(ema_20 - ema_50) / ema_50
            # Normalize: 0-0.5% → 0, 0.5-2% → linear to 0.3, 2%+ → 0.3
            if ema_diff_pct < 0.005:
                ema_score = 0.0
            elif ema_diff_pct < 0.02:
                ema_score = (ema_diff_pct - 0.005) / 0.015 * 0.3
            else:
                ema_score = 0.3
            score += ema_score
        
        # Volume confirmation component (0-0.15)
        if volume_zscore is not None:
            vol_score = min(max(volume_zscore, 0), 3) / 3 * 0.15
            score += vol_score
        
        # Distance from EMA (momentum) component (0-0.15)
        if ema_distance_atr is not None:
            # Higher distance indicates momentum
            dist_score = min(abs(ema_distance_atr), 2) / 2 * 0.15
            score += dist_score
        
        return min(score, 1.0)
    
    def _compute_range_score(
        self,
        adx: Optional[float],
        bb_width: Optional[float],
        bb_width_pct_change: Optional[float],
        ema_distance_atr: Optional[float],
        atr_percent: Optional[float]
    ) -> float:
        """
        Range score: 0 (trending) to 1 (strong range)
        
        Components:
        - Low ADX (<20 is range)
        - Narrow BB width
        - BB contracting
        - Price near EMA (low ema_distance_atr)
        - Stable ATR%
        """
        score = 0.0
        
        # Low ADX component (0-0.4)
        if adx is not None:
            # Normalize ADX: 25+ → 0, 20-25 → linear, <20 → 0.4
            if adx > 25:
                adx_score = 0.0
            elif adx > 20:
                adx_score = (25 - adx) / 5 * 0.4
            else:
                adx_score = 0.4
            score += adx_score
        
        # Narrow BB width component (0-0.3)
        if bb_width is not None:
            # Normalize: >0.05 → 0, 0.03-0.05 → linear, <0.03 → 0.3
            if bb_width > 0.05:
                bb_score = 0.0
            elif bb_width > 0.03:
                bb_score = (0.05 - bb_width) / 0.02 * 0.3
            else:
                bb_score = 0.3
            score += bb_score
        
        # BB contracting component (0-0.15)
        if bb_width_pct_change is not None and bb_width_pct_change < 0:
            # More negative = more contracting
            contraction_score = min(abs(bb_width_pct_change), 0.1) / 0.1 * 0.15
            score += contraction_score
        
        # Price near EMA component (0-0.15)
        if ema_distance_atr is not None:
            # Lower distance = more range-bound
            near_score = (1 - min(abs(ema_distance_atr), 1)) * 0.15
            score += near_score
        
        return min(score, 1.0)
    
    def _compute_volatility_score(
        self,
        atr_percent: Optional[float],
        bb_width_pct_change: Optional[float],
        spread_percent: Optional[float]
    ) -> float:
        """
        Volatility score: 0 (calm) to 1 (high volatility)
        
        Components:
        - ATR% elevated
        - BB expanding
        - Spread widening (less weight)
        """
        score = 0.0
        
        # ATR% component (0-0.6)
        if atr_percent is not None:
            # Normalize: <1% → 0, 1-5% → linear to 0.6, >5% → 0.6
            if atr_percent < 1.0:
                atr_score = 0.0
            elif atr_percent < 5.0:
                atr_score = (atr_percent - 1.0) / 4.0 * 0.6
            else:
                atr_score = 0.6
            score += atr_score
        
        # BB expanding component (0-0.3)
        if bb_width_pct_change is not None and bb_width_pct_change > 0:
            expansion_score = min(bb_width_pct_change, 0.2) / 0.2 * 0.3
            score += expansion_score
        
        # Spread component (0-0.1)
        if spread_percent is not None:
            spread_score = min(spread_percent, 0.5) / 0.5 * 0.1
            score += spread_score
        
        return min(score, 1.0)
    
    def _compute_chop_score(
        self,
        adx: Optional[float],
        bb_width: Optional[float],
        ema_distance_atr: Optional[float]
    ) -> float:
        """
        Chop score: 0 (clean trend/range) to 1 (choppy/noisy)
        
        This is essentially inverse of trend but with different weighting.
        High chop = low ADX + narrow BB + price oscillating near EMA
        """
        score = 0.0
        
        # Low ADX component (0-0.5)
        if adx is not None:
            # <15 is very choppy
            if adx < 15:
                adx_score = 0.5
            elif adx < 25:
                adx_score = (25 - adx) / 10 * 0.5
            else:
                adx_score = 0.0
            score += adx_score
        
        # Narrow BB component (0-0.3)
        if bb_width is not None:
            if bb_width < 0.02:
                bb_score = 0.3
            elif bb_width < 0.04:
                bb_score = (0.04 - bb_width) / 0.02 * 0.3
            else:
                bb_score = 0.0
            score += bb_score
        
        # Near EMA oscillation component (0-0.2)
        if ema_distance_atr is not None:
            # Very close to EMA but not exactly on it
            if abs(ema_distance_atr) < 0.5:
                near_score = 0.2
            elif abs(ema_distance_atr) < 1.0:
                near_score = (1.0 - abs(ema_distance_atr)) / 0.5 * 0.2
            else:
                near_score = 0.0
            score += near_score
        
        return min(score, 1.0)
    
    def _determine_regime(
        self,
        trend_score: float,
        range_score: float,
        volatility_score: float,
        chop_score: float
    ) -> str:
        """
        Determine dominant regime from scores.
        
        Priority:
        1. high_volatility if volatility_score > 0.6
        2. choppy if chop_score > 0.6
        3. trend if trend_score > range_score and trend_score > 0.4
        4. range if range_score > trend_score and range_score > 0.4
        5. neutral otherwise
        """
        if volatility_score > 0.6:
            return "high_volatility"
        
        if chop_score > 0.6:
            return "choppy"
        
        if trend_score > range_score and trend_score > 0.4:
            return "trend"
        
        if range_score > trend_score and range_score > 0.4:
            return "range"
        
        return "neutral"
    
    def _get_value(
        self,
        row: pd.Series,
        column_names: List[str],
        missing_tracker: List[str]
    ) -> Optional[float]:
        """
        Get value from row, trying multiple column names.
        Track missing columns for observability.
        """
        for col in column_names:
            if col in row.index:
                val = row[col]
                if pd.notna(val):
                    return float(val)
        
        # All column names missing or NaN
        missing_tracker.extend([c for c in column_names if c not in row.index])
        return None
    
    def _fallback_scores(self, reason: str) -> Dict[str, Any]:
        """
        Return neutral scores when regime can't be computed.
        """
        self.logger.warning(f"RegimeScorer: Using fallback scores, reason={reason}")
        
        return {
            "trend_score": 0.5,
            "range_score": 0.5,
            "volatility_score": 0.5,
            "chop_score": 0.5,
            "regime": "neutral",
            "missing_columns": [],
            "fallback_reason": reason
        }
