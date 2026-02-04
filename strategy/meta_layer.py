"""
Meta Layer: управление стратегиями, режимами рынка, арбитраж сигналов.

Компоненты:
1. Regime Switcher - определяет режим рынка
2. Signal Arbitration - приоритизирует конфликтующие сигналы
3. No-Trade Zones - блокирует торговлю при плохих условиях
4. Multi-timeframe confluence - проверяет согласованность на разных ТФ
"""

from typing import List, Dict, Any, Optional
import pandas as pd
from strategy.base_strategy import BaseStrategy
from data.timeframe_cache import TimeframeCache
from logger import setup_logger

logger = setup_logger(__name__)


class RegimeSwitcher:
    """Определение режима рынка"""

    @staticmethod
    def detect_regime(df: pd.DataFrame) -> str:
        """
        Определить текущий режим рынка.

        Returns:
            "trend_up" | "trend_down" | "range" | "high_vol"
        """
        latest = df.iloc[-1]

        # ADX для силы тренда
        adx = latest.get("ADX_14", 0)

        # Volatility regime
        vol_regime = latest.get("vol_regime", 0)

        # EMA для направления
        ema_20 = latest.get("ema_20", 0)
        ema_50 = latest.get("ema_50", 0)

        # Высокая волатильность - особый режим
        if vol_regime == 1:
            return "high_vol"

        # Сильный тренд (ADX > 25)
        if adx > 25:
            if ema_20 > ema_50:
                return "trend_up"
            else:
                return "trend_down"

        # Слабый тренд = диапазон
        return "range"


class SignalArbitrator:
    """Арбитраж конфликтующих сигналов"""

    @staticmethod
    def arbitrate_signals(signals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Выбрать лучший сигнал из списка.

        Правила:
        1. Если только один - берём его
        2. Если несколько в одну сторону - берём с макс. confidence
        3. Если противоречащие - блокируем все

        Args:
            signals: Список сигналов от разных стратегий

        Returns:
            Выбранный сигнал или None
        """
        if not signals:
            return None

        if len(signals) == 1:
            return signals[0]

        # Группируем по направлению
        long_signals = [s for s in signals if s["signal"] == "long"]
        short_signals = [s for s in signals if s["signal"] == "short"]
        close_signals = [s for s in signals if s["signal"] == "close"]

        # Конфликт: есть и long и short
        if long_signals and short_signals:
            logger.warning("Signal conflict: both long and short signals present - blocking all")
            return None

        # Выбираем лучший из одного направления
        if long_signals:
            best = max(long_signals, key=lambda s: s["confidence"])
            logger.info(
                f"Selected LONG signal: {best['reason']} (confidence={best['confidence']:.2f})"
            )
            return best

        if short_signals:
            best = max(short_signals, key=lambda s: s["confidence"])
            logger.info(
                f"Selected SHORT signal: {best['reason']} (confidence={best['confidence']:.2f})"
            )
            return best

        if close_signals:
            return close_signals[0]

        return None


class NoTradeZones:
    """Проверка условий для запрета торговли"""

    @staticmethod
    def is_trading_allowed(
        df: pd.DataFrame, features: Dict[str, Any], error_count: int = 0
    ) -> tuple[bool, Optional[str]]:
        """
        Проверить, разрешена ли торговля.

        Returns:
            (allowed: bool, reason: str or None)
        """
        latest = df.iloc[-1]

        # 1. Аномалия данных
        has_anomaly = latest.get("has_anomaly", 0)
        if has_anomaly == 1:
            return False, "Data anomaly detected"

        # 2. Плохая ликвидность (широкий спред)
        spread_percent = features.get("spread_percent", 0)
        if spread_percent > 2.0:  # Спред > 2% (смягчено с 1%)
            return False, f"Excessive spread: {spread_percent:.2f}%"

        # 3. Низкая глубина стакана
        depth_imbalance = features.get("depth_imbalance", 0)
        if abs(depth_imbalance) > 0.9:  # Сильный дисбаланс (смягчено с 0.8)
            return False, f"Orderbook imbalance: {depth_imbalance:.2f}"

        # 4. Серия ошибок (передаётся извне)
        if error_count > 5:  # Смягчено с 3
            return False, f"Too many errors: {error_count}"

        # 5. Экстремальная волатильность
        vol_regime = latest.get("vol_regime", 0)
        atr_percent = latest.get("atr_percent", 0)
        if vol_regime == 1 and atr_percent > 10.0:  # ATR > 10% (смягчено с 5%)
            return False, f"Extreme volatility: ATR={atr_percent:.2f}%"

        return True, None


class MetaLayer:
    """Центральный мета-слой для управления стратегиями"""

    def __init__(self, strategies: List[BaseStrategy], use_mtf: bool = True):
        """
        Args:
            strategies: Список стратегий
            use_mtf: Использовать multi-timeframe confluence checks
        """
        self.strategies = strategies
        self.regime_switcher = RegimeSwitcher()
        self.arbitrator = SignalArbitrator()
        self.no_trade_zones = NoTradeZones()
        self.use_mtf = use_mtf
        self.timeframe_cache = TimeframeCache() if use_mtf else None

        logger.info(f"MetaLayer initialized with {len(strategies)} strategies (MTF: {use_mtf})")

    def get_signal(
        self, df: pd.DataFrame, features: Dict[str, Any], error_count: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        Получить финальный торговый сигнал.

        Args:
            df: DataFrame с данными и признаками
            features: Дополнительные признаки
            error_count: Количество недавних ошибок

        Returns:
            Финальный сигнал или None
        """
        # 1. No-trade zones
        trading_allowed, block_reason = self.no_trade_zones.is_trading_allowed(
            df, features, error_count
        )
        if not trading_allowed:
            # Убрали логирование каждой блокировки для чистоты вывода
            return None

        # 2. Определяем режим рынка
        regime = self.regime_switcher.detect_regime(df)
        # Логируем только при смене режима

        # 3. Включаем/выключаем стратегии по режиму
        self._adjust_strategies_by_regime(regime)

        # 4. Собираем сигналы от всех активных стратегий
        signals = []
        for strategy in self.strategies:
            if strategy.is_enabled:
                signal = strategy.generate_signal(df, features)
                if signal:
                    signal["strategy"] = strategy.name
                    signals.append(signal)
                    logger.info(
                        f"Signal from {strategy.name}: {signal['signal']} "
                        f"(conf={signal['confidence']:.2f})"
                    )

        # 5. Арбитраж сигналов
        final_signal = self.arbitrator.arbitrate_signals(signals)

        if final_signal:
            final_signal["regime"] = regime

            # 6. Multi-timeframe confluence check (опционально)
            if self.use_mtf and self.timeframe_cache:
                # Получаем данные из кэша
                df_1m = self.timeframe_cache.get_latest("1")
                df_5m = self.timeframe_cache.get_latest("5")
                df_15m = self.timeframe_cache.get_latest("15")

                # Проверяем согласованность
                if not self.timeframe_cache.check_confluence(df_1m, df_5m, df_15m):
                    logger.info("Signal rejected: No MTF confluence")
                    return None

                final_signal["mtf_confirmed"] = True

        return final_signal

    def update_timeframe_data(self, timeframe: str, candle: Dict[str, Any]) -> None:
        """
        Обновить данные таймфрейма в кэше.

        Args:
            timeframe: Таймфрейм (1, 5, 15, 60, 240, D)
            candle: Данные свечи
        """
        if self.use_mtf and self.timeframe_cache:
            self.timeframe_cache.add_candle(timeframe, candle)

    def _adjust_strategies_by_regime(self, regime: str):
        """Включить/выключить стратегии в зависимости от режима"""
        for strategy in self.strategies:
            # TrendPullback - только в трендах
            if strategy.name == "TrendPullback":
                if regime in ["trend_up", "trend_down"]:
                    strategy.enable()
                else:
                    strategy.disable()

            # Breakout - лучше работает в диапазонах
            elif strategy.name == "Breakout":
                if regime == "range":
                    strategy.enable()
                else:
                    strategy.disable()

            # MeanReversion - ТОЛЬКО при низкой волатильности
            elif strategy.name == "MeanReversion":
                if regime == "range":  # И vol_regime == -1 проверяется внутри стратегии
                    strategy.enable()
                else:
                    strategy.disable()
