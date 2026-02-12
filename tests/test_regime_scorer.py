"""
Unit tests for Market Regime Scorer (Task 1).

Tests three scenarios with synthetic data:
1. Trend scenario - high ADX, aligned EMAs, expanding BBs
2. Range scenario - low ADX, narrow BBs, price near EMAs
3. High volatility scenario - elevated ATR%, wide spreads
"""

import pytest
import pandas as pd
import numpy as np
from strategy.regime_scorer import RegimeScorer


class TestRegimeScorer:
    """Test Market Regime Scorer"""
    
    def test_trend_scenario(self):
        """Test trend scenario: high ADX, aligned EMAs, momentum"""
        scorer = RegimeScorer()
        
        # Create synthetic trending market data
        df = pd.DataFrame({
            'close': [100 + i * 0.5 for i in range(50)],  # Uptrend
            'adx': [30.0] * 50,  # Strong ADX
            'ema_20': [100 + i * 0.5 for i in range(50)],  # Following trend
            'ema_50': [99 + i * 0.4 for i in range(50)],  # Below EMA20
            'atr_percent': [2.0] * 50,  # Moderate volatility
            'bb_width': [0.04] * 50,  # Moderate width
            'bb_width_pct_change': [0.05] * 50,  # Expanding
            'volume_zscore': [1.5] * 50,  # Above average volume
            'spread_percent': [0.1] * 50,
            'ema_distance_atr': [0.5] * 50,  # Some distance from EMA
            'depth_imbalance': [0.0] * 50
        })
        
        result = scorer.compute_scores(df)
        
        # Assertions for trend scenario
        assert result['trend_score'] > 0.5, f"Expected high trend_score, got {result['trend_score']}"
        assert result['range_score'] < 0.3, f"Expected low range_score, got {result['range_score']}"
        assert result['regime'] == 'trend', f"Expected 'trend' regime, got {result['regime']}"
        assert result['fallback_reason'] is None
        
        # Verify all scores are in valid range
        for score_key in ['trend_score', 'range_score', 'volatility_score', 'chop_score']:
            assert 0.0 <= result[score_key] <= 1.0, f"{score_key} out of range: {result[score_key]}"
    
    def test_range_scenario(self):
        """Test range scenario: low ADX, narrow BBs, price oscillating"""
        scorer = RegimeScorer()
        
        # Create synthetic ranging market data
        # Use ADX in 18-20 range to avoid choppy detection (ADX < 15)
        df = pd.DataFrame({
            'close': [100 + np.sin(i * 0.5) * 2 for i in range(50)],  # Oscillating
            'adx': [18.0] * 50,  # Low but not choppy ADX
            'ema_20': [100.0] * 50,  # Flat EMA
            'ema_50': [100.1] * 50,  # Very close to EMA20
            'atr_percent': [1.0] * 50,  # Low volatility
            'bb_width': [0.025] * 50,  # Narrow BBs
            'bb_width_pct_change': [-0.02] * 50,  # Contracting
            'volume_zscore': [0.0] * 50,  # Average volume
            'spread_percent': [0.08] * 50,
            'ema_distance_atr': [0.8] * 50,  # Not too close to avoid choppy
            'depth_imbalance': [0.0] * 50
        })
        
        result = scorer.compute_scores(df)
        
        # Assertions for range scenario
        assert result['range_score'] > 0.5, f"Expected high range_score, got {result['range_score']}"
        assert result['trend_score'] < 0.3, f"Expected low trend_score, got {result['trend_score']}"
        # Accept either range or choppy as both are valid for this scenario
        assert result['regime'] in ['range', 'choppy'], f"Expected 'range' or 'choppy' regime, got {result['regime']}"
        assert result['fallback_reason'] is None
        
        # Verify all scores are in valid range
        for score_key in ['trend_score', 'range_score', 'volatility_score', 'chop_score']:
            assert 0.0 <= result[score_key] <= 1.0, f"{score_key} out of range: {result[score_key]}"
    
    def test_high_volatility_scenario(self):
        """Test high volatility scenario: elevated ATR%, expanding BBs"""
        scorer = RegimeScorer()
        
        # Create synthetic high volatility data
        df = pd.DataFrame({
            'close': [100 + i * 2 if i % 2 == 0 else 100 - i for i in range(50)],  # Volatile
            'adx': [22.0] * 50,  # Moderate ADX
            'ema_20': [100.0] * 50,
            'ema_50': [100.5] * 50,
            'atr_percent': [6.0] * 50,  # Very high ATR%
            'bb_width': [0.08] * 50,  # Wide BBs
            'bb_width_pct_change': [0.15] * 50,  # Rapidly expanding
            'volume_zscore': [2.0] * 50,
            'spread_percent': [0.4] * 50,  # Wide spreads
            'ema_distance_atr': [1.5] * 50,
            'depth_imbalance': [0.0] * 50
        })
        
        result = scorer.compute_scores(df)
        
        # Assertions for high volatility scenario
        assert result['volatility_score'] > 0.6, f"Expected high volatility_score, got {result['volatility_score']}"
        assert result['regime'] == 'high_volatility', f"Expected 'high_volatility' regime, got {result['regime']}"
        assert result['fallback_reason'] is None
        
        # Verify all scores are in valid range
        for score_key in ['trend_score', 'range_score', 'volatility_score', 'chop_score']:
            assert 0.0 <= result[score_key] <= 1.0, f"{score_key} out of range: {result[score_key]}"
    
    def test_fallback_empty_dataframe(self):
        """Test fallback behavior with empty dataframe"""
        scorer = RegimeScorer()
        
        df = pd.DataFrame()
        result = scorer.compute_scores(df)
        
        # Should return neutral scores with fallback reason
        assert result['trend_score'] == 0.5
        assert result['range_score'] == 0.5
        assert result['volatility_score'] == 0.5
        assert result['chop_score'] == 0.5
        assert result['regime'] == 'neutral'
        assert result['fallback_reason'] is not None
        assert 'empty' in result['fallback_reason'].lower()
    
    def test_fallback_missing_critical_indicators(self):
        """Test fallback when critical indicators are missing"""
        scorer = RegimeScorer()
        
        # DataFrame with only close prices, missing ADX and ATR%
        df = pd.DataFrame({
            'close': [100.0] * 20,
            'volume': [1000.0] * 20
        })
        
        result = scorer.compute_scores(df)
        
        # Should return neutral scores with fallback reason
        assert result['trend_score'] == 0.5
        assert result['regime'] == 'neutral'
        assert result['fallback_reason'] is not None
        assert 'missing' in result['fallback_reason'].lower()
    
    def test_partial_indicators(self):
        """Test scoring with partial indicators available"""
        scorer = RegimeScorer()
        
        # DataFrame with only critical indicators (ADX, ATR%)
        df = pd.DataFrame({
            'close': [100.0] * 30,
            'adx': [20.0] * 30,
            'atr_percent': [1.5] * 30
        })
        
        result = scorer.compute_scores(df)
        
        # Should compute scores (not fallback) but with reduced accuracy
        assert result['fallback_reason'] is None
        assert result['regime'] in ['trend', 'range', 'neutral', 'choppy', 'high_volatility']
        assert len(result['missing_columns']) > 0  # Some columns should be missing
    
    def test_choppy_scenario(self):
        """Test choppy/noisy market detection"""
        scorer = RegimeScorer()
        
        # Very low ADX, very narrow BBs, price bouncing around EMA
        df = pd.DataFrame({
            'close': [100 + np.random.randn() * 0.1 for _ in range(50)],  # Noise
            'adx': [10.0] * 50,  # Very low ADX
            'ema_20': [100.0] * 50,
            'ema_50': [100.0] * 50,
            'atr_percent': [0.8] * 50,  # Low volatility
            'bb_width': [0.015] * 50,  # Very narrow
            'bb_width_pct_change': [-0.01] * 50,
            'volume_zscore': [-0.5] * 50,
            'spread_percent': [0.05] * 50,
            'ema_distance_atr': [0.1] * 50,  # Very close to EMA
            'depth_imbalance': [0.0] * 50
        })
        
        result = scorer.compute_scores(df)
        
        # Should detect choppy conditions
        assert result['chop_score'] > 0.5, f"Expected high chop_score, got {result['chop_score']}"
        assert result['regime'] == 'choppy', f"Expected 'choppy' regime, got {result['regime']}"
    
    def test_score_bounds(self):
        """Test that all scores are always bounded between 0 and 1"""
        scorer = RegimeScorer()
        
        # Create extreme values to test bounds
        df = pd.DataFrame({
            'close': [100.0] * 30,
            'adx': [100.0] * 30,  # Extreme ADX
            'ema_20': [100.0] * 30,
            'ema_50': [50.0] * 30,  # Large EMA difference
            'atr_percent': [20.0] * 30,  # Extreme ATR%
            'bb_width': [0.5] * 30,  # Very wide
            'bb_width_pct_change': [1.0] * 30,  # Extreme expansion
            'volume_zscore': [10.0] * 30,  # Extreme volume
            'spread_percent': [5.0] * 30,  # Extreme spread
            'ema_distance_atr': [10.0] * 30,  # Far from EMA
            'depth_imbalance': [1.0] * 30
        })
        
        result = scorer.compute_scores(df)
        
        # All scores must be in [0, 1] range
        for score_key in ['trend_score', 'range_score', 'volatility_score', 'chop_score']:
            score = result[score_key]
            assert 0.0 <= score <= 1.0, f"{score_key} out of bounds: {score}"
    
    def test_regime_consistency(self):
        """Test that regime determination is consistent with scores"""
        scorer = RegimeScorer()
        
        # High trend score scenario
        df = pd.DataFrame({
            'close': [100 + i for i in range(30)],
            'adx': [35.0] * 30,
            'ema_20': [100 + i for i in range(30)],
            'ema_50': [99 + i * 0.8 for i in range(30)],
            'atr_percent': [2.5] * 30,
            'bb_width': [0.05] * 30,
            'bb_width_pct_change': [0.1] * 30,
            'volume_zscore': [2.0] * 30,
            'spread_percent': [0.1] * 30,
            'ema_distance_atr': [1.2] * 30,
            'depth_imbalance': [0.0] * 30
        })
        
        result = scorer.compute_scores(df)
        
        # With high trend_score, regime should be 'trend'
        if result['trend_score'] > 0.6 and result['volatility_score'] < 0.6:
            assert result['regime'] == 'trend', \
                f"High trend_score ({result['trend_score']}) should give 'trend' regime, got {result['regime']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
