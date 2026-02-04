#!/usr/bin/env python3
"""
Test trading bot main loop logic
"""

import sys
import logging
from logger import setup_logger

logger = setup_logger(__name__)

def test_trading_bot_logic():
    """Test the actual trading bot logic"""
    try:
        from bot.trading_bot import TradingBot
        from strategy import TrendPullbackStrategy, BreakoutStrategy, MeanReversionStrategy
        
        logger.info("=" * 60)
        logger.info("Testing Trading Bot Logic")
        logger.info("=" * 60)
        
        # Create bot
        logger.info("\n1. Initializing trading bot in PAPER mode...")
        strategies = [
            TrendPullbackStrategy(),
            BreakoutStrategy(),
            MeanReversionStrategy(),
        ]
        
        bot = TradingBot(
            mode="paper",
            strategies=strategies,
            symbol="BTCUSDT",
            testnet=True
        )
        logger.info("   Bot initialized successfully!")
        
        # Run one iteration
        logger.info("\n2. Testing market data fetching (1 iteration)...")
        data = bot._fetch_market_data()
        
        if data:
            logger.info(f"   Market data fetched: {len(data['df'])} candles")
            logger.info(f"   DataFrame columns: {data['df'].columns.tolist()[:10]}...")
            
            # Test meta layer
            logger.info("\n3. Testing signal generation...")
            signal = bot.meta_layer.get_signal(data["df"], data.get("orderflow_features", {}))
            
            if signal:
                logger.info(f"   SIGNAL GENERATED: {signal['signal']}")
                logger.info(f"   Strategy: {signal.get('strategy', 'unknown')}")
                logger.info(f"   Confidence: {signal.get('confidence', 0)}")
                logger.info(f"   Reason: {signal.get('reason', 'no reason')}")
            else:
                logger.info("   No signal generated (conditions not met)")
                
        else:
            logger.error("   Failed to fetch market data!")
            return 1
            
        logger.info("\n" + "=" * 60)
        logger.info("Test Complete")
        logger.info("=" * 60)
        return 0
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(test_trading_bot_logic())
