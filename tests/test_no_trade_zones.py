"""
Unit tests for Signal Hygiene + No-Trade Zones (Task 3).

Tests each filter independently:
1. Anomaly detection (with testnet exception)
2. Orderbook quality
3. Spread check
4. Depth imbalance
5. Error count
6. Extreme volatility
"""

import pytest
import pandas as pd
import numpy as np
from strategy.meta_layer import NoTradeZones


class TestNoTradeZones:
    """Test Signal Hygiene and No-Trade Zone Filters"""
    
    def test_anomaly_wick_blocks_trading(self):
        """Test that wick anomaly blocks trading"""
        ntz = NoTradeZones()
        
        df = pd.DataFrame({
            'close': [100.0],
            'has_anomaly': [1],
            'anomaly_wick': [1],
            'anomaly_low_volume': [0],
            'anomaly_gap': [0]
        })
        
        allowed, reason = ntz.is_trading_allowed(df, {}, error_count=0)
        
        assert not allowed
        assert reason == "anomaly_wick"
    
    def test_anomaly_low_volume_blocks_trading(self):
        """Test that low volume anomaly blocks trading"""
        ntz = NoTradeZones()
        
        df = pd.DataFrame({
            'close': [100.0],
            'has_anomaly': [1],
            'anomaly_wick': [0],
            'anomaly_low_volume': [1],
            'anomaly_gap': [0]
        })
        
        allowed, reason = ntz.is_trading_allowed(df, {}, error_count=0)
        
        assert not allowed
        assert reason == "anomaly_low_volume"
    
    def test_anomaly_gap_blocks_trading(self):
        """Test that gap anomaly blocks trading"""
        ntz = NoTradeZones()
        
        df = pd.DataFrame({
            'close': [100.0],
            'has_anomaly': [1],
            'anomaly_wick': [0],
            'anomaly_low_volume': [0],
            'anomaly_gap': [1]
        })
        
        allowed, reason = ntz.is_trading_allowed(df, {}, error_count=0)
        
        assert not allowed
        assert reason == "anomaly_gap"
    
    def test_anomaly_allowed_on_testnet(self):
        """Test that anomalies are allowed on testnet when configured"""
        ntz = NoTradeZones(allow_anomaly_on_testnet=True)
        
        df = pd.DataFrame({
            'close': [100.0],
            'has_anomaly': [1],
            'anomaly_wick': [1]
        })
        
        features = {
            'is_testnet': True
        }
        
        allowed, reason = ntz.is_trading_allowed(df, features, error_count=0)
        
        assert allowed
        assert reason is None
    
    def test_anomaly_blocked_on_mainnet(self):
        """Test that anomalies are blocked on mainnet even with testnet flag"""
        ntz = NoTradeZones(allow_anomaly_on_testnet=True)
        
        df = pd.DataFrame({
            'close': [100.0],
            'has_anomaly': [1],
            'anomaly_wick': [1]
        })
        
        features = {
            'is_testnet': False
        }
        
        allowed, reason = ntz.is_trading_allowed(df, features, error_count=0)
        
        assert not allowed
        assert "anomaly" in reason
    
    def test_orderbook_invalid_blocks_trading(self):
        """Test that invalid orderbook blocks trading"""
        ntz = NoTradeZones()
        
        df = pd.DataFrame({
            'close': [100.0],
            'has_anomaly': [0]
        })
        
        features = {
            'orderbook_invalid': True,
            'orderbook_deviation_pct': 5.5
        }
        
        allowed, reason = ntz.is_trading_allowed(df, features, error_count=0)
        
        assert not allowed
        assert "orderbook_invalid" in reason
        assert "5.5" in reason
    
    def test_excessive_spread_blocks_trading(self):
        """Test that excessive spread blocks trading"""
        ntz = NoTradeZones(max_spread_pct=0.5)
        
        df = pd.DataFrame({
            'close': [100.0],
            'has_anomaly': [0],
            'spread_percent': [0.8]  # Exceeds 0.5%
        })
        
        allowed, reason = ntz.is_trading_allowed(df, {}, error_count=0)
        
        assert not allowed
        assert "excessive_spread" in reason
        assert "0.8" in reason or "0.80" in reason
    
    def test_acceptable_spread_allows_trading(self):
        """Test that acceptable spread allows trading"""
        ntz = NoTradeZones(max_spread_pct=0.5)
        
        df = pd.DataFrame({
            'close': [100.0],
            'has_anomaly': [0],
            'spread_percent': [0.3],  # Within limit
            'vol_regime': [0],
            'atr_percent': [2.0]
        })
        
        allowed, reason = ntz.is_trading_allowed(df, {}, error_count=0)
        
        assert allowed
        assert reason is None
    
    def test_depth_imbalance_extreme_blocks_trading(self):
        """Test that extreme depth imbalance blocks trading"""
        ntz = NoTradeZones(min_depth_imbalance=0.9)
        
        df = pd.DataFrame({
            'close': [100.0],
            'has_anomaly': [0],
            'spread_percent': [0.1]
        })
        
        features = {
            'depth_imbalance': 0.95  # Exceeds 0.9 threshold
        }
        
        allowed, reason = ntz.is_trading_allowed(df, features, error_count=0)
        
        assert not allowed
        assert "depth_imbalance_extreme" in reason
    
    def test_error_count_threshold_blocks_trading(self):
        """Test that error count threshold blocks trading"""
        ntz = NoTradeZones(max_error_count=3)
        
        df = pd.DataFrame({
            'close': [100.0],
            'has_anomaly': [0],
            'spread_percent': [0.1]
        })
        
        # error_count = 5 exceeds max of 3
        allowed, reason = ntz.is_trading_allowed(df, {}, error_count=5)
        
        assert not allowed
        assert "too_many_errors" in reason
        assert "5" in reason
    
    def test_error_count_below_threshold_allows_trading(self):
        """Test that error count below threshold allows trading"""
        ntz = NoTradeZones(max_error_count=5)
        
        df = pd.DataFrame({
            'close': [100.0],
            'has_anomaly': [0],
            'spread_percent': [0.1],
            'vol_regime': [0],
            'atr_percent': [1.5]
        })
        
        # error_count = 3 is below max of 5
        allowed, reason = ntz.is_trading_allowed(df, {}, error_count=3)
        
        assert allowed
        assert reason is None
    
    def test_extreme_volatility_blocks_trading(self):
        """Test that extreme volatility blocks trading"""
        ntz = NoTradeZones(max_atr_pct=10.0)
        
        df = pd.DataFrame({
            'close': [100.0],
            'has_anomaly': [0],
            'spread_percent': [0.1],
            'vol_regime': [1],  # High vol regime
            'atr_percent': [12.0]  # Exceeds 10%
        })
        
        allowed, reason = ntz.is_trading_allowed(df, {}, error_count=0)
        
        assert not allowed
        assert "extreme_volatility" in reason
        assert "12" in reason or "12.0" in reason
    
    def test_normal_volatility_allows_trading(self):
        """Test that normal volatility allows trading"""
        ntz = NoTradeZones(max_atr_pct=10.0)
        
        df = pd.DataFrame({
            'close': [100.0],
            'has_anomaly': [0],
            'spread_percent': [0.1],
            'vol_regime': [0],  # Normal vol regime
            'atr_percent': [3.0]  # Within limit
        })
        
        allowed, reason = ntz.is_trading_allowed(df, {}, error_count=0)
        
        assert allowed
        assert reason is None
    
    def test_high_atr_without_vol_regime_allows_trading(self):
        """Test that high ATR without vol_regime flag allows trading"""
        ntz = NoTradeZones(max_atr_pct=10.0)
        
        df = pd.DataFrame({
            'close': [100.0],
            'has_anomaly': [0],
            'spread_percent': [0.1],
            'vol_regime': [0],  # Not in high vol regime
            'atr_percent': [12.0]  # High but vol_regime not set
        })
        
        allowed, reason = ntz.is_trading_allowed(df, {}, error_count=0)
        
        assert allowed  # Should allow because vol_regime is 0
        assert reason is None
    
    def test_all_filters_pass(self):
        """Test that trading is allowed when all filters pass"""
        ntz = NoTradeZones(
            max_atr_pct=10.0,
            max_spread_pct=0.5,
            max_error_count=5,
            min_depth_imbalance=0.99
        )
        
        df = pd.DataFrame({
            'close': [100.0],
            'has_anomaly': [0],
            'spread_percent': [0.15],
            'vol_regime': [0],
            'atr_percent': [2.5],
            'orderbook_invalid': [False]
        })
        
        features = {
            'depth_imbalance': 0.3,
            'is_testnet': False
        }
        
        allowed, reason = ntz.is_trading_allowed(df, features, error_count=2)
        
        assert allowed
        assert reason is None
    
    def test_reason_codes_are_snake_case(self):
        """Test that all reason codes are in snake_case"""
        ntz = NoTradeZones()
        
        test_cases = [
            # Anomaly
            (pd.DataFrame({'close': [100], 'has_anomaly': [1], 'anomaly_wick': [1]}), {}),
            # Spread
            (pd.DataFrame({'close': [100], 'has_anomaly': [0], 'spread_percent': [1.0]}), {}),
            # Volatility
            (pd.DataFrame({'close': [100], 'has_anomaly': [0], 'spread_percent': [0.1], 'vol_regime': [1], 'atr_percent': [20.0]}), {}),
        ]
        
        for df, features in test_cases:
            allowed, reason = ntz.is_trading_allowed(df, features, error_count=0)
            if not allowed and reason:
                # Extract the reason code (before any pipe character)
                reason_code = reason.split('|')[0]
                # Check snake_case (lowercase with underscores, no spaces)
                assert reason_code.islower() or '_' in reason_code, f"Reason code '{reason_code}' is not snake_case"
                assert ' ' not in reason_code, f"Reason code '{reason_code}' contains spaces"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
