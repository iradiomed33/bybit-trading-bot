"""
Grid Trading Strategy

Логика:
1. Определяем торговый диапазон (автоматически или вручную)
2. Создаём сетку уровней buy/sell в этом диапазоне
3. Покупаем на нижних уровнях, продаём на верхних
4. Извлекаем прибыль из колебаний цены в диапазоне

Особенности:
- Оптимальна для бокового рынка (консолидация)
- Множественные маленькие прибыли от каждого колебания
- Риск: сильный пробой диапазона может привести к убытку
- Защита: Stop-loss за границами диапазона
"""

from typing import Dict, Any, Optional, List, Tuple
import pandas as pd
import numpy as np
from strategy.base_strategy import BaseStrategy
from logger import setup_logger

logger = setup_logger(__name__)


class GridTradingStrategy(BaseStrategy):
    """
    Стратегия сеточной торговли для диапазона консолидации.
    
    Размещает серию ордеров buy/sell на равномерных уровнях в диапазоне,
    извлекая прибыль из каждого колебания цены.
    """

    def __init__(
        self,
        # Параметры диапазона
        range_mode: str = "auto",  # "auto" или "manual"
        manual_lower: Optional[float] = None,
        manual_upper: Optional[float] = None,
        range_lookback: int = 100,  # Период для определения диапазона
        
        # Параметры сетки
        grid_levels: int = 20,  # Количество уровней в сетке
        grid_spacing_percent: float = 1.5,  # Шаг между уровнями (%)
        
        # Фильтры входа
        require_ranging_market: bool = True,  # Требовать боковое движение
        max_adx_for_range: float = 25.0,  # Максимальный ADX для бокового рынка
        min_bb_width: float = 0.015,  # Минимальная ширина BB (слишком узко = опасно)
        max_bb_width: float = 0.05,  # Максимальная ширина BB (слишком широко = тренд)
        
        # Защита от пробоя
        enable_breakout_protection: bool = True,
        breakout_volume_threshold: float = 2.0,  # Z-score объёма для подозрения на пробой
        stop_loss_atr_multiplier: float = 3.0,  # SL за границами диапазона
        
        # Управление позицией
        profit_per_grid: float = 1.5,  # Целевая прибыль на каждом уровне сетки (%)
        max_grid_positions: int = 5,  # Максимум открытых позиций одновременно
        rebalance_on_drift: bool = True,  # Пересчитывать сетку при смещении диапазона
        drift_threshold_percent: float = 10.0,  # Порог смещения для rebalance
    ):
        """
        Args:
            range_mode: Режим определения диапазона ("auto" или "manual")
            manual_lower: Нижняя граница диапазона (для manual mode)
            manual_upper: Верхняя граница диапазона (для manual mode)
            range_lookback: Период свечей для автоматического определения диапазона
            grid_levels: Количество уровней в сетке
            grid_spacing_percent: Шаг между уровнями (%)
            require_ranging_market: Требовать подтверждение бокового рынка
            max_adx_for_range: Максимальный ADX для определения range
            min_bb_width: Минимальная ширина BB
            max_bb_width: Максимальная ширина BB
            enable_breakout_protection: Включить защиту от пробоя
            breakout_volume_threshold: Z-score объёма для определения пробоя
            stop_loss_atr_multiplier: Множитель ATR для stop-loss
            profit_per_grid: Целевая прибыль на уровне сетки (%)
            max_grid_positions: Максимум открытых позиций
            rebalance_on_drift: Пересчитывать сетку при смещении
            drift_threshold_percent: Порог смещения диапазона для ребаланса
        """
        super().__init__("GridTrading")
        
        if range_mode not in ("auto", "manual"):
            raise ValueError("range_mode must be 'auto' or 'manual'")
        
        if range_mode == "manual" and (manual_lower is None or manual_upper is None):
            raise ValueError("manual mode requires manual_lower and manual_upper")
        
        self.range_mode = range_mode
        self.manual_lower = manual_lower
        self.manual_upper = manual_upper
        self.range_lookback = range_lookback
        
        self.grid_levels = grid_levels
        self.grid_spacing_percent = grid_spacing_percent
        
        self.require_ranging_market = require_ranging_market
        self.max_adx_for_range = max_adx_for_range
        self.min_bb_width = min_bb_width
        self.max_bb_width = max_bb_width
        
        self.enable_breakout_protection = enable_breakout_protection
        self.breakout_volume_threshold = breakout_volume_threshold
        self.stop_loss_atr_multiplier = stop_loss_atr_multiplier
        
        self.profit_per_grid = profit_per_grid
        self.max_grid_positions = max_grid_positions
        self.rebalance_on_drift = rebalance_on_drift
        self.drift_threshold_percent = drift_threshold_percent
        
        # Внутреннее состояние для каждого символа
        self._grid_state = {}  # symbol -> {"range": (low, high), "levels": [...]}
        
        logger.info(
            f"GridTrading initialized: mode={range_mode}, levels={grid_levels}, "
            f"spacing={grid_spacing_percent}%, range_filter={require_ranging_market}"
        )

    def generate_signal(
        self, df: pd.DataFrame, features: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Генерирует торговый сигнал на основе сеточной стратегии.
        
        Returns:
            Сигнал long/short или None если условия не выполнены
        """
        if not self.is_enabled:
            return None

        if len(df) < self.range_lookback:
            logger.debug(f"{self.name}: Insufficient data (need {self.range_lookback} bars)")
            return None

        latest = df.iloc[-1]
        symbol = features.get("symbol", "UNKNOWN")
        current_price = latest["close"]

        # 1. Проверяем условия для Grid Trading (боковой рынок)
        if not self._check_ranging_conditions(df, latest, symbol):
            return None

        # 2. Определяем или обновляем диапазон и сетку
        grid_range, grid_levels = self._calculate_grid(df, symbol, current_price)
        if grid_range is None or grid_levels is None:
            return None

        range_lower, range_upper = grid_range

        # 3. Проверяем защиту от пробоя
        if self.enable_breakout_protection:
            if self._detect_breakout_risk(df, latest, range_lower, range_upper, symbol):
                logger.info(
                    f"[GRID] {symbol}: Breakout risk detected, skipping signal | "
                    f"Price={current_price:.2f}, Range=[{range_lower:.2f}, {range_upper:.2f}]"
                )
                return None

        # 4. Определяем ближайшие уровни Grid и генерируем сигнал
        signal = self._generate_grid_signal(
            current_price, grid_levels, range_lower, range_upper, latest, df, symbol
        )

        return signal

    def _check_ranging_conditions(
        self, df: pd.DataFrame, latest: pd.Series, symbol: str
    ) -> bool:
        """
        Проверяет условия для бокового рынка (range).
        
        Returns:
            True если рынок подходит для Grid Trading
        """
        if not self.require_ranging_market:
            return True

        # Проверяем ADX (низкий ADX = боковое движение)
        adx = latest.get("ADX_14", None)
        if adx is None:
            logger.warning(f"[GRID] {symbol}: ADX not available")
            return False

        if adx > self.max_adx_for_range:
            logger.debug(
                f"[GRID] {symbol}: ADX too high for ranging market | "
                f"ADX={adx:.1f} > {self.max_adx_for_range}"
            )
            return False

        # Проверяем ширину Bollinger Bands
        bb_width = self._calculate_bb_width(df, latest)
        if bb_width is None:
            return False

        if bb_width < self.min_bb_width:
            logger.debug(
                f"[GRID] {symbol}: BB too narrow (compression risk) | "
                f"BB_Width={bb_width:.4f} < {self.min_bb_width}"
            )
            return False

        if bb_width > self.max_bb_width:
            logger.debug(
                f"[GRID] {symbol}: BB too wide (trending market) | "
                f"BB_Width={bb_width:.4f} > {self.max_bb_width}"
            )
            return False

        logger.debug(
            f"[GRID] {symbol}: Range conditions OK | ADX={adx:.1f}, BB_Width={bb_width:.4f}"
        )
        return True

    def _calculate_bb_width(self, df: pd.DataFrame, latest: pd.Series) -> Optional[float]:
        """Вычисляет относительную ширину Bollinger Bands."""
        bb_cols = [col for col in df.columns if "BBU_" in col or "BBL_" in col]
        if not bb_cols:
            logger.warning(f"{self.name}: Bollinger Bands not calculated")
            return None

        bbu_col = next((col for col in df.columns if "BBU_" in col), None)
        bbl_col = next((col for col in df.columns if "BBL_" in col), None)
        bbm_col = next((col for col in df.columns if "BBM_" in col), None)

        if bbu_col and bbl_col and bbm_col:
            bb_upper = latest.get(bbu_col, 0)
            bb_lower = latest.get(bbl_col, 0)
            bb_middle = latest.get(bbm_col, 1)
            
            if bb_middle > 0:
                bb_width = (bb_upper - bb_lower) / bb_middle
                return bb_width

        return None

    def _calculate_grid(
        self, df: pd.DataFrame, symbol: str, current_price: float
    ) -> Tuple[Optional[Tuple[float, float]], Optional[List[float]]]:
        """
        Определяет диапазон и уровни сетки.
        
        Returns:
            Tuple: ((range_lower, range_upper), [grid_levels]) или (None, None)
        """
        # Определяем диапазон
        if self.range_mode == "manual":
            range_lower = self.manual_lower
            range_upper = self.manual_upper
            logger.debug(
                f"[GRID] {symbol}: Using manual range [{range_lower:.2f}, {range_upper:.2f}]"
            )
        else:
            # Автоматическое определение диапазона
            lookback_data = df.tail(self.range_lookback)
            range_lower = lookback_data["low"].min()
            range_upper = lookback_data["high"].max()
            
            # Добавляем небольшой буфер для safety
            range_span = range_upper - range_lower
            buffer = range_span * 0.02  # 2% буфер
            range_lower -= buffer
            range_upper += buffer
            
            logger.debug(
                f"[GRID] {symbol}: Auto-detected range [{range_lower:.2f}, {range_upper:.2f}] "
                f"from {self.range_lookback} bars"
            )

        # Проверяем, нужен ли rebalance
        if symbol in self._grid_state and self.rebalance_on_drift:
            old_range = self._grid_state[symbol]["range"]
            old_lower, old_upper = old_range
            range_center_old = (old_lower + old_upper) / 2
            range_center_new = (range_lower + range_upper) / 2
            
            drift_percent = abs(range_center_new - range_center_old) / range_center_old * 100
            
            if drift_percent > self.drift_threshold_percent:
                logger.info(
                    f"[GRID] {symbol}: Range drift detected {drift_percent:.1f}%, rebalancing grid"
                )
            else:
                # Используем старый диапазон (стабильность)
                range_lower, range_upper = old_range

        # Генерируем уровни сетки
        grid_levels = self._generate_grid_levels(range_lower, range_upper, current_price)
        
        # Сохраняем состояние
        self._grid_state[symbol] = {
            "range": (range_lower, range_upper),
            "levels": grid_levels,
        }

        return (range_lower, range_upper), grid_levels

    def _generate_grid_levels(
        self, range_lower: float, range_upper: float, current_price: float
    ) -> List[float]:
        """
        Генерирует уровни сетки в диапазоне.
        
        Returns:
            Список цен уровней сетки
        """
        levels = []
        range_span = range_upper - range_lower
        
        # Вычисляем шаг сетки
        if self.grid_spacing_percent > 0:
            # Процентный шаг от текущей цены
            step = current_price * (self.grid_spacing_percent / 100)
        else:
            # Равномерное распределение уровней
            step = range_span / (self.grid_levels - 1)

        # Генерируем уровни выше и ниже текущей цены
        level = current_price
        
        # Уровни ниже (для buy)
        while level > range_lower:
            levels.append(level)
            level -= step
        
        # Уровни выше (для sell)
        level = current_price + step
        while level < range_upper:
            levels.append(level)
            level += step

        levels.sort()
        return levels

    def _detect_breakout_risk(
        self,
        df: pd.DataFrame,
        latest: pd.Series,
        range_lower: float,
        range_upper: float,
        symbol: str,
    ) -> bool:
        """
        Определяет риск пробоя диапазона.
        
        Returns:
            True если высокий риск пробоя (нужно избегать входа)
        """
        current_price = latest["close"]
        
        # Проверка 1: Цена близко к границам
        range_span = range_upper - range_lower
        proximity_threshold = range_span * 0.05  # 5% от диапазона
        
        if current_price < range_lower + proximity_threshold:
            logger.debug(f"[GRID] {symbol}: Price near lower boundary")
        elif current_price > range_upper - proximity_threshold:
            logger.debug(f"[GRID] {symbol}: Price near upper boundary")

        # Проверка 2: Высокий объём (может указывать на пробой)
        volume_z = latest.get("volume_z", 0)
        if abs(volume_z) > self.breakout_volume_threshold:
            logger.info(
                f"[GRID] {symbol}: High volume detected (breakout risk) | "
                f"Volume_Z={volume_z:.2f}"
            )
            return True

        # Проверка 3: Сильное ценовое движение
        if len(df) >= 2:
            prev_close = df.iloc[-2]["close"]
            price_change_pct = abs(current_price - prev_close) / prev_close * 100
            
            if price_change_pct > 2.0:  # >2% изменение за бар
                logger.info(
                    f"[GRID] {symbol}: Large price movement (breakout risk) | "
                    f"Change={price_change_pct:.2f}%"
                )
                return True

        return False

    def _generate_grid_signal(
        self,
        current_price: float,
        grid_levels: List[float],
        range_lower: float,
        range_upper: float,
        latest: pd.Series,
        df: pd.DataFrame,
        symbol: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Генерирует сигнал на основе текущей позиции относительно сетки.
        
        Returns:
            Сигнал long/short или None
        """
        if not grid_levels:
            return None

        # Находим ближайшие уровни выше и ниже
        levels_below = [lvl for lvl in grid_levels if lvl < current_price]
        levels_above = [lvl for lvl in grid_levels if lvl > current_price]

        if not levels_below or not levels_above:
            logger.debug(f"[GRID] {symbol}: Price outside grid range")
            return None

        nearest_support = max(levels_below)
        nearest_resistance = min(levels_above)

        # Вычисляем расстояние до уровней
        distance_to_support = current_price - nearest_support
        distance_to_resistance = nearest_resistance - current_price
        
        distance_to_support_pct = (distance_to_support / current_price) * 100
        distance_to_resistance_pct = (distance_to_resistance / current_price) * 100

        # Логика сигналов: покупаем у поддержки, продаём у сопротивления
        signal_threshold = self.grid_spacing_percent * 0.3  # 30% от шага сетки

        reasons = []
        values = {}
        
        atr = latest.get("ATRr_14", latest.get("ATR_14", 0))
        if atr == 0:
            atr = current_price * 0.01  # Fallback 1%

        # LONG сигнал: цена близко к уровню поддержки
        if distance_to_support_pct <= signal_threshold:
            confidence = 0.70 + (0.20 * (1 - distance_to_support_pct / signal_threshold))
            
            entry_price = current_price
            stop_loss = range_lower - (atr * self.stop_loss_atr_multiplier)
            take_profit = nearest_resistance  # Следующий уровень сетки
            
            reasons.append(f"Price near grid support level {nearest_support:.2f}")
            reasons.append(f"Distance to support: {distance_to_support_pct:.2f}%")
            reasons.append(f"Target: next grid level {take_profit:.2f}")
            
            values.update({
                "grid_support": nearest_support,
                "grid_resistance": nearest_resistance,
                "range_lower": range_lower,
                "range_upper": range_upper,
                "grid_levels_count": len(grid_levels),
                "distance_to_support_pct": distance_to_support_pct,
            })

            logger.info(
                f"[GRID] {symbol} LONG signal | Price={current_price:.2f}, "
                f"Support={nearest_support:.2f}, Target={take_profit:.2f}, "
                f"Confidence={confidence:.2f}"
            )

            return {
                "signal": "long",
                "confidence": confidence,
                "reasons": reasons,
                "values": values,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
            }

        # SHORT сигнал: цена близко к уровню сопротивления
        elif distance_to_resistance_pct <= signal_threshold:
            confidence = 0.70 + (0.20 * (1 - distance_to_resistance_pct / signal_threshold))
            
            entry_price = current_price
            stop_loss = range_upper + (atr * self.stop_loss_atr_multiplier)
            take_profit = nearest_support  # Следующий уровень сетки
            
            reasons.append(f"Price near grid resistance level {nearest_resistance:.2f}")
            reasons.append(f"Distance to resistance: {distance_to_resistance_pct:.2f}%")
            reasons.append(f"Target: next grid level {take_profit:.2f}")
            
            values.update({
                "grid_support": nearest_support,
                "grid_resistance": nearest_resistance,
                "range_lower": range_lower,
                "range_upper": range_upper,
                "grid_levels_count": len(grid_levels),
                "distance_to_resistance_pct": distance_to_resistance_pct,
            })

            logger.info(
                f"[GRID] {symbol} SHORT signal | Price={current_price:.2f}, "
                f"Resistance={nearest_resistance:.2f}, Target={take_profit:.2f}, "
                f"Confidence={confidence:.2f}"
            )

            return {
                "signal": "short",
                "confidence": confidence,
                "reasons": reasons,
                "values": values,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
            }

        # В середине между уровнями - не торгуем
        logger.debug(
            f"[GRID] {symbol}: Between grid levels, waiting | "
            f"Price={current_price:.2f}, Support={nearest_support:.2f}, "
            f"Resistance={nearest_resistance:.2f}"
        )
        return None

    def get_grid_state(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Возвращает текущее состояние сетки для символа.
        
        Args:
            symbol: Торговый символ
            
        Returns:
            Dict с состоянием сетки или None
        """
        return self._grid_state.get(symbol)

    def reset_grid(self, symbol: Optional[str] = None):
        """
        Сбрасывает состояние сетки (для ребаланса или изменения параметров).
        
        Args:
            symbol: Конкретный символ или None для всех
        """
        if symbol:
            if symbol in self._grid_state:
                del self._grid_state[symbol]
                logger.info(f"[GRID] {symbol}: Grid state reset")
        else:
            self._grid_state.clear()
            logger.info("[GRID] All grid states reset")
