#!/usr/bin/env python3

"""

Simple test script to debug market data fetching issues

"""


import sys

import logging

from logger import setup_logger


logger = setup_logger(__name__)


# Configure logging to be more verbose

logging.getLogger().setLevel(logging.DEBUG)


def test_market_data_fetch():
    """Test the exact same code that trading bot uses"""

    try:

        from exchange.market_data import MarketDataClient

        from data.features import FeaturePipeline

        from utils import retry_api_call

        import pandas as pd

        logger.info("=" * 60)

        logger.info("Testing Market Data Fetch")

        logger.info("=" * 60)

        market_client = MarketDataClient(testnet=True)

        pipeline = FeaturePipeline()

        symbol = "BTCUSDT"

        # Test 1: Direct call

        logger.info("\n1. Testing direct get_kline call...")

        try:

            kline_direct = market_client.get_kline(symbol=symbol, interval="60", limit=500)

            logger.info(f"   Direct call SUCCESS: retCode={kline_direct.get('retCode')}")

            if kline_direct.get("retCode") != 0:

                logger.error(f"   ERROR MSG: {kline_direct.get('retMsg')}")

        except Exception as e:

            logger.error(f"   Direct call FAILED: {e}", exc_info=True)

        # Test 2: Via retry_api_call (like trading bot does)

        logger.info("\n2. Testing via retry_api_call...")

        try:

            kline_retry = retry_api_call(

                market_client.get_kline, symbol, interval="60", limit=500, max_retries=2

            )

            if kline_retry:

                logger.info(f"   retry_api_call SUCCESS: retCode={kline_retry.get('retCode')}")

                if kline_retry.get("retCode") != 0:

                    logger.error(f"   ERROR MSG: {kline_retry.get('retMsg')}")

            else:

                logger.error("   retry_api_call returned None")

        except Exception as e:

            logger.error(f"   retry_api_call FAILED: {e}", exc_info=True)

        # Test 3: Build features

        if kline_direct and kline_direct.get("retCode") == 0:

            logger.info("\n3. Testing feature pipeline...")

            try:

                candles = kline_direct.get("result", {}).get("list", [])

                if candles:

                    df = pd.DataFrame(

                        candles,

                        columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"],

                    )

                    for col in ["open", "high", "low", "close", "volume"]:

                        df[col] = df[col].astype(float)

                    df = df.sort_values("timestamp").reset_index(drop=True)

                    logger.info(f"   DataFrame shape: {df.shape}")

                    logger.info(f"   Columns: {df.columns.tolist()}")

                    # Build features

                    df_with_features = pipeline.build_features(df)

                    logger.info(f"   Features added, new shape: {df_with_features.shape}")

                    logger.info(f"   New columns: {df_with_features.columns.tolist()}")

                    # Check if we have required columns for strategies

                    required = ["adx", "ema_20", "ema_50", "atr", "rsi", "vwap"]

                    missing = [col for col in required if col not in df_with_features.columns]

                    if missing:

                        logger.warning(f"   Missing columns for strategies: {missing}")

                    else:

                        logger.info("   All required strategy columns present!")

                else:

                    logger.error("   No candles in response")

            except Exception as e:

                logger.error(f"   Feature pipeline FAILED: {e}", exc_info=True)

        logger.info("\n" + "=" * 60)

        logger.info("Test Complete")

        logger.info("=" * 60)

        return 0

    except Exception as e:

        logger.error(f"Test script failed: {e}", exc_info=True)

        return 1


if __name__ == "__main__":

    sys.exit(test_market_data_fetch())
