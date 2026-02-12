"""
Integration tests for the complete weighted strategy selection flow (Task 9).

Tests end-to-end integration:
1. Trend regime → selects TrendPullback or Breakout based on ema_distance
2. Range regime → selects MeanReversion
3. High spread/ATR → blocks signals via hygiene filters
4. Complete flow: 3 strategies → regime scorer → router → final signal
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock

from strategy.meta_layer import MetaLayer
from strategy.base_strategy import BaseStrategy


class MockStrategy(BaseStrategy):
    """Mock strategy for testing"""
    
    def __init__(self, name: str, signal_to_return: dict = None):
        super().__init__(name=name)
        self.signal_to_return = signal_to_return
        self.call_count = 0
    
    def generate_signal(self, df: pd.DataFrame, features: dict) -> dict:
        self.call_count += 1
        if self.signal_to_return:
            return self.signal_to_return.copy()
        return None
    
    def calculate_stop_loss(self, *args, **kwargs):
        return 0.0
    
    def calculate_take_profit(self, *args, **kwargs):
        return 0.0


class TestIntegrationWeightedRouter:
    """Integration tests for weighted strategy router"""
    
    def test_trend_regime_selects_pullback_over_mean_reversion(self):
        """Test that trend regime favors TrendPullback over MeanReversion"""
        
        # Create mock strategies
        pullback_strategy = MockStrategy(
            "TrendPullback",
            {
                "signal": "long",
                "confidence": 0.7,
                "entry_price": 100.0,
                "stop_loss": 95.0,
                "take_profit": 110.0,
                "reasons": ["trend_aligned"],
                "values": {}
            }
        )
        
        mean_rev_strategy = MockStrategy(
            "MeanReversion",
            {
                "signal": "long",
                "confidence": 0.7,  # Same raw confidence
                "entry_price": 100.0,
                "stop_loss": 95.0,
                "take_profit": 105.0,
                "reasons": ["oversold"],
                "values": {}
            }
        )
        
        # Create MetaLayer with weighted router
        meta = MetaLayer(
            strategies=[pullback_strategy, mean_rev_strategy],
            use_mtf=False,
            use_weighted_router=True
        )
        
        # Create trend market data
        df = pd.DataFrame({
            'close': [100 + i * 0.5 for i in range(50)],  # Uptrend
            'adx': [30.0] * 50,  # Strong trend
            'ema_20': [100 + i * 0.5 for i in range(50)],
            'ema_50': [99 + i * 0.4 for i in range(50)],
            'atr_percent': [2.0] * 50,
            'bb_width': [0.04] * 50,
            'bb_width_pct_change': [0.05] * 50,
            'volume_zscore': [1.0] * 50,
            'spread_percent': [0.1] * 50,
            'ema_distance_atr': [0.5] * 50,
            'has_anomaly': [0] * 50,
            'vol_regime': [0] * 50
        })
        
        features = {
            "symbol": "BTCUSDT",
            "is_testnet": False
        }
        
        signal = meta.get_signal(df, features, error_count=0)
        
        # Should select TrendPullback (higher weight in trend)
        assert signal is not None
        assert signal["strategy"] == "TrendPullback"
        # TrendPullback should be called since it's enabled in trend regime
        assert pullback_strategy.call_count > 0
        # MeanReversion may or may not be called depending on regime filtering
    
    def test_range_regime_selects_mean_reversion(self):
        """Test that range regime favors MeanReversion"""
        
        # Create mock strategies
        pullback_strategy = MockStrategy(
            "TrendPullback",
            {
                "signal": "long",
                "confidence": 0.6,
                "entry_price": 100.0,
                "stop_loss": 95.0,
                "take_profit": 110.0,
                "reasons": ["pullback"],
                "values": {}
            }
        )
        
        mean_rev_strategy = MockStrategy(
            "MeanReversion",
            {
                "signal": "long",
                "confidence": 0.6,
                "entry_price": 100.0,
                "stop_loss": 95.0,
                "take_profit": 105.0,
                "reasons": ["oversold"],
                "values": {}
            }
        )
        
        # Create MetaLayer
        meta = MetaLayer(
            strategies=[pullback_strategy, mean_rev_strategy],
            use_mtf=False,
            use_weighted_router=True
        )
        
        # Create range market data
        df = pd.DataFrame({
            'close': [100 + np.sin(i * 0.3) * 2 for i in range(50)],  # Oscillating
            'adx': [18.0] * 50,  # Low ADX
            'ema_20': [100.0] * 50,
            'ema_50': [100.1] * 50,
            'atr_percent': [1.0] * 50,
            'bb_width': [0.025] * 50,
            'bb_width_pct_change': [-0.02] * 50,
            'volume_zscore': [0.0] * 50,
            'spread_percent': [0.1] * 50,
            'ema_distance_atr': [0.8] * 50,
            'has_anomaly': [0] * 50,
            'vol_regime': [0] * 50
        })
        
        features = {
            "symbol": "BTCUSDT",
            "is_testnet": False
        }
        
        signal = meta.get_signal(df, features, error_count=0)
        
        # Should select MeanReversion (higher weight in range)
        assert signal is not None
        assert signal["strategy"] == "MeanReversion"
    
    def test_high_spread_blocks_all_signals(self):
        """Test that high spread blocks signals via hygiene filter"""
        
        # Create mock strategy that generates signal
        pullback_strategy = MockStrategy(
            "TrendPullback",
            {
                "signal": "long",
                "confidence": 0.8,
                "entry_price": 100.0,
                "stop_loss": 95.0,
                "take_profit": 110.0,
                "reasons": ["trend_aligned"],
                "values": {}
            }
        )
        
        # Create MetaLayer with strict spread limit
        meta = MetaLayer(
            strategies=[pullback_strategy],
            use_mtf=False,
            no_trade_zone_max_spread_pct=0.5  # Max 0.5%
        )
        
        # Create data with excessive spread
        df = pd.DataFrame({
            'close': [100.0] * 20,
            'adx': [25.0] * 20,
            'ema_20': [100.0] * 20,
            'ema_50': [99.0] * 20,
            'atr_percent': [2.0] * 20,
            'bb_width': [0.04] * 20,
            'bb_width_pct_change': [0.02] * 20,
            'volume_zscore': [1.0] * 20,
            'spread_percent': [0.8] * 20,  # Excessive spread (0.8% > 0.5%)
            'has_anomaly': [0] * 20,
            'vol_regime': [0] * 20
        })
        
        features = {
            "symbol": "BTCUSDT",
            "is_testnet": False
        }
        
        signal = meta.get_signal(df, features, error_count=0)
        
        # Should be blocked due to excessive spread
        assert signal is None
        # Strategy should not even be called if no-trade zone blocks early
    
    def test_high_atr_blocks_signals(self):
        """Test that extreme volatility blocks signals"""
        
        # Create mock strategy
        strategy = MockStrategy(
            "TrendPullback",
            {
                "signal": "long",
                "confidence": 0.7,
                "entry_price": 100.0,
                "stop_loss": 95.0,
                "take_profit": 110.0,
                "reasons": ["pullback"],
                "values": {}
            }
        )
        
        # Create MetaLayer with ATR limit
        meta = MetaLayer(
            strategies=[strategy],
            use_mtf=False,
            no_trade_zone_max_atr_pct=10.0  # Max 10% ATR
        )
        
        # Create data with extreme volatility
        df = pd.DataFrame({
            'close': [100.0] * 20,
            'adx': [25.0] * 20,
            'ema_20': [100.0] * 20,
            'ema_50': [99.0] * 20,
            'atr_percent': [15.0] * 20,  # Extreme ATR (15% > 10%)
            'spread_percent': [0.1] * 20,
            'has_anomaly': [0] * 20,
            'vol_regime': [1] * 20  # High vol regime flag set
        })
        
        features = {
            "symbol": "BTCUSDT"
        }
        
        signal = meta.get_signal(df, features, error_count=0)
        
        # Should be blocked due to extreme volatility
        assert signal is None
    
    def test_signal_conflict_blocks_all(self):
        """Test that conflicting signals (long + short) are blocked"""
        
        # Create strategies with conflicting signals
        long_strategy = MockStrategy(
            "TrendPullback",
            {
                "signal": "long",
                "confidence": 0.7,
                "entry_price": 100.0,
                "stop_loss": 95.0,
                "take_profit": 110.0,
                "reasons": ["pullback_long"],
                "values": {}
            }
        )
        
        short_strategy = MockStrategy(
            "Breakout",
            {
                "signal": "short",
                "confidence": 0.6,
                "entry_price": 100.0,
                "stop_loss": 105.0,
                "take_profit": 90.0,
                "reasons": ["breakout_short"],
                "values": {}
            }
        )
        
        # Create MetaLayer
        meta = MetaLayer(
            strategies=[long_strategy, short_strategy],
            use_mtf=False,
            use_weighted_router=True
        )
        
        # Create neutral market data
        df = pd.DataFrame({
            'close': [100.0] * 30,
            'adx': [20.0] * 30,
            'ema_20': [100.0] * 30,
            'ema_50': [100.0] * 30,
            'atr_percent': [2.0] * 30,
            'bb_width': [0.03] * 30,
            'bb_width_pct_change': [0.0] * 30,
            'volume_zscore': [0.5] * 30,
            'spread_percent': [0.1] * 30,
            'ema_distance_atr': [0.3] * 30,
            'has_anomaly': [0] * 30,
            'vol_regime': [0] * 30
        })
        
        features = {
            "symbol": "BTCUSDT"
        }
        
        signal = meta.get_signal(df, features, error_count=0)
        
        # Should be blocked due to conflict
        assert signal is None
    
    def test_complete_flow_with_all_components(self):
        """Test complete flow: strategies → regime scorer → router → signal"""
        
        # Create all three strategies
        pullback = MockStrategy(
            "TrendPullback",
            {
                "signal": "long",
                "confidence": 0.75,
                "entry_price": 100.0,
                "stop_loss": 95.0,
                "take_profit": 110.0,
                "reasons": ["trend_pullback"],
                "values": {"adx": 28.0}
            }
        )
        
        breakout = MockStrategy(
            "Breakout",
            {
                "signal": "long",
                "confidence": 0.65,
                "entry_price": 100.0,
                "stop_loss": 95.0,
                "take_profit": 115.0,
                "reasons": ["breakout_confirmed"],
                "values": {"bb_width": 0.05}
            }
        )
        
        mean_rev = MockStrategy(
            "MeanReversion",
            {
                "signal": "long",
                "confidence": 0.60,
                "entry_price": 100.0,
                "stop_loss": 96.0,
                "take_profit": 104.0,
                "reasons": ["oversold"],
                "values": {"rsi": 25}
            }
        )
        
        # Create MetaLayer with all components
        meta = MetaLayer(
            strategies=[pullback, breakout, mean_rev],
            use_mtf=False,
            use_weighted_router=True,
            no_trade_zone_max_spread_pct=0.5,
            no_trade_zone_max_atr_pct=10.0
        )
        
        # Create strong trend data
        df = pd.DataFrame({
            'close': [100 + i for i in range(50)],  # Strong uptrend
            'adx': [32.0] * 50,
            'ema_20': [100 + i for i in range(50)],
            'ema_50': [99 + i * 0.9 for i in range(50)],
            'atr_percent': [3.0] * 50,
            'bb_width': [0.05] * 50,
            'bb_width_pct_change': [0.08] * 50,
            'volume_zscore': [1.5] * 50,
            'spread_percent': [0.12] * 50,  # Acceptable
            'ema_distance_atr': [1.0] * 50,
            'has_anomaly': [0] * 50,
            'vol_regime': [0] * 50
        })
        
        features = {
            "symbol": "BTCUSDT",
            "is_testnet": False
        }
        
        signal = meta.get_signal(df, features, error_count=0)
        
        # Should select a signal (TrendPullback most likely due to trend regime)
        assert signal is not None
        assert signal["strategy"] in ["TrendPullback", "Breakout"]  # Both valid in trend
        assert signal["signal"] == "long"
        assert "regime" in signal
        assert "_scoring" in signal or "confidence" in signal
        
        # At least pullback should have been called (enabled in trend regime)
        assert pullback.call_count > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
