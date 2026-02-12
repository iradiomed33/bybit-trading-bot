#!/usr/bin/env python3

"""

Debug why no trading signals are generated

"""


import sys

from logger import setup_logger


logger = setup_logger(__name__)


def debug_no_signals():
    """Debug why no signals are generated"""

    try:

        from bot.trading_bot import TradingBot

        from strategy.meta_layer import NoTradeZones, RegimeSwitcher

        from config.settings import ConfigManager

        from bot.strategy_builder import StrategyBuilder

        logger.info("=" * 60)

        logger.info("Debugging: Why No Trading Signals?")

        logger.info("=" * 60)

        # Create strategies from config

        logger.info("\nInitializing strategies from config...")

        config = ConfigManager()

        builder = StrategyBuilder(config)

        strategies = builder.build_strategies()

        # Create bot

        bot = TradingBot(mode="paper", strategies=strategies, symbol="BTCUSDT", testnet=True)

        # Get market data

        logger.info("\n1. Fetching market data...")

        data = bot._fetch_market_data()

        if not data:

            logger.error("   Failed to fetch market data!")

            return 1

        df = data["d"]

        features = data.get("orderflow_features", {})

        latest = df.iloc[-1]

        logger.info(f"   Data fetched: {len(df)} candles")

        # Check NoTradeZones

        logger.info("\n2. Checking NoTradeZones conditions...")

        trading_allowed, block_reason = NoTradeZones.is_trading_allowed(df, features, error_count=0)

        logger.info(f"   Trading allowed: {trading_allowed}")

        if not trading_allowed:

            logger.warning(f"   BLOCKED: {block_reason}")

            # Log all the conditions

            logger.info("\n   Detailed conditions:")

            has_anomaly = latest.get("has_anomaly", 0)

            logger.info(f"   - has_anomaly: {has_anomaly} (must be 0)")

            spread_percent = features.get("spread_percent", 0)

            logger.info(f"   - spread_percent: {spread_percent:.4f}% (must be < 2.0%)")

            depth_imbalance = features.get("depth_imbalance", 0)

            logger.info(f"   - depth_imbalance: {depth_imbalance:.4f} (must be < 0.9 in abs value)")

            vol_regime = latest.get("vol_regime", 0)

            atr_percent = latest.get("atr_percent", 0)

            logger.info(f"   - vol_regime: {vol_regime} (HIGH_VOL={1}, LOW_VOL={-1})")

            logger.info(f"   - atr_percent: {atr_percent:.2f}% (if HIGH_VOL, must be < 10%)")

            return 1

        # Check market regime

        logger.info("\n3. Checking market regime...")

        regime = RegimeSwitcher.detect_regime(df)

        logger.info(f"   Regime: {regime}")

        adx = latest.get("adx", latest.get("ADX_14", 0))

        ema_20 = latest.get("ema_20", 0)

        ema_50 = latest.get("ema_50", 0)

        logger.info(f"   - ADX: {adx:.2f} (trend strength)")

        logger.info(f"   - EMA20: {ema_20:.2f}")

        logger.info(f"   - EMA50: {ema_50:.2f}")

        logger.info(f"   - Price: {latest['close']:.2f}")

        # Check each strategy

        logger.info("\n4. Checking individual strategy conditions...")

        for strategy in bot.meta_layer.strategies:

            logger.info(f"\n   Strategy: {strategy.name}")

            logger.info(f"   - Enabled: {strategy.is_enabled}")

            if strategy.name == "TrendPullback":

                min_adx = strategy.min_adx

                required_adx_met = adx >= min_adx

                logger.info(f"   - Need ADX >= {min_adx}: {required_adx_met} (actual: {adx:.2f})")

            elif strategy.name == "Breakout":

                logger.info("   - Breakout specific conditions would be checked here")

            elif strategy.name == "MeanReversion":

                vol_regime = latest.get("vol_regime", 0)

                logger.info(

                    f"   - Need vol_regime == -1 (LOW): {vol_regime == -1} (actual: {vol_regime})"

                )

            # Try to generate signal

            try:

                signal = strategy.generate_signal(df, features)

                if signal:

                    logger.info(

                        f"   - Signal: {signal['signal']} (confidence: {signal['confidence']:.2f})"

                    )

                else:

                    logger.info("   - Signal: None (conditions not met)")

            except Exception as e:

                logger.error(f"   - Error generating signal: {e}")

        logger.info("\n" + "=" * 60)

        logger.info("Debug Complete")

        logger.info("=" * 60)

        return 0

    except Exception as e:

        logger.error(f"Debug failed: {e}", exc_info=True)

        return 1


if __name__ == "__main__":

    sys.exit(debug_no_signals())
