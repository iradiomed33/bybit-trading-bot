"""

Mean Reversion Strategy (только при низкой волатильности)


Логика:

1. Проверяем режим волатильности (должен быть LOW)

2. Цена отклонилась от VWAP/SMA

3. RSI в зоне перепроданности/перекупленности

4. Вход на возврат к среднему с tight stop

"""


from typing import Dict, Any, Optional

import pandas as pd

from strategy.base_strategy import BaseStrategy

from strategy.meta_layer import RegimeSwitcher

from logger import setup_logger

from signal_logger import get_signal_logger


logger = setup_logger(__name__)

signal_logger = get_signal_logger()


class MeanReversionStrategy(BaseStrategy):

    """Стратегия возврата к среднему (только при низкой волатильности)"""

    def __init__(

        self,

        vwap_distance_threshold: float = 2.0,

        rsi_oversold: float = 30.0,

        rsi_overbought: float = 70.0,

        max_adx_for_entry: float = 25.0,  # Запрет входа при ADX > 25 (сильный тренд)

        # STR-004: Range mode filter

        require_range_regime: bool = True,

        # STR-004: Anti-knife filter (резкий рост ADX/ATR)

        enable_anti_knife: bool = True,

        adx_spike_threshold: float = 5.0,  # Рост ADX за 3 бара

        atr_spike_threshold: float = 0.5,  # Рост ATR slope

        # STR-005: Time-based exit and hard stop

        max_hold_bars: int = 20,  # Максимум баров удержания позиции

        max_hold_minutes: Optional[

            int

        ] = None,  # Максимум минут (если None, используем max_hold_bars)

        stop_loss_atr_multiplier: float = 1.0,  # Жёсткий стоп = k * ATR от entry

    ):
        """

        Args:

            vwap_distance_threshold: Мин. отклонение от VWAP (%)

            rsi_oversold: RSI уровень перепроданности

            rsi_overbought: RSI уровень перекупленности

            max_adx_for_entry: Максимальный ADX для допуска входа (защита от тренда)

            require_range_regime: STR-004: Требовать range режим (по умолчанию True)

            enable_anti_knife: STR-004: Блокировать при резком росте ADX/ATR

            adx_spike_threshold: Макс. рост ADX за 3 бара для anti-knife

            atr_spike_threshold: Макс. ATR slope для anti-knife

            max_hold_bars: STR-005: Максимальное количество баров удержания позиции

            max_hold_minutes: STR-005: Максимальное время удержания (минуты, опционально)

            stop_loss_atr_multiplier: STR-005: Множитель ATR для жёсткого стопа

        """

        super().__init__("MeanReversion")

        self.vwap_distance_threshold = vwap_distance_threshold

        self.rsi_oversold = rsi_oversold

        self.rsi_overbought = rsi_overbought

        self.max_adx_for_entry = max_adx_for_entry

        # STR-004

        self.require_range_regime = require_range_regime

        self.enable_anti_knife = enable_anti_knife

        self.adx_spike_threshold = adx_spike_threshold

        self.atr_spike_threshold = atr_spike_threshold

        # STR-005

        self.max_hold_bars = max_hold_bars

        self.max_hold_minutes = max_hold_minutes

        self.stop_loss_atr_multiplier = stop_loss_atr_multiplier

        # Position tracking state (STR-005)

        self._active_position: Optional[Dict[str, Any]] = None

    def _check_exit_conditions(

        self, df: pd.DataFrame, features: Dict[str, Any]

    ) -> Optional[Dict[str, Any]]:
        """

        STR-005: Check if active position should be exited.


        Returns:

            Exit signal dict if exit condition met, None otherwise

        """

        if not self._active_position:

            return None

        latest = df.iloc[-1]

        current_bar_index = len(df) - 1

        current_price = latest.get("close", 0)

        current_timestamp = latest.get("timestamp") if hasattr(latest, "timestamp") else None

        entry_price = self._active_position["entry_price"]

        entry_bar = self._active_position["entry_bar_index"]

        entry_time = self._active_position.get("entry_timestamp")

        side = self._active_position["side"]  # "long" or "short"

        atr_at_entry = self._active_position["atr"]

        mean_target = self._active_position["mean_target"]  # VWAP

        bars_held = current_bar_index - entry_bar

        symbol = features.get("symbol", "UNKNOWN")

        # Calculate PnL

        if side == "long":

            pnl_pct = ((current_price - entry_price) / entry_price) * 100

        else:  # short

            pnl_pct = ((entry_price - current_price) / entry_price) * 100

        # Check 1: Time limit (bars)

        if bars_held >= self.max_hold_bars:

            logger.info(

                f"[STR-005] {self.name} TIME_STOP: bars_held={bars_held} >= max={self.max_hold_bars} | "

                f"Symbol={symbol} | PnL={pnl_pct:.2f}%"

            )

            return self._create_exit_signal(

                exit_reason="time_stop",

                current_price=current_price,

                bars_held=bars_held,

                pnl_pct=pnl_pct,

                symbol=symbol,

            )

        # Check 2: Time limit (minutes) if configured

        if self.max_hold_minutes and entry_time and current_timestamp:

            try:

                if hasattr(current_timestamp, "timestamp"):

                    current_ts = current_timestamp.timestamp()

                    entry_ts = entry_time.timestamp()

                else:

                    current_ts = float(current_timestamp)

                    entry_ts = float(entry_time)

                minutes_held = (current_ts - entry_ts) / 60.0

                if minutes_held >= self.max_hold_minutes:

                    logger.info(

                        f"[STR-005] {self.name} TIME_STOP: minutes_held={minutes_held:.1f} >= max={self.max_hold_minutes} | "

                        f"Symbol={symbol} | PnL={pnl_pct:.2f}%"

                    )

                    return self._create_exit_signal(

                        exit_reason="time_stop",

                        current_price=current_price,

                        bars_held=bars_held,

                        minutes_held=minutes_held,

                        pnl_pct=pnl_pct,

                        symbol=symbol,

                    )

            except Exception as e:

                logger.debug(f"[STR-005] Could not calculate minutes_held: {e}")

        # Check 3: Hard stop loss (k * ATR from entry)

        stop_distance = self.stop_loss_atr_multiplier * atr_at_entry

        if side == "long":

            stop_price = entry_price - stop_distance

            stop_hit = current_price <= stop_price

        else:  # short

            stop_price = entry_price + stop_distance

            stop_hit = current_price >= stop_price

        if stop_hit:

            logger.info(

                f"[STR-005] {self.name} STOP_LOSS: price={current_price:.2f} hit stop={stop_price:.2f} | "

                f"Side={side} | Symbol={symbol} | PnL={pnl_pct:.2f}%"

            )

            return self._create_exit_signal(

                exit_reason="stop_loss",

                current_price=current_price,

                bars_held=bars_held,

                pnl_pct=pnl_pct,

                stop_price=stop_price,

                symbol=symbol,

            )

        # Check 4: Take profit (price returned to mean)

        # For LONG: entered below VWAP, exit when price >= VWAP

        # For SHORT: entered above VWAP, exit when price <= VWAP

        mean_tolerance = 0.001  # 0.1% tolerance to avoid whipsaws

        if side == "long":

            target_hit = current_price >= mean_target * (1 - mean_tolerance)

        else:  # short

            target_hit = current_price <= mean_target * (1 + mean_tolerance)

        if target_hit:

            logger.info(

                f"[STR-005] {self.name} TAKE_PROFIT: price={current_price:.2f} reached mean={mean_target:.2f} | "

                f"Side={side} | Symbol={symbol} | PnL={pnl_pct:.2f}%"

            )

            return self._create_exit_signal(

                exit_reason="take_profit",

                current_price=current_price,

                bars_held=bars_held,

                pnl_pct=pnl_pct,

                mean_target=mean_target,

                symbol=symbol,

            )

        return None

    def _create_exit_signal(

        self,

        exit_reason: str,

        current_price: float,

        bars_held: int,

        pnl_pct: float,

        symbol: str,

        **kwargs,

    ) -> Dict[str, Any]:
        """

        Create exit signal and reset position tracking.


        Args:

            exit_reason: "time_stop", "stop_loss", or "take_profit"

            current_price: Current market price

            bars_held: Number of bars position was held

            pnl_pct: Profit/loss percentage

            symbol: Trading symbol

            **kwargs: Additional metadata

        """

        side = self._active_position["side"]

        # Log structured exit with [STR-005] tag

        logger.info(

            f"[STR-005] {self.name} EXIT: {exit_reason.upper()} | "

            f"Symbol={symbol} | Side={side} | Entry={self._active_position['entry_price']:.2f} | "

            f"Exit={current_price:.2f} | Bars={bars_held} | PnL={pnl_pct:.2f}%"

        )

        # Also log via signal_logger for detailed tracking

        signal_logger.log_signal_generated(

            strategy_name=self.name,

            symbol=symbol,

            direction="CLOSE_LONG" if side == "long" else "CLOSE_SHORT",

            confidence=1.0,

            price=current_price,

            reasons=[exit_reason, f"bars_held={bars_held}", f"pnl={pnl_pct:.2f}%"],

            values={

                "exit_reason": exit_reason,

                "side": side,

                "entry_price": self._active_position["entry_price"],

                "exit_price": current_price,

                "bars_held": bars_held,

                "pnl_pct": round(pnl_pct, 2),

                **kwargs,

            },

        )

        # Reset position tracking

        self._active_position = None

        return {

            "signal": "exit",

            "side": side,

            "exit_reason": exit_reason,

            "exit_price": current_price,

            "bars_held": bars_held,

            "pnl_pct": round(pnl_pct, 2),

            "confidence": 1.0,

            "metadata": {"exit_reason": exit_reason, **kwargs},

        }

    def generate_signal(

        self, df: pd.DataFrame, features: Dict[str, Any]

    ) -> Optional[Dict[str, Any]]:
        """Генерация сигнала"""

        if not self.is_enabled:

            return None

        latest = df.iloc[-1]

        symbol = features.get("symbol", "UNKNOWN")

        # STR-005: Check exit conditions FIRST if we have an active position

        exit_signal = self._check_exit_conditions(df, features)

        if exit_signal:

            return exit_signal

        # Get vol_regime early (needed for values dict later)

        vol_regime = latest.get("vol_regime", 0)

        # STR-004: Жесткая проверка режима - только range!

        if self.require_range_regime:

            regime = RegimeSwitcher.detect_regime(df)
            
            # Проверка на frozen data (нет движения цены)
            import math
            adx = latest.get("adx", 0)
            is_frozen_data = (
                regime == "unknown" and 
                (adx is None or (isinstance(adx, float) and math.isnan(adx)))
            )
            
            if is_frozen_data:
                # Замороженные данные - пропускаем без WARNING
                logger.debug(
                    f"[STR-004] {self.name} skipped: frozen data detected (ADX=nan, regime=unknown) | "
                    f"Symbol={symbol}"
                )
                return None

            signal_logger.log_filter_check(

                filter_name="Regime Filter (STR-004)",

                symbol=symbol,

                passed=(regime == "range"),

                value=regime,

                threshold="range",

            )

            if regime != "range":

                logger.info(

                    f"[STR-004] {self.name} rejected: regime={regime} (only 'range' allowed) | "

                    f"Symbol={symbol}"

                )

                return None

            logger.info(f"[STR-004] {self.name}: regime=range ✓ | Symbol={symbol}")

        # STR-004: Anti-knife filter - блокировать при резком росте ADX/ATR

        if self.enable_anti_knife and len(df) >= 4:

            adx_current = latest.get("adx", 0)

            adx_3bars_ago = df.iloc[-4].get("adx", 0) if len(df) >= 4 else adx_current

            adx_spike = adx_current - adx_3bars_ago

            atr_slope = latest.get("atr_slope", 0)

            is_knife = (adx_spike > self.adx_spike_threshold) or (

                atr_slope > self.atr_spike_threshold

            )

            signal_logger.log_filter_check(

                filter_name="Anti-Knife Filter (STR-004)",

                symbol=symbol,

                passed=not is_knife,

                value={"adx_spike": round(adx_spike, 2), "atr_slope": round(atr_slope, 2)},

                threshold=f"ADX_spike<{self.adx_spike_threshold}, ATR_slope<{self.atr_spike_threshold}",

            )

            if is_knife:

                logger.warning(

                    f"[STR-004] {self.name} rejected: anti_knife_triggered | "

                    f"ADX_spike={adx_spike:.2f} (threshold={self.adx_spike_threshold}), "

                    f"ATR_slope={atr_slope:.2f} (threshold={self.atr_spike_threshold}) | "

                    f"Symbol={symbol}"

                )

                return None

        # 1. Старый фильтр волатильности (для обратной совместимости, если require_range_regime=False)

        if not self.require_range_regime:

            vol_regime = latest.get("vol_regime", 0)

            if vol_regime != -1:  # -1 = low volatility

                logger.debug(

                    f"{self.name}: Rejected - vol_regime={vol_regime} (only -1/low allowed)"

                )

                return None

        # 2. Фильтр тренда: запрет на вход против сильного тренда (ADX > 25)

        adx = latest.get("adx", latest.get("ADX_14", 0))  # Fallback compatibility

        if adx > self.max_adx_for_entry:

            logger.debug(

                f"{self.name}: Rejected - trend_too_strong (ADX={adx:.2f} > {self.max_adx_for_entry})"

            )

            return None

        # 3. Проверка направления EMA (не входим сильно против тренда)

        ema_20 = latest.get("ema_20", 0)

        ema_50 = latest.get("ema_50", 0)

        close = latest["close"]

        # 4. Проверка отклонения от VWAP

        vwap_distance = latest.get("vwap_distance", 0)

        rsi = latest.get("rsi", 50)

        vwap = latest.get("vwap", close)

        # Long: цена сильно ниже VWAP, RSI перепродан, и не слишком сильный downtrend

        if vwap_distance < -self.vwap_distance_threshold and rsi < self.rsi_oversold:

            # Дополнительный фильтр: не входим если цена слишком далеко ниже EMA50

            if close < ema_50 * 0.95:  # Цена более чем на 5% ниже EMA50 = сильный downtrend

                logger.debug(

                    f"{self.name}: Rejected - price_too_far_below_ema50 "

                    f"(close={close:.2f} < ema50*0.95={ema_50 * 0.95:.2f})"

                )

                return None

            atr = latest.get("atr", 0)

            stop_loss = close - (1.0 * atr)  # Tight stop

            take_profit = vwap  # Цель = возврат к VWAP

            reasons = [

                "range_regime",  # STR-004

                "anti_knife_passed",  # STR-004

                "trend_not_too_strong",

                "vwap_distance_ok",

                "rsi_oversold",

                "ema50_distance_ok",

            ]

            values = {

                "vwap_distance": round(vwap_distance, 2),

                "rsi": round(rsi, 2),

                "adx": round(adx, 2),

                "vol_regime": vol_regime,

                "ema_20": round(ema_20, 2),

                "ema_50": round(ema_50, 2),

                "atr": round(atr, 4),

                "close": round(close, 2),

                "vwap": round(vwap, 2),

            }

            # STR-005: Track position for exit monitoring

            self._active_position = {

                "side": "long",

                "entry_price": close,

                "entry_bar_index": len(df) - 1,

                "entry_timestamp": (

                    latest.get("timestamp") if hasattr(latest, "timestamp") else None

                ),

                "atr": atr,

                "mean_target": vwap,

            }

            return {

                "signal": "long",

                "confidence": 0.6,  # Ниже чем у трендовых

                "entry_price": close,

                "stop_loss": stop_loss,

                "take_profit": take_profit,

                "reasons": reasons,

                "values": values,

                "reason": "; ".join(reasons),

                "metadata": values,

            }

        # Short: цена сильно выше VWAP, RSI перекуплен, и не слишком сильный uptrend

        if vwap_distance > self.vwap_distance_threshold and rsi > self.rsi_overbought:

            # Дополнительный фильтр: не входим если цена слишком далеко выше EMA50

            if close > ema_50 * 1.05:  # Цена более чем на 5% выше EMA50 = сильный uptrend

                logger.debug(

                    f"{self.name}: Rejected - price_too_far_above_ema50 "

                    f"(close={close:.2f} > ema50*1.05={ema_50 * 1.05:.2f})"

                )

                return None

            atr = latest.get("atr", 0)

            stop_loss = close + (1.0 * atr)

            take_profit = vwap

            reasons = [

                "range_regime",  # STR-004

                "anti_knife_passed",  # STR-004

                "trend_not_too_strong",

                "vwap_distance_ok",

                "rsi_overbought",

                "ema50_distance_ok",

            ]

            values = {

                "vwap_distance": round(vwap_distance, 2),

                "rsi": round(rsi, 2),

                "adx": round(adx, 2),

                "vol_regime": vol_regime,

                "ema_20": round(ema_20, 2),

                "ema_50": round(ema_50, 2),

                "atr": round(atr, 4),

                "close": round(close, 2),

                "vwap": round(vwap, 2),

            }

            # STR-005: Track position for exit monitoring

            self._active_position = {

                "side": "short",

                "entry_price": close,

                "entry_bar_index": len(df) - 1,

                "entry_timestamp": (

                    latest.get("timestamp") if hasattr(latest, "timestamp") else None

                ),

                "atr": atr,

                "mean_target": vwap,

            }

            return {

                "signal": "short",

                "confidence": 0.6,

                "entry_price": close,

                "stop_loss": stop_loss,

                "take_profit": take_profit,

                "reasons": reasons,

                "values": values,

                "reason": "; ".join(reasons),

                "metadata": values,

            }

        return None
