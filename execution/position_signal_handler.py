"""

Обработчик новых сигналов для существующих позиций.


Реализует три стратегии:

1. IGNORE - Игнорировать сигнал если уже в позиции

2. ADD - Пирамидинг (добавить в существующую позицию)

3. FLIP - Закрыть текущую и открыть противоположную

"""


from enum import Enum

from dataclasses import dataclass

from typing import Optional, Dict, Any, Tuple

from decimal import Decimal

from logger import setup_logger

from utils.signal_logger import signal_logger


logger = setup_logger(__name__)


class SignalAction(Enum):

    """Возможные действия при получении нового сигнала"""

    IGNORE = "ignore"  # Игнорировать сигнал

    ADD = "add"  # Пирамидинг - добавить в позицию

    FLIP = "flip"  # Flip - закрыть и открыть противоположную


@dataclass
class SignalActionConfig:

    """Конфигурация правил обработки сигналов"""

    # Основное действие по умолчанию

    default_action: SignalAction = SignalAction.IGNORE

    # Правила по направлению сигнала

    long_signal_action: SignalAction = SignalAction.IGNORE

    short_signal_action: SignalAction = SignalAction.IGNORE

    # Параметры пирамидинга (для ADD)

    max_pyramid_levels: int = 3  # Максимум добавлений в позицию

    pyramid_qty_increase: Decimal = Decimal("0.5")  # 50% от основной позиции на каждый уровень

    pyramid_max_notional: Decimal = Decimal("1000")  # Макс notional при пирамидинге

    # Параметры flip

    flip_immediately: bool = True  # Flip без задержки, или с подтверждением?

    flip_preserve_sl_tp: bool = True  # Сохранять ли SL/TP % при flip?

    # Проверки перед действием

    require_higher_confidence: bool = False  # ADD/FLIP требуют выше confidence?

    min_confidence_for_action: float = 0.7  # Минимум confidence для ADD/FLIP

    # Ограничения по максимальному exposure

    max_total_exposure_usd: Decimal = Decimal("5000")  # Макс total notional для всех позиций

    max_position_qty_increase_percent: float = 50.0  # Макс +50% к текущей позиции при ADD


@dataclass
class SignalActionResult:

    """Результат обработки сигнала"""

    action_taken: SignalAction

    success: bool

    message: str

    position_update: Optional[Dict[str, Any]] = None  # Данные об изменении позиции

    # Для tracking

    old_qty: Optional[Decimal] = None  # Предыдущее количество

    new_qty: Optional[Decimal] = None  # Новое количество

    order_id: Optional[str] = None  # ID выставленного ордера


class PositionSignalHandler:

    """Обработчик сигналов для позиций"""

    def __init__(self, config: SignalActionConfig = None):
        """

        Args:

            config: Конфигурация правил обработки сигналов

        """

        self.config = config or SignalActionConfig()

        logger.info(

            "PositionSignalHandler initialized: "

            f"default_action={self.config.default_action.value}, "

            f"pyramid_levels={self.config.max_pyramid_levels}"

        )

    def get_action_for_signal(

        self,

        current_position: Optional[Dict[str, Any]],

        new_signal: Dict[str, Any],

    ) -> SignalAction:
        """

        Определить действие для нового сигнала


        Args:

            current_position: Текущая позиция (если есть)

                {

                    'symbol': 'BTCUSDT',

                    'side': 'Long',

                    'qty': Decimal('0.1'),

                    'entry_price': Decimal('30000'),

                    'strategy_id': 'trend_pullback',

                }

            new_signal: Новый сигнал

                {

                    'signal': 'long' или 'short',

                    'strategy': 'strategy_name',

                    'confidence': 0.85,

                    'entry_price': Decimal('31000'),

                    ...

                }


        Returns:

            SignalAction - действие для выполнения

        """

        # Если нет открытой позиции - всегда открываем

        if not current_position:

            logger.debug("No current position, will open new position")

            return SignalAction.IGNORE  # Игнорирование означает "не конфликт", позиция откроется

        signal_direction = new_signal.get("signal", "").lower()

        current_side = current_position.get("side", "").lower()

        # Определяем направление нового сигнала

        signal_side_is_long = signal_direction in ["long", "buy"]

        current_is_long = current_side in ["long", "buy"]

        # Одинаковое направление (оба лонг или оба шорт)

        if signal_side_is_long == current_is_long:

            # Это signal в том же направлении что и текущая позиция

            return self._get_action_for_same_direction(current_position, new_signal)

        # Противоположное направление

        else:

            # Это signal в противоположном направлении

            return self._get_action_for_opposite_direction(current_position, new_signal)

    def _get_action_for_same_direction(

        self, current_position: Dict[str, Any], new_signal: Dict[str, Any]

    ) -> SignalAction:
        """Определить действие когда сигнал в том же направлении"""

        # По умолчанию - пирамидинг или игнор

        signal_direction = new_signal.get("signal", "").lower()

        signal_is_long = signal_direction in ["long", "buy"]

        action = (

            self.config.long_signal_action if signal_is_long else self.config.short_signal_action

        )

        logger.debug(

            f"Same direction signal: current_side={current_position.get('side')}, "

            f"signal={signal_direction}, action={action.value}"

        )

        return action

    def _get_action_for_opposite_direction(

        self, current_position: Dict[str, Any], new_signal: Dict[str, Any]

    ) -> SignalAction:
        """Определить действие когда сигнал в противоположном направлении"""

        # При противоположном сигнале - обычно flip или ignore

        signal_direction = new_signal.get("signal", "").lower()

        signal_is_long = signal_direction in ["long", "buy"]

        action = (

            self.config.long_signal_action if signal_is_long else self.config.short_signal_action

        )

        logger.debug(

            f"Opposite direction signal: current_side={current_position.get('side')}, "

            f"signal={signal_direction}, action={action.value}"

        )

        return action

    def validate_add_action(

        self,

        current_position: Dict[str, Any],

        new_signal: Dict[str, Any],

        add_qty: Decimal,

        current_price: Decimal,

    ) -> Tuple[bool, str]:
        """

        Валидировать возможность пирамидинга (ADD)


        Returns:

            (is_valid, error_message)

        """

        # Проверка 1: Confidence достаточно высокий?

        if self.config.require_higher_confidence:

            confidence = new_signal.get("confidence", 0.5)

            if confidence < self.config.min_confidence_for_action:

                return (

                    False,

                    f"Confidence too low: {confidence} < {self.config.min_confidence_for_action}",

                )

        # Проверка 2: Не превышаем ли лимит пирамидов?

        pyramid_level = current_position.get("pyramid_level", 1)

        if pyramid_level >= self.config.max_pyramid_levels:

            return (

                False,

                f"Max pyramid levels reached: {pyramid_level} >= {self.config.max_pyramid_levels}",

            )

        # Проверка 3: Увеличение qty не превышает лимит?

        current_qty = Decimal(str(current_position.get("qty", 0)))

        max_qty_increase = current_qty * Decimal(

            str(self.config.max_position_qty_increase_percent / 100)

        )

        if add_qty > max_qty_increase:

            return False, f"Add qty too large: {add_qty} > {max_qty_increase}"

        # Проверка 4: Новое total notional не превышает лимит?

        new_total_qty = current_qty + add_qty

        new_notional = new_total_qty * current_price

        if new_notional > self.config.max_total_exposure_usd:

            return (

                False,

                f"Total exposure too high: {new_notional} > {self.config.max_total_exposure_usd}",

            )

        logger.info(

            "ADD validation passed: "

            f"pyramid_level={pyramid_level}, "

            f"new_qty={new_total_qty}, "

            f"new_notional={new_notional}"

        )

        return True, ""

    def validate_flip_action(

        self,

        current_position: Dict[str, Any],

        new_signal: Dict[str, Any],

    ) -> Tuple[bool, str]:
        """

        Валидировать возможность flip


        Returns:

            (is_valid, error_message)

        """

        # Проверка 1: Confidence достаточно высокий?

        if self.config.require_higher_confidence:

            confidence = new_signal.get("confidence", 0.5)

            if confidence < self.config.min_confidence_for_action:

                return (

                    False,

                    f"Confidence too low: {confidence} < {self.config.min_confidence_for_action}",

                )

        # Проверка 2: Позиция достаточно долго открыта?

        # (можно добавить check на минимальное время в позиции)

        logger.info(

            "FLIP validation passed: "

            f"closing {current_position.get('side')} "

            f"qty={current_position.get('qty')}"

        )

        return True, ""

    def handle_signal(

        self,

        current_position: Optional[Dict[str, Any]],

        new_signal: Dict[str, Any],

        current_price: Decimal,

        account_balance: Decimal,

        position_sizer: Optional[Any] = None,

    ) -> SignalActionResult:
        """

        Обработать новый сигнал с учётом текущей позиции


        Args:

            current_position: Текущая позиция (если есть)

            new_signal: Новый сигнал

            current_price: Текущая цена

            account_balance: Баланс аккаунта

            position_sizer: Объект для расчёта размера позиции


        Returns:

            SignalActionResult с информацией о действии

        """

        # Если нет позиции - просто разрешить открытие

        if not current_position:

            logger.debug(

                f"No current position, signal will be processed normally: {new_signal.get('signal')}"

            )

            return SignalActionResult(

                action_taken=SignalAction.IGNORE,  # IGNORE = "нет конфликта, открываем"

                success=True,

                message="No position conflict, will open new position",

            )

        # Определяем действие

        action = self.get_action_for_signal(current_position, new_signal)

        # IGNORE - просто игнорируем сигнал

        if action == SignalAction.IGNORE:

            logger.warning(

                f"Signal IGNORED: already in {current_position.get('side')} position, "

                f"new signal={new_signal.get('signal')}"

            )

            return SignalActionResult(

                action_taken=SignalAction.IGNORE,

                success=False,

                message=f"Position conflict: already in {current_position.get('side')}, ignoring {new_signal.get('signal')} signal",

            )

        # ADD - пирамидинг

        elif action == SignalAction.ADD:

            return self._handle_add_action(

                current_position, new_signal, current_price, account_balance, position_sizer

            )

        # FLIP - закрыть и открыть противоположную

        elif action == SignalAction.FLIP:

            return self._handle_flip_action(current_position, new_signal)

        else:

            return SignalActionResult(

                action_taken=action,

                success=False,

                message=f"Unknown action: {action}",

            )

    def _handle_add_action(

        self,

        current_position: Dict[str, Any],

        new_signal: Dict[str, Any],

        current_price: Decimal,

        account_balance: Decimal,

        position_sizer: Optional[Any] = None,

    ) -> SignalActionResult:
        """Обработать ADD (пирамидинг)"""

        current_price = Decimal(str(current_price))

        current_qty = Decimal(str(current_position.get("qty", 0)))

        # Расчитываем размер добавления (обычно % от текущей позиции)

        add_qty = current_qty * self.config.pyramid_qty_increase

        # Валидируем

        is_valid, error_msg = self.validate_add_action(

            current_position, new_signal, add_qty, current_price

        )

        if not is_valid:

            logger.warning(f"ADD validation failed: {error_msg}")

            # Log structured rejection for ADD action

            symbol = current_position.get("symbol", "UNKNOWN")

            signal_logger.log_signal_rejected(

                strategy_name=new_signal.get("strategy", "Unknown"),

                symbol=symbol,

                direction=new_signal.get("signal", "unknown").upper(),

                confidence=new_signal.get("confidence", 0),

                reasons=["add_validation_failed"],

                values={

                    "validation_error": error_msg,

                    "current_qty": float(current_qty),

                    "add_qty": float(add_qty),

                    "current_price": float(current_price),

                    "pyramid_level": current_position.get("pyramid_level", 1),

                },

            )

            return SignalActionResult(

                action_taken=SignalAction.ADD,

                success=False,

                message=f"ADD validation failed: {error_msg}",

                old_qty=current_qty,

            )

        new_total_qty = current_qty + add_qty

        logger.info(

            "ADD action approved: "

            f"old_qty={current_qty}, "

            f"add_qty={add_qty}, "

            f"new_qty={new_total_qty}"

        )

        return SignalActionResult(

            action_taken=SignalAction.ADD,

            success=True,

            message=f"Pyramid ADD approved: adding {add_qty} to {current_qty}",

            position_update={

                "action": "add",

                "add_qty": float(add_qty),

                "new_total_qty": float(new_total_qty),

                "pyramid_level": current_position.get("pyramid_level", 1) + 1,

            },

            old_qty=current_qty,

            new_qty=new_total_qty,

        )

    def _handle_flip_action(

        self,

        current_position: Dict[str, Any],

        new_signal: Dict[str, Any],

    ) -> SignalActionResult:
        """Обработать FLIP (закрыть и открыть противоположную)"""

        # Валидируем

        is_valid, error_msg = self.validate_flip_action(current_position, new_signal)

        if not is_valid:

            logger.warning(f"FLIP validation failed: {error_msg}")

            # Log structured rejection for FLIP action

            symbol = current_position.get("symbol", "UNKNOWN")

            signal_logger.log_signal_rejected(

                strategy_name=new_signal.get("strategy", "Unknown"),

                symbol=symbol,

                direction=new_signal.get("signal", "unknown").upper(),

                confidence=new_signal.get("confidence", 0),

                reasons=["flip_validation_failed"],

                values={

                    "validation_error": error_msg,

                    "current_side": current_position.get("side", "Unknown"),

                    "current_qty": float(current_position.get("qty", 0)),

                },

            )

            return SignalActionResult(

                action_taken=SignalAction.FLIP,

                success=False,

                message=f"FLIP validation failed: {error_msg}",

            )

        current_qty = Decimal(str(current_position.get("qty", 0)))

        current_side = current_position.get("side", "Long")

        new_side = new_signal.get("signal", "long").lower()

        logger.info(

            "FLIP action approved: "

            f"close {current_side} qty={current_qty}, "

            f"open new {new_side}"

        )

        return SignalActionResult(

            action_taken=SignalAction.FLIP,

            success=True,

            message=f"FLIP approved: closing {current_side} and opening {new_side}",

            position_update={

                "action": "flip",

                "close_qty": float(current_qty),

                "close_side": current_side,

                "open_side": new_side,

                "pyramid_level": 1,  # Reset на новой позиции

            },

            old_qty=current_qty,

            new_qty=Decimal("0"),  # Временно 0, затем откроется новая

        )


class PositionManager:

    """Улучшенный менеджер позиций с обработкой сигналов"""

    def __init__(self, order_manager, signal_config: SignalActionConfig = None):
        """

        Args:

            order_manager: Менеджер ордеров для выставления

            signal_config: Конфигурация правил обработки сигналов

        """

        self.order_manager = order_manager

        self.signal_handler = PositionSignalHandler(signal_config or SignalActionConfig())

        # Хранилище текущих позиций по символам

        self._positions: Dict[str, Dict[str, Any]] = {}

        logger.info("PositionManager initialized with signal handling")

    def register_position(

        self,

        symbol: str,

        side: str,

        entry_price: Decimal,

        qty: Decimal,

        order_id: str,

        strategy_id: str = "Unknown",

        stop_loss: Optional[Decimal] = None,

        take_profit: Optional[Decimal] = None,

    ) -> bool:
        """Зарегистрировать новую позицию"""

        position = {

            "symbol": symbol,

            "side": side,

            "entry_price": Decimal(str(entry_price)),

            "qty": Decimal(str(qty)),

            "order_id": order_id,

            "strategy_id": strategy_id,

            "stop_loss": Decimal(str(stop_loss)) if stop_loss else None,

            "take_profit": Decimal(str(take_profit)) if take_profit else None,

            "pyramid_level": 1,

            "created_at": __import__("time").time(),

        }

        self._positions[symbol] = position

        logger.info(

            f"Position registered: {symbol} {side} qty={qty} @ {entry_price}, "

            f"level=1, strategy={strategy_id}"

        )

        return True

    def add_to_position(

        self,

        symbol: str,

        add_qty: Decimal,

        entry_price: Decimal,

        order_id: str,

    ) -> bool:
        """Добавить к существующей позиции (пирамидинг)"""

        if symbol not in self._positions:

            logger.error(f"Position not found for {symbol}")

            return False

        position = self._positions[symbol]

        old_qty = position["qty"]

        # Обновляем средневзвешенную цену входа

        total_qty = old_qty + add_qty

        old_entry = position["entry_price"]

        weighted_entry = (old_entry * old_qty + entry_price * add_qty) / total_qty

        position["qty"] = total_qty

        position["entry_price"] = weighted_entry

        position["pyramid_level"] = position.get("pyramid_level", 1) + 1

        logger.info(

            f"Position ADD: {symbol} added {add_qty}, "

            f"new_qty={total_qty}, "

            f"weighted_entry={weighted_entry}, "

            f"level={position['pyramid_level']}"

        )

        return True

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Получить текущую позицию"""

        return self._positions.get(symbol)

    def has_position(self, symbol: str) -> bool:
        """Проверить есть ли открытая позиция"""

        return symbol in self._positions

    def close_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Закрыть позицию"""

        if symbol not in self._positions:

            return None

        position = self._positions.pop(symbol)

        logger.info(f"Position CLOSED: {symbol} {position['side']} qty={position['qty']}")

        return position

    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """Получить все открытые позиции"""

        return dict(self._positions)
