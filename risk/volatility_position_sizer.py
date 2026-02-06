"""

Volatility-Scaled Position Sizing - D3 EPIC


Key principle: Keep USD risk constant, scale quantity with volatility.


Formula:

  Risk$ = Account * RiskPercent / 100

  Distance_to_SL = ATR * SL_Multiplier (e.g., 2.0)

  Position_Qty = Risk$ / Distance_to_SL / Entry_Price


Behavior:

- High volatility (large ATR) → Larger distance → Smaller quantity

- Low volatility (small ATR) → Smaller distance → Larger quantity

- USD risk always = RiskPercent * Account


This prevents over-trading in volatile conditions and under-trading in calm conditions.

"""


from datetime import datetime

from decimal import Decimal, ROUND_HALF_UP

from typing import Dict, Optional, Tuple

import logging


logger = logging.getLogger(__name__)


class VolatilityPositionSizerConfig:

    """Configuration for volatility-scaled position sizing."""

    def __init__(

        self,

        risk_percent: Decimal = Decimal("1.0"),  # 1% of account per trade

        atr_multiplier: Decimal = Decimal("2.0"),  # SL distance = ATR * 2.0

        min_position_size: Decimal = Decimal("0.00001"),  # Minimum qty (very small)

        max_position_size: Decimal = Decimal("100.0"),  # Maximum qty

        use_percent_fallback: bool = True,  # If no ATR, use % of account

        percent_fallback: Decimal = Decimal("5.0"),  # 5% of account fallback

    ):
        """

        Args:

            risk_percent: Risk per trade as % of account (1% = 1.0)

            atr_multiplier: Multiplier for ATR to get stop loss distance

            min_position_size: Minimum position quantity

            max_position_size: Maximum position quantity

            use_percent_fallback: Use percent-based sizing if no ATR

            percent_fallback: Fallback position size as % of account

        """

        self.risk_percent = risk_percent

        self.atr_multiplier = atr_multiplier

        self.min_position_size = min_position_size

        self.max_position_size = max_position_size

        self.use_percent_fallback = use_percent_fallback

        self.percent_fallback = percent_fallback


class VolatilityPositionSizer:

    """

    Position sizing engine that scales with volatility.


    Maintains stable USD risk across different market conditions

    by adjusting position quantity based on ATR-derived stop loss distance.

    """

    def __init__(self, config: Optional[VolatilityPositionSizerConfig] = None):
        """

        Initialize Volatility Position Sizer.


        Args:

            config: Configuration object (defaults to 1% risk per trade)

        """

        self.config = config or VolatilityPositionSizerConfig()

        # Tracking

        self.last_calculation_timestamp = None

        self.last_calculation_details: Dict = {}

        logger.info("Volatility Position Sizer initialized")

        logger.info(f"  Risk per trade: {self.config.risk_percent}%")

        logger.info(f"  ATR Multiplier: {self.config.atr_multiplier}x")

        logger.info(f"  Min position: {self.config.min_position_size}")

        logger.info(f"  Max position: {self.config.max_position_size}")

    def calculate_position_size(

        self,

        account_balance: Decimal,

        entry_price: Decimal,

        atr: Optional[Decimal] = None,

        signal: Optional[Dict] = None,

    ) -> Tuple[Decimal, Dict]:
        """

        Calculate position size scaled by volatility.


        Args:

            account_balance: Total account balance in USD

            entry_price: Entry price for the position

            atr: Average True Range (if None, uses fallback)

            signal: Optional signal dict with additional context


        Returns:

            Tuple of (position_qty, details_dict) where details_dict contains:

            {

                "position_qty": Decimal,

                "risk_usd": Decimal,

                "distance_to_sl": Decimal,

                "atr": Decimal or None,

                "stop_loss_price": Decimal,

                "method": str ("volatility" or "fallback"),

                "timestamp": datetime,

            }

        """

        timestamp = datetime.now()

        # Validate inputs

        if account_balance <= 0:

            logger.error(f"Invalid account balance: {account_balance}")

            return Decimal("0"), {"error": "Invalid account balance", "timestamp": timestamp}

        if entry_price <= 0:

            logger.error(f"Invalid entry price: {entry_price}")

            return Decimal("0"), {"error": "Invalid entry price", "timestamp": timestamp}

        account_balance = Decimal(str(account_balance))

        entry_price = Decimal(str(entry_price))

        # Calculate USD risk

        risk_usd = (account_balance * self.config.risk_percent / 100).quantize(

            Decimal("0.01"), rounding=ROUND_HALF_UP

        )

        # Determine method and calculate quantity

        if atr and atr > 0:

            # Volatility-scaled sizing

            atr = Decimal(str(atr))

            distance_to_sl = atr * self.config.atr_multiplier

            # Position qty = Risk$ / Distance / Price

            # But we want qty such that: qty * distance = risk$

            # So: qty = risk$ / distance

            position_qty = risk_usd / distance_to_sl / entry_price

            method = "volatility"

            sl_price = entry_price - distance_to_sl  # Approximate SL (depends on signal)

            logger.info(

                f"Volatility sizing: ATR={atr:.2f}, Distance={distance_to_sl:.2f}, "

                f"Qty={position_qty:.4f}, Risk=${risk_usd:.2f}"

            )

        else:

            # Fallback: percent-based sizing

            if not self.config.use_percent_fallback:

                logger.warning("No ATR provided and fallback disabled")

                return Decimal("0"), {

                    "error": "No ATR and fallback disabled",

                    "timestamp": timestamp,

                }

            # Position size = percent of account / entry price

            position_qty = (account_balance * self.config.percent_fallback / 100) / entry_price

            distance_to_sl = Decimal("0")  # Unknown

            method = "fallback"

            sl_price = Decimal("0")

            logger.info(

                f"Fallback sizing: {self.config.percent_fallback}% of account, "

                f"Qty={position_qty:.4f}, Risk approx ${risk_usd:.2f}"

            )

        # Apply min/max constraints

        position_qty_constrained = position_qty

        constraint_applied = False

        if position_qty < self.config.min_position_size:

            logger.warning(

                f"Position size {position_qty:.4f} < minimum {self.config.min_position_size}, "

                "clamping to min"

            )

            position_qty_constrained = self.config.min_position_size

            constraint_applied = True

        elif position_qty > self.config.max_position_size:

            logger.warning(

                f"Position size {position_qty:.4f} > maximum {self.config.max_position_size}, "

                "clamping to max"

            )

            position_qty_constrained = self.config.max_position_size

            constraint_applied = True

        # Round to reasonable precision (match min_position_size or smaller)

        # For min_position_size=0.00001, use 0.00001 rounding

        rounding_precision = self.config.min_position_size

        if rounding_precision == Decimal("0.00001"):

            position_qty_rounded = position_qty_constrained.quantize(

                Decimal("0.00001"), rounding=ROUND_HALF_UP

            )

        else:

            position_qty_rounded = position_qty_constrained.quantize(

                Decimal("0.0001"), rounding=ROUND_HALF_UP

            )

        details = {

            "position_qty": position_qty_rounded,

            "risk_usd": float(risk_usd),

            "distance_to_sl": float(distance_to_sl) if distance_to_sl > 0 else None,

            "atr": float(atr) if atr else None,

            "entry_price": float(entry_price),

            "stop_loss_price": float(sl_price) if sl_price > 0 else None,

            "account_balance": float(account_balance),

            "method": method,

            "constrained": constraint_applied,

            "timestamp": timestamp.isoformat(),

        }

        self.last_calculation_timestamp = timestamp

        self.last_calculation_details = details

        return position_qty_rounded, details

    def calculate_risk_dollars(self, account_balance: Decimal) -> Decimal:
        """Get USD risk for given account balance."""

        account_balance = Decimal(str(account_balance))

        risk_usd = (account_balance * self.config.risk_percent / 100).quantize(

            Decimal("0.01"), rounding=ROUND_HALF_UP

        )

        return risk_usd

    def validate_position_size(

        self,

        position_qty: Decimal,

        account_balance: Decimal,

        entry_price: Decimal,

        distance_to_sl: Decimal,

    ) -> Tuple[bool, str]:
        """

        Validate if position size is reasonable.


        Args:

            position_qty: Position quantity to validate

            account_balance: Account balance

            entry_price: Entry price

            distance_to_sl: Distance from entry to stop loss


        Returns:

            Tuple of (is_valid, message)

        """

        if position_qty <= 0:

            return False, "Position quantity must be > 0"

        if distance_to_sl <= 0:

            return False, "Distance to SL must be > 0"

        # Check if position qty * distance / entry >= account risk

        account_balance = Decimal(str(account_balance))

        entry_price = Decimal(str(entry_price))

        position_qty = Decimal(str(position_qty))

        distance_to_sl = Decimal(str(distance_to_sl))

        implied_risk = (position_qty * distance_to_sl).quantize(

            Decimal("0.01"), rounding=ROUND_HALF_UP

        )

        max_risk = (account_balance * self.config.risk_percent / 100).quantize(

            Decimal("0.01"), rounding=ROUND_HALF_UP

        )

        if implied_risk > max_risk * Decimal("1.1"):  # Allow 10% tolerance

            return False, (

                f"Position size {position_qty} implies ${implied_risk:.2f} risk, "

                f"exceeds max ${max_risk:.2f}"

            )

        # Check leverage (position value / account)

        position_value = (position_qty * entry_price).quantize(

            Decimal("0.01"), rounding=ROUND_HALF_UP

        )

        leverage = position_value / account_balance if account_balance > 0 else Decimal("0")

        if leverage > Decimal("10"):  # Max 10x leverage

            return False, f"Position implies {leverage:.1f}x leverage, exceeds 10x"

        return True, "Position size is valid"

    def get_details(self) -> Dict:
        """Get details of last calculation."""

        return {

            "last_calculation": (

                self.last_calculation_timestamp.isoformat()

                if self.last_calculation_timestamp

                else None

            ),

            "details": self.last_calculation_details,

            "config": {

                "risk_percent": float(self.config.risk_percent),

                "atr_multiplier": float(self.config.atr_multiplier),

                "min_position_size": float(self.config.min_position_size),

                "max_position_size": float(self.config.max_position_size),

            },

        }

    def update_config(self, **kwargs) -> None:
        """Update configuration parameters."""

        for key, value in kwargs.items():

            if hasattr(self.config, key):

                setattr(

                    self.config,

                    key,

                    Decimal(str(value)) if isinstance(value, (int, float)) else value,

                )

                logger.info(f"Config updated: {key} = {value}")

            else:

                logger.warning(f"Unknown config parameter: {key}")
