"""
Paper Trading Simulator - E1 EPIC

Реалистичная симуляция сделок:
- Fills по close цене + slippage
- Комиссии (maker/taker)
- Отслеживание позиций и equity
- SL/TP срабатывание
- Воспроизводимые результаты (deterministic с seed)

Formula для заполнения:
- Entry: close_price * (1 + slippage_buy)
- Exit: close_price * (1 - slippage_sell)
- Commission: filled_qty * entry_price * commission_rate

Equity: cash + unrealized_pnl
PnL: (exit_price - entry_price) * qty - commission_entry - commission_exit
"""

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import logging
import numpy as np
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """Статусы ордеров"""
    PENDING = "pending"
    FILLED = "filled"
    CANCELED = "canceled"
    PARTIALLY_FILLED = "partially_filled"
    REJECTED = "rejected"


class TradeState(Enum):
    """Состояние сделки"""
    OPEN = "open"
    CLOSED = "closed"
    STOPPED_OUT = "stopped_out"  # SL сработал
    TP_HIT = "tp_hit"  # TP сработал


@dataclass
class PaperTradingConfig:
    """Конфигурация для paper trading"""
    
    initial_balance: Decimal = Decimal("10000")        # Начальный баланс
    maker_commission: Decimal = Decimal("0.0002")      # 0.02% maker
    taker_commission: Decimal = Decimal("0.0004")      # 0.04% taker
    
    slippage_buy: Decimal = Decimal("0.0001")          # 0.01% slippage при покупке
    slippage_sell: Decimal = Decimal("0.0001")         # 0.01% slippage при продаже
    slippage_volatility_factor: Decimal = Decimal("1.0")  # множитель волатильности для slippage
    
    seed: Optional[int] = None                          # Для reproducibility
    use_random_slippage: bool = False                   # Случайный slippage вместо фиксированного


@dataclass
class Order:
    """Ордер в paper trading"""
    
    order_id: str
    symbol: str
    side: str                           # "Buy" или "Sell"
    order_type: str                     # "Market", "Limit", "StopMarket"
    qty: Decimal
    price: Decimal                      # Цена заполнения (для limit/stop)
    
    filled_qty: Decimal = Decimal("0")
    avg_filled_price: Decimal = Decimal("0")
    status: OrderStatus = OrderStatus.PENDING
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None
    commission_paid: Decimal = Decimal("0")
    
    def __post_init__(self):
        if self.order_id is None:
            raise ValueError("order_id is required")


@dataclass
class Trade:
    """Завершенная сделка (entry + exit)"""
    
    trade_id: str
    symbol: str
    side: str
    
    # Entry
    entry_price: Decimal
    entry_qty: Decimal
    entry_time: datetime
    entry_commission: Decimal
    
    # Exit
    exit_price: Decimal
    exit_qty: Decimal
    exit_time: datetime
    exit_commission: Decimal
    
    # Results
    pnl: Decimal                       # Realized PnL (без комиссий)
    pnl_after_commission: Decimal      # После комиссий
    roi_percent: Decimal               # ROI %
    
    state: TradeState = TradeState.CLOSED
    
    # SL/TP info
    stopped_loss_price: Optional[Decimal] = None
    take_profit_price: Optional[Decimal] = None
    was_sl_hit: bool = False
    was_tp_hit: bool = False
    
    # Duration
    duration_seconds: float = 0.0
    
    def calculate_metrics(self) -> Dict[str, Decimal]:
        """Вычислить метрики сделки"""
        return {
            "pnl": self.pnl,
            "pnl_after_commission": self.pnl_after_commission,
            "roi_percent": self.roi_percent,
            "is_profitable": self.pnl_after_commission > 0,
            "was_sl_hit": self.was_sl_hit,
            "was_tp_hit": self.was_tp_hit,
        }


@dataclass
class Position:
    """Открытая позиция"""
    
    symbol: str
    side: str                          # "long" или "short"
    qty: Decimal
    entry_price: Decimal
    entry_commission: Decimal
    entry_time: datetime
    
    # Current
    current_price: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    
    # SL/TP
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    
    def calculate_unrealized_pnl(self, current_price: Decimal) -> Decimal:
        """Вычислить unrealized PnL"""
        if self.side == "long":
            pnl = (current_price - self.entry_price) * self.qty
        else:  # short
            pnl = (self.entry_price - current_price) * self.qty
        
        self.unrealized_pnl = pnl
        self.current_price = current_price
        return pnl
    
    def check_sl_tp(self, current_price: Decimal) -> Optional[str]:
        """
        Проверить SL/TP срабатывание.
        Returns: 'sl' если сработал SL, 'tp' если сработал TP, None иначе
        """
        if self.side == "long":
            if self.stop_loss and current_price <= self.stop_loss:
                return "sl"
            if self.take_profit and current_price >= self.take_profit:
                return "tp"
        else:  # short
            if self.stop_loss and current_price >= self.stop_loss:
                return "sl"
            if self.take_profit and current_price <= self.take_profit:
                return "tp"
        
        return None


class PaperTradingSimulator:
    """
    Полнофункциональный симулятор сделок для paper mode.
    
    Особенности:
    - Реалистичные fills (close + slippage)
    - Maker/taker комиссии
    - SL/TP логика
    - Отслеживание equity, PnL
    - История всех сделок
    - Deterministic с seed
    """
    
    def __init__(self, config: PaperTradingConfig = None):
        """
        Инициализация симулятора.
        
        Args:
            config: PaperTradingConfig с параметрами
        """
        self.config = config or PaperTradingConfig()
        self.cash = self.config.initial_balance
        self.initial_balance = self.config.initial_balance
        
        # Состояние
        self.positions: Dict[str, Position] = {}          # symbol -> Position
        self.trades: List[Trade] = []                      # История всех закрытых сделок
        self.orders: Dict[str, Order] = {}                 # order_id -> Order
        
        # Для reproducibility
        self._rng = np.random.RandomState(self.config.seed)
        self._order_counter = 0
        self._trade_counter = 0
        
        logger.info(
            f"PaperTradingSimulator initialized: "
            f"balance=${float(self.initial_balance):.2f}, "
            f"maker={float(self.config.maker_commission)*100:.3f}%, "
            f"taker={float(self.config.taker_commission)*100:.3f}%"
        )
    
    # ==================== Order Management ====================
    
    def submit_market_order(
        self,
        symbol: str,
        side: str,
        qty: Decimal,
        current_price: Decimal,
    ) -> Tuple[str, bool, str]:
        """
        Отправить market ордер (заполняется сразу).
        
        Args:
            symbol: Торговая пара
            side: "Buy" или "Sell"
            qty: Количество
            current_price: Текущая цена (close цена свечи)
        
        Returns:
            (order_id, success, message)
        """
        if qty <= 0:
            return "", False, "Quantity must be positive"
        
        if side not in ["Buy", "Sell"]:
            return "", False, "Side must be 'Buy' or 'Sell'"
        
        # Проверить достаточно средств
        if side == "Buy":
            estimated_cost = qty * current_price * (1 + self.config.taker_commission)
            if self.cash < estimated_cost:
                return "", False, f"Insufficient cash: need ${float(estimated_cost):.2f}, have ${float(self.cash):.2f}"
        
        # Создать ордер
        order_id = f"order_{self._order_counter}"
        self._order_counter += 1
        
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty,
            price=current_price,
            filled_qty=qty,  # Market ордеры заполняются полностью
            avg_filled_price=current_price,
            status=OrderStatus.FILLED,
            filled_at=datetime.utcnow(),
        )
        
        # Заполнить ордер (с slippage и комиссией)
        success, message = self._fill_order(order, current_price, is_market=True)
        
        if success:
            self.orders[order_id] = order
            return order_id, True, "Order filled"
        else:
            return order_id, False, message
    
    def submit_limit_order(
        self,
        symbol: str,
        side: str,
        qty: Decimal,
        limit_price: Decimal,
    ) -> Tuple[str, bool, str]:
        """
        Отправить limit ордер (ждет заполнения).
        
        Args:
            symbol: Торговая пара
            side: "Buy" или "Sell"
            qty: Количество
            limit_price: Лимит цена
        
        Returns:
            (order_id, success, message)
        """
        if qty <= 0:
            return "", False, "Quantity must be positive"
        
        order_id = f"order_{self._order_counter}"
        self._order_counter += 1
        
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type="Limit",
            qty=qty,
            price=limit_price,
            status=OrderStatus.PENDING,
        )
        
        self.orders[order_id] = order
        logger.info(
            f"Limit order submitted: {side} {float(qty):.6f} {symbol} @ ${float(limit_price):.2f}"
        )
        
        return order_id, True, "Order pending"
    
    def _fill_order(
        self,
        order: Order,
        current_price: Decimal,
        is_market: bool = True,
    ) -> Tuple[bool, str]:
        """
        Заполнить ордер с slippage и комиссией.
        
        Args:
            order: Order для заполнения
            current_price: Текущая цена (close)
            is_market: True если market ордер (иначе limit)
        
        Returns:
            (success, message)
        """
        # Вычислить цену заполнения с slippage
        filled_price = self._calculate_filled_price(
            current_price,
            order.side,
            is_market=is_market
        )
        
        # Вычислить комиссию
        commission_rate = self.config.taker_commission if is_market else self.config.maker_commission
        commission = order.qty * filled_price * commission_rate
        
        # Проверить баланс для Buy
        if order.side == "Buy":
            total_cost = order.qty * filled_price + commission
            if self.cash < total_cost:
                return False, f"Insufficient cash for order fill"
            
            self.cash -= total_cost
        
        # Обновить ордер
        order.filled_qty = order.qty
        order.avg_filled_price = filled_price
        order.status = OrderStatus.FILLED
        order.filled_at = datetime.utcnow()
        order.commission_paid = commission
        
        # Обновить позицию
        if order.side == "Buy":
            self._update_position_on_buy(order.symbol, order.qty, filled_price, commission)
        else:  # Sell
            self._update_position_on_sell(order.symbol, order.qty, filled_price, commission)
        
        logger.debug(
            f"Order {order.order_id} filled: {order.side} {float(order.qty):.6f} {order.symbol} "
            f"@ ${float(filled_price):.2f}, commission ${float(commission):.2f}"
        )
        
        return True, "Order filled successfully"
    
    def _calculate_filled_price(
        self,
        close_price: Decimal,
        side: str,
        is_market: bool = True,
    ) -> Decimal:
        """
        Вычислить цену заполнения с slippage.
        
        Args:
            close_price: Close цена свечи
            side: "Buy" или "Sell"
            is_market: True если market ордер
        
        Returns:
            Цена заполнения
        """
        if not is_market:
            # Limit ордеры заполняются по лимит цене без slippage
            return close_price
        
        # Вычислить slippage (может быть случайным или фиксированным)
        if self.config.use_random_slippage:
            # Случайный slippage ±50% от базового
            slippage = self.config.slippage_buy * Decimal(str(0.5 + self._rng.random()))
        else:
            slippage = self.config.slippage_buy
        
        # Применить направление slippage
        if side == "Buy":
            # При покупке цена выше close (неудача)
            filled_price = close_price * (1 + slippage)
        else:  # Sell
            # При продаже цена ниже close (неудача)
            filled_price = close_price * (1 - slippage)
        
        return filled_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    def _update_position_on_buy(
        self,
        symbol: str,
        qty: Decimal,
        price: Decimal,
        commission: Decimal,
    ):
        """Обновить позицию при покупке"""
        if symbol not in self.positions:
            self.positions[symbol] = Position(
                symbol=symbol,
                side="long",
                qty=qty,
                entry_price=price,
                entry_commission=commission,
                entry_time=datetime.utcnow(),
            )
        else:
            pos = self.positions[symbol]
            # Average up
            total_qty = pos.qty + qty
            pos.entry_price = (pos.entry_price * pos.qty + price * qty) / total_qty
            pos.qty = total_qty
            pos.entry_commission += commission
    
    def _update_position_on_sell(
        self,
        symbol: str,
        qty: Decimal,
        price: Decimal,
        commission: Decimal,
    ):
        """
        Обновить позицию при продаже.
        Может закрыть позицию или открыть short.
        """
        if symbol not in self.positions:
            # Открыть short позицию
            self.cash += qty * price - commission  # Получить средства от short
            self.positions[symbol] = Position(
                symbol=symbol,
                side="short",
                qty=qty,
                entry_price=price,
                entry_commission=commission,
                entry_time=datetime.utcnow(),
            )
        else:
            pos = self.positions[symbol]
            
            if pos.side == "long":
                # Закрыть long или частичная закрытие
                if qty >= pos.qty:
                    # Полная закрытие
                    self._close_trade(symbol, price, qty, commission)
                    del self.positions[symbol]
                else:
                    # Частичная закрытие
                    self._close_trade(symbol, price, qty, commission)
                    pos.qty -= qty
            else:
                # Short позиция, add more short
                total_qty = pos.qty + qty
                pos.entry_price = (pos.entry_price * pos.qty + price * qty) / total_qty
                pos.qty = total_qty
                pos.entry_commission += commission
                self.cash += qty * price - commission
    
    def _close_trade(
        self,
        symbol: str,
        exit_price: Decimal,
        exit_qty: Decimal,
        exit_commission: Decimal,
    ):
        """
        Закрыть сделку и записать trade в историю.
        """
        pos = self.positions[symbol]
        
        # Вычислить PnL
        if pos.side == "long":
            pnl = (exit_price - pos.entry_price) * exit_qty
        else:  # short
            pnl = (pos.entry_price - exit_price) * exit_qty
        
        total_commission = pos.entry_commission * (exit_qty / pos.qty) + exit_commission
        pnl_after_commission = pnl - total_commission
        
        # ROI
        entry_notional = pos.entry_price * exit_qty
        roi = (pnl_after_commission / entry_notional * 100) if entry_notional > 0 else Decimal("0")
        
        # Создать Trade
        trade = Trade(
            trade_id=f"trade_{self._trade_counter}",
            symbol=symbol,
            side=pos.side,
            entry_price=pos.entry_price,
            entry_qty=exit_qty,
            entry_time=pos.entry_time,
            entry_commission=pos.entry_commission * (exit_qty / pos.qty),
            exit_price=exit_price,
            exit_qty=exit_qty,
            exit_time=datetime.utcnow(),
            exit_commission=exit_commission,
            pnl=pnl,
            pnl_after_commission=pnl_after_commission,
            roi_percent=roi,
        )
        
        self._trade_counter += 1
        self.trades.append(trade)
        
        # Обновить cash при close long
        if pos.side == "long":
            self.cash += exit_price * exit_qty - exit_commission
        
        logger.info(
            f"Trade closed: {pos.side.upper()} {float(exit_qty):.6f} {symbol}, "
            f"PnL: ${float(pnl_after_commission):.2f}, ROI: {float(roi):.2f}%"
        )
    
    # ==================== Position Management ====================
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Получить открытую позицию"""
        return self.positions.get(symbol)
    
    def set_stop_loss_take_profit(
        self,
        symbol: str,
        stop_loss: Optional[Decimal],
        take_profit: Optional[Decimal],
    ) -> bool:
        """Установить SL/TP для позиции"""
        if symbol not in self.positions:
            logger.warning(f"No position for {symbol}")
            return False
        
        pos = self.positions[symbol]
        pos.stop_loss = stop_loss
        pos.take_profit = take_profit
        
        logger.info(
            f"SL/TP set for {symbol}: SL=${float(stop_loss):.2f}, TP=${float(take_profit):.2f}"
        )
        return True
    
    def check_sl_tp(self, current_price: Decimal) -> Dict[str, str]:
        """
        Проверить все SL/TP срабатывания.
        
        Returns:
            Dict[symbol, "sl" | "tp"] для сработавших позиций
        """
        triggered = {}
        
        for symbol, pos in list(self.positions.items()):
            sl_tp = pos.check_sl_tp(current_price)
            if sl_tp:
                triggered[symbol] = sl_tp
        
        return triggered
    
    def close_position_on_trigger(
        self,
        symbol: str,
        trigger_type: str,  # "sl" или "tp"
        exit_price: Decimal,
    ) -> Tuple[bool, str]:
        """
        Закрыть позицию по SL/TP.
        
        Args:
            symbol: Торговая пара
            trigger_type: "sl" или "tp"
            exit_price: Цена закрытия
        
        Returns:
            (success, message)
        """
        if symbol not in self.positions:
            return False, f"No position for {symbol}"
        
        pos = self.positions[symbol]
        
        # Вычислить комиссию
        commission = pos.qty * exit_price * self.config.taker_commission
        
        # Закрыть сделку
        self._close_trade(symbol, exit_price, pos.qty, commission)
        
        # Обновить trade с информацией о SL/TP
        if self.trades:
            trade = self.trades[-1]
            if trigger_type == "sl":
                trade.was_sl_hit = True
                trade.state = TradeState.STOPPED_OUT
            else:  # tp
                trade.was_tp_hit = True
                trade.state = TradeState.TP_HIT
        
        del self.positions[symbol]
        return True, f"Position closed by {trigger_type.upper()}"
    
    # ==================== Equity & PnL ====================
    
    def get_equity(self) -> Decimal:
        """Получить текущий equity (cash + unrealized PnL)"""
        unrealized = Decimal("0")
        for pos in self.positions.values():
            unrealized += pos.unrealized_pnl
        return self.cash + unrealized
    
    def update_market_prices(self, prices: Dict[str, Decimal]):
        """
        Обновить текущие цены для всех позиций.
        
        Args:
            prices: Dict[symbol, current_price]
        """
        for symbol, current_price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].calculate_unrealized_pnl(current_price)
    
    def get_account_summary(self) -> Dict[str, Any]:
        """Получить summary счета"""
        equity = self.get_equity()
        total_pnl = equity - self.initial_balance
        roi = (total_pnl / self.initial_balance * 100) if self.initial_balance > 0 else Decimal("0")
        
        unrealized_pnl = Decimal("0")
        for pos in self.positions.values():
            unrealized_pnl += pos.unrealized_pnl
        
        return {
            "initial_balance": float(self.initial_balance),
            "current_balance": float(self.cash),
            "equity": float(equity),
            "total_pnl": float(total_pnl),
            "total_roi_percent": float(roi),
            "open_positions": len(self.positions),
            "closed_trades": len(self.trades),
            "unrealized_pnl": float(unrealized_pnl),
        }
    
    def get_trades(self) -> List[Trade]:
        """Получить историю всех закрытых сделок"""
        return self.trades
