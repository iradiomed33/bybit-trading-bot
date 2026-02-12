"""
Unit tests for Confidence Normalization/Calibration (Task 4).

Tests:
1. Default scaling (no change)
2. Per-strategy scaling
3. Per-symbol override
4. Clamping to [0, 1] range
5. Linear transformation correctness
"""

import pytest
from strategy.meta_layer import ConfidenceScaler


class TestConfidenceScaler:
    """Test Confidence Normalization and Calibration"""
    
    def test_default_no_scaling(self):
        """Test that default config does no scaling"""
        scaler = ConfidenceScaler()
        
        # Default is a=1.0, b=0.0
        assert scaler.scale_confidence(0.5, "TrendPullback") == 0.5
        assert scaler.scale_confidence(0.8, "Breakout") == 0.8
        assert scaler.scale_confidence(0.2, "MeanReversion") == 0.2
    
    def test_per_strategy_scaling(self):
        """Test per-strategy scaling parameters"""
        config = {
            "default": {"a": 1.0, "b": 0.0},
            "per_strategy": {
                "TrendPullback": {"a": 0.9, "b": 0.1},  # Slightly boost
                "Breakout": {"a": 1.1, "b": -0.05},      # Boost high, penalize low
                "MeanReversion": {"a": 0.8, "b": 0.2}    # Compress range
            }
        }
        
        scaler = ConfidenceScaler(config)
        
        # TrendPullback: 0.9x + 0.1
        # 0.5 → 0.55
        assert abs(scaler.scale_confidence(0.5, "TrendPullback") - 0.55) < 0.01
        
        # Breakout: 1.1x - 0.05
        # 0.7 → 0.72
        assert abs(scaler.scale_confidence(0.7, "Breakout") - 0.72) < 0.01
        
        # MeanReversion: 0.8x + 0.2
        # 0.6 → 0.68
        assert abs(scaler.scale_confidence(0.6, "MeanReversion") - 0.68) < 0.01
    
    def test_per_symbol_override(self):
        """Test per-symbol override takes precedence"""
        config = {
            "default": {"a": 1.0, "b": 0.0},
            "per_strategy": {
                "TrendPullback": {"a": 0.9, "b": 0.1}
            },
            "per_symbol": {
                "BTCUSDT": {
                    "TrendPullback": {"a": 1.2, "b": -0.1}
                }
            }
        }
        
        scaler = ConfidenceScaler(config)
        
        # For BTCUSDT, use symbol-specific override
        # 1.2x - 0.1
        # 0.5 → 0.5
        assert abs(scaler.scale_confidence(0.5, "TrendPullback", "BTCUSDT") - 0.5) < 0.01
        
        # For ETHUSDT, use per-strategy config
        # 0.9x + 0.1
        # 0.5 → 0.55
        assert abs(scaler.scale_confidence(0.5, "TrendPullback", "ETHUSDT") - 0.55) < 0.01
    
    def test_clamping_upper_bound(self):
        """Test that scaled confidence is clamped to max 1.0"""
        config = {
            "default": {"a": 1.0, "b": 0.0},
            "per_strategy": {
                "Breakout": {"a": 1.5, "b": 0.0}  # Aggressive boost
            }
        }
        
        scaler = ConfidenceScaler(config)
        
        # 1.5 * 0.8 = 1.2 → clamped to 1.0
        assert scaler.scale_confidence(0.8, "Breakout") == 1.0
        
        # 1.5 * 0.9 = 1.35 → clamped to 1.0
        assert scaler.scale_confidence(0.9, "Breakout") == 1.0
    
    def test_clamping_lower_bound(self):
        """Test that scaled confidence is clamped to min 0.0"""
        config = {
            "default": {"a": 1.0, "b": 0.0},
            "per_strategy": {
                "MeanReversion": {"a": 1.0, "b": -0.5}  # Negative offset
            }
        }
        
        scaler = ConfidenceScaler(config)
        
        # 1.0 * 0.3 - 0.5 = -0.2 → clamped to 0.0
        assert scaler.scale_confidence(0.3, "MeanReversion") == 0.0
        
        # 1.0 * 0.4 - 0.5 = -0.1 → clamped to 0.0
        assert scaler.scale_confidence(0.4, "MeanReversion") == 0.0
    
    def test_linear_transformation(self):
        """Test correctness of linear transformation formula"""
        config = {
            "default": {"a": 1.0, "b": 0.0},
            "per_strategy": {
                "TestStrategy": {"a": 2.0, "b": -0.3}
            }
        }
        
        scaler = ConfidenceScaler(config)
        
        # Formula: scaled = clamp(a * raw + b, 0, 1)
        # a=2.0, b=-0.3
        
        # raw=0.4 → 2.0*0.4 - 0.3 = 0.5
        assert abs(scaler.scale_confidence(0.4, "TestStrategy") - 0.5) < 0.01
        
        # raw=0.6 → 2.0*0.6 - 0.3 = 0.9
        assert abs(scaler.scale_confidence(0.6, "TestStrategy") - 0.9) < 0.01
        
        # raw=0.2 → 2.0*0.2 - 0.3 = 0.1
        assert abs(scaler.scale_confidence(0.2, "TestStrategy") - 0.1) < 0.01
    
    def test_identity_transformation(self):
        """Test that a=1, b=0 is identity"""
        config = {
            "default": {"a": 1.0, "b": 0.0}
        }
        
        scaler = ConfidenceScaler(config)
        
        test_values = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]
        
        for val in test_values:
            assert scaler.scale_confidence(val, "AnyStrategy") == val
    
    def test_boost_transformation(self):
        """Test boosting low confidences"""
        config = {
            "default": {"a": 1.0, "b": 0.0},
            "per_strategy": {
                "BoostStrategy": {"a": 0.8, "b": 0.2}  # Boost floor, compress range
            }
        }
        
        scaler = ConfidenceScaler(config)
        
        # Low confidences get boosted more
        # 0.2 → 0.8*0.2 + 0.2 = 0.36
        low_scaled = scaler.scale_confidence(0.2, "BoostStrategy")
        assert abs(low_scaled - 0.36) < 0.01
        
        # High confidences get slightly reduced
        # 0.9 → 0.8*0.9 + 0.2 = 0.92
        high_scaled = scaler.scale_confidence(0.9, "BoostStrategy")
        assert abs(high_scaled - 0.92) < 0.01
    
    def test_penalize_transformation(self):
        """Test penalizing confidences"""
        config = {
            "default": {"a": 1.0, "b": 0.0},
            "per_strategy": {
                "PenalizeStrategy": {"a": 1.2, "b": -0.2}  # Penalize floor, expand range
            }
        }
        
        scaler = ConfidenceScaler(config)
        
        # Low confidences get penalized (can go to 0)
        # 0.1 → 1.2*0.1 - 0.2 = -0.08 → clamped to 0.0
        assert scaler.scale_confidence(0.1, "PenalizeStrategy") == 0.0
        
        # Mid confidences slightly reduced
        # 0.5 → 1.2*0.5 - 0.2 = 0.4
        assert abs(scaler.scale_confidence(0.5, "PenalizeStrategy") - 0.4) < 0.01
        
        # High confidences boosted
        # 0.9 → 1.2*0.9 - 0.2 = 0.88
        assert abs(scaler.scale_confidence(0.9, "PenalizeStrategy") - 0.88) < 0.01
    
    def test_unknown_strategy_uses_default(self):
        """Test that unknown strategy uses default config"""
        config = {
            "default": {"a": 0.9, "b": 0.05},
            "per_strategy": {
                "TrendPullback": {"a": 1.1, "b": 0.0}
            }
        }
        
        scaler = ConfidenceScaler(config)
        
        # Unknown strategy should use default
        # 0.5 → 0.9*0.5 + 0.05 = 0.5
        assert abs(scaler.scale_confidence(0.5, "UnknownStrategy") - 0.5) < 0.01
    
    def test_edge_cases_zero_and_one(self):
        """Test edge cases of 0.0 and 1.0 confidence"""
        config = {
            "default": {"a": 1.0, "b": 0.0},
            "per_strategy": {
                "TestStrategy": {"a": 0.8, "b": 0.1}
            }
        }
        
        scaler = ConfidenceScaler(config)
        
        # 0.0 → 0.8*0.0 + 0.1 = 0.1
        assert abs(scaler.scale_confidence(0.0, "TestStrategy") - 0.1) < 0.01
        
        # 1.0 → 0.8*1.0 + 0.1 = 0.9
        assert abs(scaler.scale_confidence(1.0, "TestStrategy") - 0.9) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
