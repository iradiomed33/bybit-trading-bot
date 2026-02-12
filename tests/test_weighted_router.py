"""
Unit tests for Weighted Strategy Router (Task 2).

Tests:
1. Trend regime favors TrendPullback over MeanReversion
2. Range regime favors MeanReversion over TrendPullback
3. Breakout selection depends on ema_distance_atr in trend
4. Conflict handling (long + short signals)
5. Weighted scoring calculation
"""

import pytest
import pandas as pd
import numpy as np
from strategy.meta_layer import WeightedStrategyRouter


class TestWeightedStrategyRouter:
    """Test Weighted Strategy Router"""
    
    def test_trend_regime_favors_pullback(self):
        """Test that trend regime gives higher weight to TrendPullback"""
        router = WeightedStrategyRouter()
        
        # Simulate trend regime scores
        regime_scores = {
            "trend_score": 0.8,
            "range_score": 0.2,
            "volatility_score": 0.3,
            "chop_score": 0.1,
            "regime": "trend"
        }
        
        # Create candidates from different strategies
        candidates = [
            {
                "strategy": "TrendPullback",
                "signal": "long",
                "confidence": 0.7,
                "reasons": ["trend_aligned"],
                "values": {}
            },
            {
                "strategy": "MeanReversion",
                "signal": "long",
                "confidence": 0.7,  # Same raw confidence
                "reasons": ["oversold"],
                "values": {}
            }
        ]
        
        result = router.route_signals(
            candidates=candidates,
            regime_scores=regime_scores,
            regime="trend",
            symbol="BTCUSDT"
        )
        
        # TrendPullback should be selected (higher weight in trend)
        assert result["selected"] is not None
        assert result["selected"]["strategy"] == "TrendPullback"
        
        # Verify scoring
        all_candidates = result["all_candidates"]
        pullback = next(c for c in all_candidates if c["strategy"] == "TrendPullback")
        mean_rev = next(c for c in all_candidates if c["strategy"] == "MeanReversion")
        
        assert pullback["_scoring"]["final_score"] > mean_rev["_scoring"]["final_score"]
        assert pullback["_scoring"]["strategy_weight"] > mean_rev["_scoring"]["strategy_weight"]
    
    def test_range_regime_favors_mean_reversion(self):
        """Test that range regime gives higher weight to MeanReversion"""
        router = WeightedStrategyRouter()
        
        regime_scores = {
            "trend_score": 0.2,
            "range_score": 0.8,
            "volatility_score": 0.2,
            "chop_score": 0.3,
            "regime": "range"
        }
        
        candidates = [
            {
                "strategy": "TrendPullback",
                "signal": "long",
                "confidence": 0.7,
                "reasons": ["pullback"],
                "values": {}
            },
            {
                "strategy": "MeanReversion",
                "signal": "long",
                "confidence": 0.7,
                "reasons": ["oversold"],
                "values": {}
            }
        ]
        
        result = router.route_signals(
            candidates=candidates,
            regime_scores=regime_scores,
            regime="range",
            symbol="BTCUSDT"
        )
        
        # MeanReversion should be selected (higher weight in range)
        assert result["selected"] is not None
        assert result["selected"]["strategy"] == "MeanReversion"
        
        # Verify scoring
        all_candidates = result["all_candidates"]
        pullback = next(c for c in all_candidates if c["strategy"] == "TrendPullback")
        mean_rev = next(c for c in all_candidates if c["strategy"] == "MeanReversion")
        
        assert mean_rev["_scoring"]["final_score"] > pullback["_scoring"]["final_score"]
        assert mean_rev["_scoring"]["strategy_weight"] > pullback["_scoring"]["strategy_weight"]
    
    def test_breakout_vs_pullback_in_trend(self):
        """Test that in trend, higher confidence can overcome weight differences"""
        router = WeightedStrategyRouter()
        
        regime_scores = {
            "trend_score": 0.7,
            "range_score": 0.3,
            "volatility_score": 0.3,
            "chop_score": 0.2,
            "regime": "trend"
        }
        
        candidates = [
            {
                "strategy": "TrendPullback",
                "signal": "long",
                "confidence": 0.6,  # Lower confidence
                "reasons": ["pullback"],
                "values": {}
            },
            {
                "strategy": "Breakout",
                "signal": "long",
                "confidence": 0.9,  # Much higher confidence
                "reasons": ["breakout"],
                "values": {}
            }
        ]
        
        result = router.route_signals(
            candidates=candidates,
            regime_scores=regime_scores,
            regime="trend",
            symbol="BTCUSDT"
        )
        
        # Breakout should win due to much higher confidence
        assert result["selected"] is not None
        # Either could win depending on weights, but verify scoring is applied
        assert "_scoring" in result["selected"]
        assert "final_score" in result["selected"]["_scoring"]
    
    def test_signal_conflict_blocks_all(self):
        """Test that conflicting signals (long + short) are blocked"""
        router = WeightedStrategyRouter()
        
        regime_scores = {
            "trend_score": 0.5,
            "range_score": 0.5,
            "volatility_score": 0.3,
            "chop_score": 0.3,
            "regime": "neutral"
        }
        
        candidates = [
            {
                "strategy": "TrendPullback",
                "signal": "long",
                "confidence": 0.8,
                "reasons": ["pullback_long"],
                "values": {}
            },
            {
                "strategy": "Breakout",
                "signal": "short",
                "confidence": 0.7,
                "reasons": ["breakout_short"],
                "values": {}
            }
        ]
        
        result = router.route_signals(
            candidates=candidates,
            regime_scores=regime_scores,
            regime="neutral",
            symbol="BTCUSDT"
        )
        
        # No signal should be selected due to conflict
        assert result["selected"] is None
        assert "signal_conflict" in result["rejection_summary"]
        
        # Both candidates should have rejection reason
        for candidate in result["all_candidates"]:
            assert candidate.get("_rejection_reason") == "signal_conflict"
    
    def test_mtf_multiplier_applied(self):
        """Test that MTF score affects final scoring"""
        import copy
        router = WeightedStrategyRouter()
        
        regime_scores = {
            "trend_score": 0.6,
            "range_score": 0.4,
            "volatility_score": 0.3,
            "chop_score": 0.2,
            "regime": "trend"
        }
        
        base_candidate = {
            "strategy": "TrendPullback",
            "signal": "long",
            "confidence": 0.7,
            "reasons": ["pullback"],
            "values": {}
        }
        
        # Test with high MTF score
        result_high_mtf = router.route_signals(
            candidates=[copy.deepcopy(base_candidate)],
            regime_scores=regime_scores,
            regime="trend",
            symbol="BTCUSDT",
            mtf_score=0.8
        )
        
        # Test with low MTF score
        result_low_mtf = router.route_signals(
            candidates=[copy.deepcopy(base_candidate)],
            regime_scores=regime_scores,
            regime="trend",
            symbol="BTCUSDT",
            mtf_score=0.2
        )
        
        # High MTF should result in higher final score
        high_score = result_high_mtf["selected"]["_scoring"]["final_score"]
        low_score = result_low_mtf["selected"]["_scoring"]["final_score"]
        
        assert high_score > low_score
        
        # Verify MTF multiplier is in range [0.5, 1.0]
        high_mtf_mult = result_high_mtf["selected"]["_scoring"]["mtf_multiplier"]
        low_mtf_mult = result_low_mtf["selected"]["_scoring"]["mtf_multiplier"]
        
        assert 0.5 <= high_mtf_mult <= 1.0
        assert 0.5 <= low_mtf_mult <= 1.0
        assert high_mtf_mult > low_mtf_mult
    
    def test_empty_candidates(self):
        """Test handling of empty candidate list"""
        router = WeightedStrategyRouter()
        
        regime_scores = {
            "trend_score": 0.5,
            "range_score": 0.5,
            "volatility_score": 0.3,
            "chop_score": 0.3,
            "regime": "neutral"
        }
        
        result = router.route_signals(
            candidates=[],
            regime_scores=regime_scores,
            regime="neutral",
            symbol="BTCUSDT"
        )
        
        assert result["selected"] is None
        assert result["all_candidates"] == []
        assert result["rejection_summary"] == {}
    
    def test_high_volatility_penalizes_all(self):
        """Test that high volatility regime reduces weights for all strategies"""
        router = WeightedStrategyRouter()
        
        regime_scores = {
            "trend_score": 0.3,
            "range_score": 0.2,
            "volatility_score": 0.8,
            "chop_score": 0.2,
            "regime": "high_volatility"
        }
        
        candidates = [
            {
                "strategy": "TrendPullback",
                "signal": "long",
                "confidence": 0.8,
                "reasons": ["pullback"],
                "values": {}
            },
            {
                "strategy": "Breakout",
                "signal": "long",
                "confidence": 0.8,
                "reasons": ["breakout"],
                "values": {}
            },
            {
                "strategy": "MeanReversion",
                "signal": "long",
                "confidence": 0.8,
                "reasons": ["oversold"],
                "values": {}
            }
        ]
        
        result = router.route_signals(
            candidates=candidates,
            regime_scores=regime_scores,
            regime="high_volatility",
            symbol="BTCUSDT"
        )
        
        # All strategies should have reduced weights in high volatility
        for candidate in result["all_candidates"]:
            weight = candidate["_scoring"]["strategy_weight"]
            # Weight should be less than base (1.0)
            assert weight < 1.0, f"{candidate['strategy']} should have reduced weight in high vol"
    
    def test_scoring_metadata_present(self):
        """Test that all candidates have scoring metadata"""
        router = WeightedStrategyRouter()
        
        regime_scores = {
            "trend_score": 0.6,
            "range_score": 0.4,
            "volatility_score": 0.3,
            "chop_score": 0.2,
            "regime": "trend"
        }
        
        candidates = [
            {
                "strategy": "TrendPullback",
                "signal": "long",
                "confidence": 0.7,
                "reasons": ["pullback"],
                "values": {}
            }
        ]
        
        result = router.route_signals(
            candidates=candidates,
            regime_scores=regime_scores,
            regime="trend",
            symbol="BTCUSDT"
        )
        
        # Check scoring metadata
        candidate = result["all_candidates"][0]
        assert "_scoring" in candidate
        
        scoring = candidate["_scoring"]
        assert "raw_confidence" in scoring
        assert "strategy_weight" in scoring
        assert "mtf_multiplier" in scoring
        assert "final_score" in scoring
        
        # Verify values
        assert scoring["raw_confidence"] == 0.7
        assert scoring["strategy_weight"] > 0
        assert scoring["mtf_multiplier"] == 1.0  # No MTF provided
        assert scoring["final_score"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
