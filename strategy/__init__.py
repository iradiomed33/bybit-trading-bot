"""

Strategy module: торговые стратегии и meta-layer

"""


from strategy.base_strategy import BaseStrategy

from strategy.trend_pullback import TrendPullbackStrategy

from strategy.breakout import BreakoutStrategy

from strategy.mean_reversion import MeanReversionStrategy

from strategy.meta_layer import MetaLayer, RegimeSwitcher, SignalArbitrator, NoTradeZones


__all__ = [

    "BaseStrategy",

    "TrendPullbackStrategy",

    "BreakoutStrategy",

    "MeanReversionStrategy",

    "MetaLayer",

    "RegimeSwitcher",

    "SignalArbitrator",

    "NoTradeZones",

]
