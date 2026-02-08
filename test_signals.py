#!/usr/bin/env python3

"""Simple test - generate signals"""

import sys

from logger import setup_logger


logger = setup_logger(__name__)


try:

    from bot.trading_bot import TradingBot

    from strategy import TrendPullbackStrategy, BreakoutStrategy, MeanReversionStrategy

    logger.info("=" * 60)

    logger.info("Testing Signal Generation")

    logger.info("=" * 60)

    strategies = [

        TrendPullbackStrategy(),

        BreakoutStrategy(),

        MeanReversionStrategy(),

    ]

    bot = TradingBot(mode="paper", strategies=strategies, symbol="BTCUSDT", testnet=True)

    logger.info("\n✓ Bot initialized")

    # Get market data

    data = bot._fetch_market_data()

    if not data:

        logger.error("✗ Failed to fetch market data")

        sys.exit(1)

    logger.info(f"✓ Market data fetched: {len(data['d'])} candles")

    # Try to get signal
    
    # TASK-001: Гарантируем наличие symbol в features
    orderflow_features = data.get("orderflow_features", {})
    orderflow_features["symbol"] = bot.symbol

    signal = bot.meta_layer.get_signal(data["d"], orderflow_features)

    if signal:

        logger.info("\n✅ SIGNAL GENERATED!")

        logger.info(f"   Direction: {signal['signal'].upper()}")

        logger.info(f"   Strategy:  {signal.get('strategy', 'unknown')}")

        logger.info(f"   Confidence: {signal.get('confidence', 0):.2f}")

        logger.info(f"   Reason:    {signal.get('reason', 'N/A')}")

    else:

        logger.info("\n❌ NO SIGNAL (conditions not met)")

    logger.info("\n" + "=" * 60)

    sys.exit(0)


except Exception as e:

    logger.error(f"Error: {e}", exc_info=True)

    sys.exit(1)
