"""

Advanced Risk Limits Management - D2 EPIC


Unified risk evaluation contract:

- evaluate(state) -> RiskDecision(ALLOW/DENY/STOP)


Validates:

1. Max leverage - prevents over-leverage

2. Max notional - limits position size in USD

3. Daily loss limit - maximum losses per day

4. Max drawdown - cumulative underwater percentage


When limits exceeded:

- DENY: Block new positions but keep existing

- STOP: Trigger kill switch for critical violations

"""


from datetime import datetime

from decimal import Decimal

from enum import Enum

from typing import Dict, Optional, Tuple

import logging


from storage.database import Database


logger = logging.getLogger(__name__)


class RiskDecision(Enum):

    """Risk evaluation decision."""

    ALLOW = "allow"  # Trade allowed

    DENY = "deny"  # New trades blocked (existing OK)

    STOP = "stop"  # Critical - trigger kill switch


class RiskCheckResult:

    """Result of a single risk check."""

    def __init__(

        self,

        passed: bool,

        check_name: str,

        current_value: Decimal,

        limit_value: Decimal,

        severity: str = "warning",  # warning, critical

    ):

        self.passed = passed

        self.check_name = check_name

        self.current_value = current_value

        self.limit_value = limit_value

        self.severity = severity

    def __repr__(self):

        status = "✓" if self.passed else "✗"

        return (

            f"{status} {self.check_name}: {self.current_value:.2f} "

            f"({'<' if self.passed else '>'} {self.limit_value:.2f})"

        )


class RiskLimitsConfig:

    """Configuration for risk limits."""

    def __init__(

        self,

        max_leverage: Decimal = Decimal("10"),  # 10x max

        max_notional: Decimal = Decimal("50000"),  # $50k max per position

        daily_loss_limit_percent: Decimal = Decimal("5"),  # 5% of account

        max_drawdown_percent: Decimal = Decimal("10"),  # 10% underwater

        enable_leverage_check: bool = True,

        enable_notional_check: bool = True,

        enable_daily_loss_check: bool = True,

        enable_drawdown_check: bool = True,

    ):
        """

        Args:

            max_leverage: Maximum allowed leverage (10 = 10x)

            max_notional: Maximum position size in USD

            daily_loss_limit_percent: Max daily loss as % of account

            max_drawdown_percent: Max drawdown from session start

            enable_*: Enable/disable specific checks

        """

        self.max_leverage = max_leverage

        self.max_notional = max_notional

        self.daily_loss_limit_percent = daily_loss_limit_percent

        self.max_drawdown_percent = max_drawdown_percent

        self.enable_leverage_check = enable_leverage_check

        self.enable_notional_check = enable_notional_check

        self.enable_daily_loss_check = enable_daily_loss_check

        self.enable_drawdown_check = enable_drawdown_check


class AdvancedRiskLimits:

    """

    Advanced risk management with unified decision contract.


    Evaluates trading state against multiple risk constraints:

    1. Leverage limit - prevents dangerous over-leverage

    2. Notional limit - caps position size

    3. Daily loss - cumulative losses in current day

    4. Drawdown - equity underwater from session start


    Returns: RiskDecision(ALLOW/DENY/STOP) with details

    """

    def __init__(self, db: Database, config: Optional[RiskLimitsConfig] = None):
        """

        Initialize Advanced Risk Limits.


        Args:

            db: Database instance

            config: RiskLimitsConfig (defaults to conservative values)

        """

        self.db = db

        self.config = config or RiskLimitsConfig()

        # Session tracking

        self.session_start_time = datetime.now()

        self.session_start_equity = Decimal("0")

        self.max_equity = Decimal("0")

        # Daily tracking

        self.daily_start_realized_pnl = Decimal("0")

        self.last_daily_reset = datetime.now().date()

        logger.info("Advanced Risk Limits initialized")

        logger.info(f"  Max Leverage: {self.config.max_leverage}x")

        logger.info(f"  Max Notional: ${self.config.max_notional}")

        logger.info(f"  Daily Loss Limit: {self.config.daily_loss_limit_percent}%")

        logger.info(f"  Max Drawdown: {self.config.max_drawdown_percent}%")

    def set_session_start_equity(self, equity: Decimal) -> None:
        """Set starting equity for the session."""

        self.session_start_equity = equity

        self.max_equity = equity

        logger.info(f"Session start equity: ${self.session_start_equity:.2f}")

    def evaluate(self, state: Dict) -> Tuple[RiskDecision, Dict]:
        """

        Evaluate trading state against all risk limits.


        Args:

            state: Dict with:

            {

                "account_balance": Decimal,      # Total account balance

                "open_position_notional": Decimal, # USD value of open position

                "position_leverage": Decimal,    # Current leverage of position

                "new_position_notional": Decimal, # Proposed new position USD value

                "realized_pnl_today": Decimal,  # Today's realized PnL

                "current_equity": Decimal,      # Current equity (balance + unrealized)

            }


        Returns:

            Tuple of (RiskDecision, Dict with details)

            {

                "decision": RiskDecision,

                "reason": str,

                "violations": List[RiskCheckResult],

                "warnings": List[RiskCheckResult],

                "checks": Dict of all check results

            }

        """

        # Reset daily counters if new day

        self._check_daily_reset()

        violations = []

        warnings = []

        checks_detail = {}

        # 1. Check leverage

        if self.config.enable_leverage_check:

            leverage_check = self._check_leverage(state)

            checks_detail["leverage"] = leverage_check

            if not leverage_check.passed:

                (violations if leverage_check.severity == "critical" else warnings).append(

                    leverage_check

                )

        # 2. Check notional (position size)

        if self.config.enable_notional_check:

            notional_check = self._check_notional(state)

            checks_detail["notional"] = notional_check

            if not notional_check.passed:

                (violations if notional_check.severity == "critical" else warnings).append(

                    notional_check

                )

        # 3. Check daily loss

        if self.config.enable_daily_loss_check:

            daily_loss_check = self._check_daily_loss(state)

            checks_detail["daily_loss"] = daily_loss_check

            if not daily_loss_check.passed:

                (violations if daily_loss_check.severity == "critical" else warnings).append(

                    daily_loss_check

                )

        # 4. Check drawdown

        if self.config.enable_drawdown_check:

            drawdown_check = self._check_drawdown(state)

            checks_detail["drawdown"] = drawdown_check

            if not drawdown_check.passed:

                (violations if drawdown_check.severity == "critical" else warnings).append(

                    drawdown_check

                )

        # Determine decision

        if violations:

            # Critical violations - need kill switch

            critical_violations = [v for v in violations if v.severity == "critical"]

            if critical_violations:

                decision = RiskDecision.STOP

                reason = (

                    f"CRITICAL violations: {', '.join(v.check_name for v in critical_violations)}"

                )

                logger.critical(f"Risk evaluation: STOP - {reason}")

            else:

                decision = RiskDecision.DENY

                reason = f"Violations: {', '.join(v.check_name for v in violations)}"

                logger.warning(f"Risk evaluation: DENY - {reason}")

        elif warnings:

            decision = RiskDecision.DENY

            reason = f"Warnings: {', '.join(w.check_name for w in warnings)}"

            logger.warning(f"Risk evaluation: DENY - {reason}")

        else:

            decision = RiskDecision.ALLOW

            reason = "All risk checks passed"

            logger.debug("Risk evaluation: ALLOW")

        # Update equity tracking

        if state.get("current_equity"):

            current_equity = Decimal(str(state["current_equity"]))

            if current_equity > self.max_equity:

                self.max_equity = current_equity

        return (

            decision,

            {

                "decision": decision,

                "reason": reason,

                "violations": violations,

                "warnings": warnings,

                "checks": checks_detail,

                "timestamp": datetime.now(),

            },

        )

    def _check_leverage(self, state: Dict) -> RiskCheckResult:
        """Check if position leverage exceeds limit."""

        leverage = Decimal(str(state.get("position_leverage", 0)))

        max_lev = self.config.max_leverage

        # Severity: critical if > 2x over limit

        severity = "critical" if leverage > max_lev * 2 else "warning"

        passed = leverage <= max_lev

        logger.debug(f"Leverage check: {leverage:.1f}x <= {max_lev:.1f}x? {passed}")

        return RiskCheckResult(

            passed=passed,

            check_name="Leverage",

            current_value=leverage,

            limit_value=max_lev,

            severity=severity if not passed else "warning",

        )

    def _check_notional(self, state: Dict) -> RiskCheckResult:
        """Check if position notional exceeds limit."""

        position_notional = Decimal(str(state.get("open_position_notional", 0)))

        new_position_notional = Decimal(str(state.get("new_position_notional", 0)))

        total_notional = position_notional + new_position_notional

        max_notional = self.config.max_notional

        # Severity: critical if > 50% over limit

        overage_percent = (

            (total_notional - max_notional) / max_notional

            if total_notional > max_notional

            else Decimal(0)

        )

        severity = "critical" if overage_percent > Decimal("0.5") else "warning"

        passed = total_notional <= max_notional

        logger.debug(f"Notional check: ${total_notional:.2f} <= ${max_notional:.2f}? {passed}")

        return RiskCheckResult(

            passed=passed,

            check_name="Notional",

            current_value=total_notional,

            limit_value=max_notional,

            severity=severity if not passed else "warning",

        )

    def _check_daily_loss(self, state: Dict) -> RiskCheckResult:
        """Check if daily loss exceeds limit."""

        realized_pnl_today = Decimal(str(state.get("realized_pnl_today", 0)))

        account_balance = Decimal(str(state.get("account_balance", 1)))

        max_daily_loss = account_balance * self.config.daily_loss_limit_percent / 100

        daily_loss = -min(realized_pnl_today, 0)  # Negative PnL only

        # Loss percent

        loss_percent = (daily_loss / account_balance * 100) if account_balance > 0 else Decimal(0)

        # Severity: critical if > 80% of limit

        severity = "critical" if daily_loss > max_daily_loss * Decimal("0.8") else "warning"

        passed = daily_loss <= max_daily_loss

        logger.debug(

            f"Daily loss check: ${daily_loss:.2f} ({loss_percent:.2f}%) "

            f"<= ${max_daily_loss:.2f}? {passed}"

        )

        return RiskCheckResult(

            passed=passed,

            check_name="Daily Loss",

            current_value=loss_percent,

            limit_value=self.config.daily_loss_limit_percent,

            severity=severity if not passed else "warning",

        )

    def _check_drawdown(self, state: Dict) -> RiskCheckResult:
        """Check if underwater percentage exceeds limit."""

        current_equity = Decimal(str(state.get("current_equity", 1)))

        # Drawdown is how far below peak

        if self.session_start_equity > 0:

            drawdown_amount = self.max_equity - current_equity

            drawdown_percent = (

                (drawdown_amount / self.max_equity * 100) if self.max_equity > 0 else Decimal(0)

            )

        else:

            drawdown_percent = Decimal(0)

        max_drawdown = self.config.max_drawdown_percent

        # Severity: critical if > 80% of limit

        severity = "critical" if drawdown_percent > max_drawdown * Decimal("0.8") else "warning"

        passed = drawdown_percent <= max_drawdown

        logger.debug(f"Drawdown check: {drawdown_percent:.2f}% <= {max_drawdown:.2f}%? {passed}")

        return RiskCheckResult(

            passed=passed,

            check_name="Drawdown",

            current_value=drawdown_percent,

            limit_value=max_drawdown,

            severity=severity if not passed else "warning",

        )

    def _check_daily_reset(self) -> None:
        """Reset daily counters if new day."""

        today = datetime.now().date()

        if today != self.last_daily_reset:

            logger.info(f"Daily reset: {self.last_daily_reset} -> {today}")

            self.last_daily_reset = today

            self.daily_start_realized_pnl = Decimal("0")

    def log_trade_realization(self, realized_pnl: Decimal, symbol: str) -> None:
        """Log a realized PnL from trade closure."""

        logger.info(

            f"Trade realized: {symbol} PnL={realized_pnl:+.2f} "

            f"(daily={self.daily_start_realized_pnl + realized_pnl:+.2f})"

        )

    def get_status(self) -> Dict:
        """Get current risk status."""

        time_elapsed = datetime.now() - self.session_start_time

        return {

            "session_start": self.session_start_time.isoformat(),

            "session_elapsed_seconds": int(time_elapsed.total_seconds()),

            "session_start_equity": float(self.session_start_equity),

            "max_equity": float(self.max_equity),

            "daily_start_realized_pnl": float(self.daily_start_realized_pnl),

            "last_daily_reset": self.last_daily_reset.isoformat(),

            "config": {

                "max_leverage": float(self.config.max_leverage),

                "max_notional": float(self.config.max_notional),

                "daily_loss_limit_percent": float(self.config.daily_loss_limit_percent),

                "max_drawdown_percent": float(self.config.max_drawdown_percent),

            },

        }

    def disable_check(self, check_name: str) -> None:
        """Disable a specific risk check."""

        check_map = {

            "leverage": "enable_leverage_check",

            "notional": "enable_notional_check",

            "daily_loss": "enable_daily_loss_check",

            "drawdown": "enable_drawdown_check",

        }

        if check_name in check_map:

            setattr(self.config, check_map[check_name], False)

            logger.info(f"Risk check disabled: {check_name}")

    def enable_check(self, check_name: str) -> None:
        """Enable a specific risk check."""

        check_map = {

            "leverage": "enable_leverage_check",

            "notional": "enable_notional_check",

            "daily_loss": "enable_daily_loss_check",

            "drawdown": "enable_drawdown_check",

        }

        if check_name in check_map:

            setattr(self.config, check_map[check_name], True)

            logger.info(f"Risk check enabled: {check_name}")
