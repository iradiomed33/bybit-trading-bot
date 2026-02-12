"""
TASK-005: StrategyBuilder — создаёт стратегии с параметрами из конфига

Вместо hardcoded TrendPullbackStrategy(), использует конфиг для:
- Выбора активных стратегий
- Передачи параметров в конструкторы
- Логирования использованных параметров
"""

from typing import List, Dict, Any
from logger import setup_logger
from config.settings import ConfigManager

logger = setup_logger(__name__)


class StrategyBuilder:
    """Фабрика для создания стратегий с параметрами из конфига"""
    
    def __init__(self, config: ConfigManager):
        """
        Args:
            config: ConfigManager с загруженным bot_settings.json
        """
        self.config = config
    
    def build_strategies(self) -> List:
        """
        Создаёт стратегии на основе конфига.
        
        Returns:
            Список экземпляров стратегий
            
        Example:
            config = ConfigManager()
            builder = StrategyBuilder(config)
            strategies = builder.build_strategies()
        """
        
        strategies = []
        active_strategies = self.config.get("trading.active_strategies", [])
        
        logger.info("="*70)
        logger.info("Building strategies from config")
        logger.info("="*70)
        logger.info(f"Active strategies: {active_strategies}")
        
        # TrendPullback Strategy
        if "TrendPullback" in active_strategies:
            try:
                strat = self._build_trend_pullback()
                strategies.append(strat)
                logger.info(f"✓ TrendPullback added")
            except Exception as e:
                logger.error(f"Failed to build TrendPullback: {e}")
                raise
        
        # Breakout Strategy
        if "Breakout" in active_strategies:
            try:
                strat = self._build_breakout()
                strategies.append(strat)
                logger.info(f"✓ Breakout added")
            except Exception as e:
                logger.error(f"Failed to build Breakout: {e}")
                raise
        
        # Mean Reversion Strategy
        if "MeanReversion" in active_strategies:
            try:
                strat = self._build_mean_reversion()
                strategies.append(strat)
                logger.info(f"✓ MeanReversion added")
            except Exception as e:
                logger.error(f"Failed to build MeanReversion: {e}")
                raise
        
        logger.info("="*70)
        logger.info(f"Built {len(strategies)} strategies")
        logger.info("="*70)
        
        if not strategies:
            logger.warning("No strategies configured!")
        
        return strategies
    
    def _build_trend_pullback(self):
        """Создаёт TrendPullbackStrategy с параметрами из конфига"""
        
        from strategy.trend_pullback import TrendPullbackStrategy
        
        # Get params from config or use defaults
        config_key = "strategies.TrendPullback"
        
        min_adx = self.config.get(f"{config_key}.min_adx", 15.0)
        pullback_percent = self.config.get(f"{config_key}.pullback_percent", 0.5)
        confidence_threshold = self.config.get(f"{config_key}.confidence_threshold", 0.35)
        min_candles = self.config.get(f"{config_key}.min_candles", 15)
        lookback = self.config.get(f"{config_key}.lookback", 20)
        
        # Optional STR-002 params
        enable_liquidation_filter = self.config.get(
            f"{config_key}.enable_liquidation_filter", True
        )
        liquidation_cooldown_bars = self.config.get(
            f"{config_key}.liquidation_cooldown_bars", 3
        )
        liquidation_atr_multiplier = self.config.get(
            f"{config_key}.liquidation_atr_multiplier", 2.5
        )
        liquidation_wick_ratio = self.config.get(
            f"{config_key}.liquidation_wick_ratio", 0.7
        )
        liquidation_volume_pctl = self.config.get(
            f"{config_key}.liquidation_volume_pctl", 95.0
        )
        
        # STR-003 params
        entry_mode = self.config.get(f"{config_key}.entry_mode", "confirm_close")
        limit_ttl_bars = self.config.get(f"{config_key}.limit_ttl_bars", 3)
        
        # Configurable entry zone and volume thresholds
        entry_zone_atr_low = self.config.get(f"{config_key}.entry_zone_atr_low", -0.5)
        entry_zone_atr_high = self.config.get(f"{config_key}.entry_zone_atr_high", 0.2)
        volume_z_threshold = self.config.get(f"{config_key}.volume_z_threshold", 1.0)
        
        logger.info(f"\n  [TrendPullback Config]")
        logger.info(f"    min_adx: {min_adx}")
        logger.info(f"    pullback_percent: {pullback_percent}")
        logger.info(f"    confidence_threshold: {confidence_threshold}")
        logger.info(f"    min_candles: {min_candles}")
        logger.info(f"    lookback: {lookback}")
        logger.info(f"    enable_liquidation_filter: {enable_liquidation_filter}")
        logger.info(f"    entry_mode: {entry_mode}")
        logger.info(f"    entry_zone: [{entry_zone_atr_low}, {entry_zone_atr_high}] ATRs")
        logger.info(f"    volume_z_threshold: {volume_z_threshold}")
        
        strategy = TrendPullbackStrategy(
            min_adx=float(min_adx),
            pullback_percent=float(pullback_percent),
            enable_liquidation_filter=bool(enable_liquidation_filter),
            liquidation_cooldown_bars=int(liquidation_cooldown_bars),
            liquidation_atr_multiplier=float(liquidation_atr_multiplier),
            liquidation_wick_ratio=float(liquidation_wick_ratio),
            liquidation_volume_pctl=float(liquidation_volume_pctl),
            entry_mode=str(entry_mode),
            limit_ttl_bars=int(limit_ttl_bars),
            entry_zone_atr_low=float(entry_zone_atr_low),
            entry_zone_atr_high=float(entry_zone_atr_high),
            volume_z_threshold=float(volume_z_threshold),
        )
        
        # Store config for later access (e.g., in MetaLayer)
        strategy.confidence_threshold = float(confidence_threshold)
        strategy.min_candles = int(min_candles)
        strategy.lookback = int(lookback)
        
        return strategy
    
    def _build_breakout(self):
        """Создаёт BreakoutStrategy с параметрами из конфига"""
        
        from strategy.breakout import BreakoutStrategy
        
        config_key = "strategies.Breakout"
        
        # Core params
        bb_width_threshold = self.config.get(f"{config_key}.bb_width_threshold", 0.02)
        min_volume_zscore = self.config.get(f"{config_key}.min_volume_zscore", 1.5)
        min_atr_percent_expansion = self.config.get(f"{config_key}.min_atr_percent_expansion", 1.2)
        
        # STR-007 params
        breakout_entry = self.config.get(f"{config_key}.breakout_entry", "instant")
        retest_ttl_bars = self.config.get(f"{config_key}.retest_ttl_bars", 3)
        
        # STR-006 squeeze/expansion params
        require_squeeze = self.config.get(f"{config_key}.require_squeeze", True)
        require_expansion = self.config.get(f"{config_key}.require_expansion", True)
        require_volume = self.config.get(f"{config_key}.require_volume", True)
        
        # Meta params
        confidence_threshold = self.config.get(f"{config_key}.confidence_threshold", 0.35)
        min_candles = self.config.get(f"{config_key}.min_candles", 10)
        
        logger.info(f"\n  [Breakout Config]")
        logger.info(f"    bb_width_threshold: {bb_width_threshold}")
        logger.info(f"    min_volume_zscore: {min_volume_zscore}")
        logger.info(f"    min_atr_percent_expansion: {min_atr_percent_expansion}")
        logger.info(f"    breakout_entry: {breakout_entry}")
        logger.info(f"    require_squeeze: {require_squeeze}")
        logger.info(f"    require_expansion: {require_expansion}")
        logger.info(f"    confidence_threshold: {confidence_threshold}")
        
        strategy = BreakoutStrategy(
            bb_width_threshold=float(bb_width_threshold),
            min_volume_zscore=float(min_volume_zscore),
            min_atr_percent_expansion=float(min_atr_percent_expansion),
            breakout_entry=str(breakout_entry),
            retest_ttl_bars=int(retest_ttl_bars),
            require_squeeze=bool(require_squeeze),
            require_expansion=bool(require_expansion),
            require_volume=bool(require_volume),
        )
        
        # Store config for later access
        strategy.confidence_threshold = float(confidence_threshold)
        strategy.min_candles = int(min_candles)
        
        return strategy
    
    def _build_mean_reversion(self):
        """Создаёт MeanReversionStrategy с параметрами из конфига"""
        
        from strategy.mean_reversion import MeanReversionStrategy
        
        config_key = "strategies.MeanReversion"
        
        # Core params
        vwap_distance_threshold = self.config.get(f"{config_key}.vwap_distance_threshold", 2.0)
        rsi_oversold = self.config.get(f"{config_key}.rsi_oversold", 30.0)
        rsi_overbought = self.config.get(f"{config_key}.rsi_overbought", 70.0)
        max_adx_for_entry = self.config.get(f"{config_key}.max_adx_for_entry", 25.0)
        
        # STR-004/005 params
        require_range_regime = self.config.get(f"{config_key}.require_range_regime", True)
        enable_anti_knife = self.config.get(f"{config_key}.enable_anti_knife", True)
        adx_spike_threshold = self.config.get(f"{config_key}.adx_spike_threshold", 5.0)
        atr_spike_threshold = self.config.get(f"{config_key}.atr_spike_threshold", 0.5)
        max_hold_bars = self.config.get(f"{config_key}.max_hold_bars", 20)
        stop_loss_atr_multiplier = self.config.get(f"{config_key}.stop_loss_atr_multiplier", 1.0)
        
        # Meta params
        confidence_threshold = self.config.get(f"{config_key}.confidence_threshold", 0.3)
        min_candles = self.config.get(f"{config_key}.min_candles", 15)
        
        logger.info(f"\n  [MeanReversion Config]")
        logger.info(f"    vwap_distance_threshold: {vwap_distance_threshold}")
        logger.info(f"    rsi_oversold: {rsi_oversold}")
        logger.info(f"    rsi_overbought: {rsi_overbought}")
        logger.info(f"    max_adx_for_entry: {max_adx_for_entry}")
        logger.info(f"    require_range_regime: {require_range_regime}")
        logger.info(f"    max_hold_bars: {max_hold_bars}")
        logger.info(f"    confidence_threshold: {confidence_threshold}")
        
        strategy = MeanReversionStrategy(
            vwap_distance_threshold=float(vwap_distance_threshold),
            rsi_oversold=float(rsi_oversold),
            rsi_overbought=float(rsi_overbought),
            max_adx_for_entry=float(max_adx_for_entry),
            require_range_regime=bool(require_range_regime),
            enable_anti_knife=bool(enable_anti_knife),
            adx_spike_threshold=float(adx_spike_threshold),
            atr_spike_threshold=float(atr_spike_threshold),
            max_hold_bars=int(max_hold_bars),
            stop_loss_atr_multiplier=float(stop_loss_atr_multiplier),
        )
        
        # Store config for later access
        strategy.confidence_threshold = float(confidence_threshold)
        strategy.min_candles = int(min_candles)
        
        return strategy
    
    def get_strategy_params_summary(self) -> Dict[str, Any]:
        """Получить сводку по параметрам стратегий"""
        
        summary = {
            "active_strategies": self.config.get("trading.active_strategies", []),
        }
        
        # Collect all strategy params
        for strategy_name in ["TrendPullback", "Breakout", "MeanReversion"]:
            config_prefix = f"strategies.{strategy_name}"
            summary[strategy_name] = {}
            
            # Get all keys for this strategy
            strategy_config = self.config.get(f"strategies.{strategy_name}", {})
            if isinstance(strategy_config, dict):
                summary[strategy_name] = strategy_config
        
        return summary


def create_strategies_from_config(config_path: str = None) -> List:
    """
    Convenience function для создания стратегий из конфига.
    
    Args:
        config_path: Путь к bot_settings.json (опционально)
        
    Returns:
        Список стратегий
        
    Example:
        strategies = create_strategies_from_config()
        bot = TradingBot(mode="paper", strategies=strategies)
    """
    
    config = ConfigManager(config_path)
    builder = StrategyBuilder(config)
    return builder.build_strategies()
