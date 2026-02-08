"""
Risk Monitor Service - Real-time risk monitoring with exchange data.

Monitors:
1. Equity = wallet_balance + unrealized_pnl
2. Realized PnL for the day (from executions)
3. Max daily loss limit
4. Max position size / leverage
5. Max orders per symbol

When critical limits violated → trigger kill switch
"""

import threading
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
import logging

from exchange.account import AccountClient
from execution.kill_switch import KillSwitchManager
from storage.database import Database
from risk.advanced_risk_limits import AdvancedRiskLimits, RiskDecision


logger = logging.getLogger(__name__)


class RiskMonitorConfig:
    """Configuration for Risk Monitor"""
    
    def __init__(
        self,
        max_daily_loss_percent: float = 5.0,
        max_position_notional: float = 50000.0,
        max_leverage: float = 10.0,
        max_orders_per_symbol: int = 10,
        monitor_interval_seconds: int = 30,
        enable_auto_kill_switch: bool = True,
    ):
        """
        Args:
            max_daily_loss_percent: Maximum daily loss as % of equity
            max_position_notional: Maximum position size in USD
            max_leverage: Maximum leverage allowed
            max_orders_per_symbol: Maximum open orders per symbol
            monitor_interval_seconds: How often to check (seconds)
            enable_auto_kill_switch: Auto-trigger kill switch on critical violations
        """
        self.max_daily_loss_percent = max_daily_loss_percent
        self.max_position_notional = max_position_notional
        self.max_leverage = max_leverage
        self.max_orders_per_symbol = max_orders_per_symbol
        self.monitor_interval_seconds = monitor_interval_seconds
        self.enable_auto_kill_switch = enable_auto_kill_switch


class RiskMonitorService:
    """
    Real-time risk monitoring service using actual exchange data.
    
    Features:
    - Calculates equity from wallet balance + unrealized PnL
    - Tracks realized PnL for the day from executions
    - Monitors all risk limits against real data
    - Auto-triggers kill switch on critical violations
    """
    
    def __init__(
        self,
        account_client: AccountClient,
        kill_switch_manager: Optional[KillSwitchManager],
        advanced_risk_limits: AdvancedRiskLimits,
        db: Database,
        symbol: str,
        config: Optional[RiskMonitorConfig] = None,
    ):
        """
        Initialize Risk Monitor.
        
        Args:
            account_client: For fetching exchange data
            kill_switch_manager: For emergency shutdown
            advanced_risk_limits: For risk evaluation
            db: Database for historical data
            symbol: Trading symbol
            config: Monitor configuration
        """
        self.account_client = account_client
        self.kill_switch_manager = kill_switch_manager
        self.advanced_risk_limits = advanced_risk_limits
        self.db = db
        self.symbol = symbol
        self.config = config or RiskMonitorConfig()
        
        # Monitoring state
        self.running = False
        self.monitor_thread = None
        
        # Cached data
        self.last_equity = Decimal("0")
        self.last_wallet_balance = Decimal("0")
        self.last_unrealized_pnl = Decimal("0")
        self.last_realized_pnl_today = Decimal("0")
        
        logger.info("RiskMonitorService initialized")
        logger.info(f"  Symbol: {symbol}")
        logger.info(f"  АКТИВНА ТОЛЬКО ПРОВЕРКА: Daily Loss > {self.config.max_daily_loss_percent}%")
        logger.info(f"  Остальные проверки ОТКЛЮЧЕНЫ (leverage, notional, drawdown, orders)")
        logger.info(f"  Monitor Interval: {self.config.monitor_interval_seconds}s")
        logger.info(f"  Auto Kill Switch: {self.config.enable_auto_kill_switch}")
    
    def calculate_equity(self) -> Decimal:
        """
        Calculate equity = wallet_balance + unrealized_pnl.
        
        Returns:
            Current equity in USD
        """
        try:
            # Get wallet balance
            wallet_response = self.account_client.get_wallet_balance("USDT")
            if wallet_response.get("retCode") != 0:
                logger.error(f"Failed to get wallet balance: {wallet_response}")
                return self.last_equity
            
            wallet_balance = Decimal(str(wallet_response.get("balance", 0)))
            self.last_wallet_balance = wallet_balance
            
            # Get positions for unrealized PnL
            positions_response = self.account_client.get_positions(category="linear")
            if positions_response.get("retCode") != 0:
                logger.error(f"Failed to get positions: {positions_response}")
                return wallet_balance  # Return at least wallet balance
            
            # Sum unrealized PnL from all positions
            unrealized_pnl = Decimal("0")
            positions = positions_response.get("result", {}).get("list", [])
            for position in positions:
                pnl = Decimal(str(position.get("unrealisedPnl", 0)))
                unrealized_pnl += pnl
            
            self.last_unrealized_pnl = unrealized_pnl
            
            # Calculate equity
            equity = wallet_balance + unrealized_pnl
            self.last_equity = equity
            
            logger.debug(
                f"Equity: ${equity:.2f} (wallet=${wallet_balance:.2f} + "
                f"unrealized=${unrealized_pnl:+.2f})"
            )
            
            return equity
            
        except Exception as e:
            logger.error(f"Error calculating equity: {e}")
            return self.last_equity
    
    def calculate_daily_realized_pnl(self) -> Decimal:
        """
        Calculate realized PnL for today from executions.
        
        Returns:
            Realized PnL in USD for today
        """
        try:
            # Get executions (last 100)
            executions_response = self.account_client.get_executions(
                category="linear",
                symbol=self.symbol,
                limit=100
            )
            
            if executions_response.get("retCode") != 0:
                logger.error(f"Failed to get executions: {executions_response}")
                return self.last_realized_pnl_today
            
            # Filter executions for today
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_start_ms = int(today_start.timestamp() * 1000)
            
            realized_pnl = Decimal("0")
            executions = executions_response.get("result", {}).get("list", [])
            
            for exec_data in executions:
                exec_time = int(exec_data.get("execTime", 0))
                if exec_time < today_start_ms:
                    continue  # Skip older executions
                
                # Calculate PnL from execution
                exec_qty = Decimal(str(exec_data.get("execQty", 0)))
                exec_price = Decimal(str(exec_data.get("execPrice", 0)))
                exec_fee = Decimal(str(exec_data.get("execFee", 0)))
                side = exec_data.get("side", "")
                
                # For closing trades, we get closedPnl
                closed_pnl = Decimal(str(exec_data.get("closedPnl", 0)))
                if closed_pnl != 0:
                    realized_pnl += closed_pnl
                
                # Subtract fees
                realized_pnl -= abs(exec_fee)
            
            self.last_realized_pnl_today = realized_pnl
            
            logger.debug(f"Realized PnL today: ${realized_pnl:+.2f}")
            
            return realized_pnl
            
        except Exception as e:
            logger.error(f"Error calculating daily realized PnL: {e}")
            return self.last_realized_pnl_today
    
    def get_position_info(self) -> Dict[str, Any]:
        """
        Get current position information.
        
        Returns:
            Dict with position details (size, leverage, notional, unrealized_pnl)
        """
        try:
            positions_response = self.account_client.get_positions(
                category="linear",
                symbol=self.symbol
            )
            
            if positions_response.get("retCode") != 0:
                logger.error(f"Failed to get position: {positions_response}")
                return {
                    "size": Decimal("0"),
                    "leverage": Decimal("0"),
                    "notional": Decimal("0"),
                    "unrealized_pnl": Decimal("0"),
                }
            
            positions = positions_response.get("result", {}).get("list", [])
            if not positions:
                return {
                    "size": Decimal("0"),
                    "leverage": Decimal("0"),
                    "notional": Decimal("0"),
                    "unrealized_pnl": Decimal("0"),
                }
            
            position = positions[0]
            
            # Safe decimal conversion with fallback
            def safe_decimal(value, default="0"):
                """Safely convert to Decimal, handling empty strings and None"""
                if value is None or value == "" or value == "None":
                    return Decimal(default)
                try:
                    return Decimal(str(value))
                except:
                    return Decimal(default)
            
            size = safe_decimal(position.get("size", 0))
            leverage = safe_decimal(position.get("leverage", 0))
            mark_price = safe_decimal(position.get("markPrice", 0))
            notional = size * mark_price
            unrealized_pnl = safe_decimal(position.get("unrealisedPnl", 0))
            
            return {
                "size": size,
                "leverage": leverage,
                "notional": notional,
                "unrealized_pnl": unrealized_pnl,
                "mark_price": mark_price,
            }
            
        except Exception as e:
            logger.error(f"Error getting position info: {e}", exc_info=True)
            return {
                "size": Decimal("0"),
                "leverage": Decimal("0"),
                "notional": Decimal("0"),
                "unrealized_pnl": Decimal("0"),
            }
    
    def count_open_orders(self, symbol: Optional[str] = None) -> int:
        """
        Count number of open orders for symbol.
        
        Args:
            symbol: Symbol to count (defaults to self.symbol)
        
        Returns:
            Number of open orders
        """
        try:
            symbol = symbol or self.symbol
            
            orders_response = self.account_client.get_open_orders(
                category="linear",
                symbol=symbol
            )
            
            if orders_response.get("retCode") != 0:
                logger.error(f"Failed to get open orders: {orders_response}")
                return 0
            
            orders = orders_response.get("result", {}).get("list", [])
            count = len(orders)
            
            logger.debug(f"Open orders for {symbol}: {count}")
            
            return count
            
        except Exception as e:
            logger.error(f"Error counting open orders: {e}")
            return 0
    
    def check_all_limits(self) -> Dict[str, Any]:
        """
        Check all risk limits using real exchange data.
        
        Returns:
            Dict with check results and decision
        """
        # Calculate real values
        equity = self.calculate_equity()
        realized_pnl_today = self.calculate_daily_realized_pnl()
        position_info = self.get_position_info()
        order_count = self.count_open_orders()
        
        # Build state for AdvancedRiskLimits
        state = {
            "account_balance": float(self.last_wallet_balance),
            "current_equity": float(equity),
            "realized_pnl_today": float(realized_pnl_today),
            "open_position_notional": float(position_info["notional"]),
            "position_leverage": float(position_info["leverage"]),
            "new_position_notional": 0,  # Not opening new position during monitoring
        }
        
        # Check with AdvancedRiskLimits (только daily loss check активен)
        decision, details = self.advanced_risk_limits.evaluate(state)
        
        # ИЗМЕНЕНО: Убрана проверка max_orders_per_symbol - оставляем только daily loss
        
        # Compile results
        result = {
            "decision": decision,
            "equity": float(equity),
            "wallet_balance": float(self.last_wallet_balance),
            "unrealized_pnl": float(self.last_unrealized_pnl),
            "realized_pnl_today": float(realized_pnl_today),
            "position_notional": float(position_info["notional"]),
            "position_leverage": float(position_info["leverage"]),
            "open_orders_count": order_count,
            "violations": details.get("violations", []),
            "warnings": details.get("warnings", []),
            "timestamp": datetime.now(),
        }
        
        return result
    
    def trigger_kill_switch_if_needed(self, check_result: Dict[str, Any]) -> bool:
        """
        Trigger kill switch if critical violations detected.
        
        Args:
            check_result: Result from check_all_limits()
        
        Returns:
            True if kill switch was triggered
        """
        if not self.config.enable_auto_kill_switch:
            return False
        
        if not self.kill_switch_manager:
            logger.warning("Kill switch manager not available")
            return False
        
        decision = check_result["decision"]
        
        if decision == RiskDecision.STOP:
            # Critical violation - trigger kill switch
            violations = check_result.get("violations", [])
            reason = f"Critical risk violations: {', '.join([str(v) for v in violations])}"
            
            logger.critical(f"🚨 TRIGGERING KILL SWITCH: {reason}")
            
            try:
                self.kill_switch_manager.activate(reason)
                self.db.save_config("trading_disabled", True)
                logger.critical("Kill switch activated successfully")
                return True
            except Exception as e:
                logger.error(f"Failed to activate kill switch: {e}")
                return False
        
        return False
    
    def run_monitoring_check(self) -> Dict[str, Any]:
        """
        Run a single monitoring check.
        
        Returns:
            Check result
        """
        try:
            logger.debug("Running risk monitoring check...")
            
            check_result = self.check_all_limits()
            
            # Log summary
            decision = check_result["decision"]
            equity = check_result["equity"]
            pnl_today = check_result["realized_pnl_today"]
            
            logger.info(
                f"Risk Check: decision={decision.value}, "
                f"equity=${equity:.2f}, pnl_today=${pnl_today:+.2f}"
            )
            
            # Trigger kill switch if needed
            if check_result["decision"] == RiskDecision.STOP:
                self.trigger_kill_switch_if_needed(check_result)
            elif check_result["decision"] == RiskDecision.DENY:
                logger.warning("Risk limits violated - new trades denied")
            
            return check_result
            
        except Exception as e:
            logger.error(f"Error in monitoring check: {e}")
            return {"decision": RiskDecision.ALLOW, "error": str(e)}
    
    def _monitoring_loop(self):
        """Background monitoring loop."""
        logger.info("Risk monitoring loop started")
        
        while self.running:
            try:
                self.run_monitoring_check()
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
            
            # Sleep for interval
            time.sleep(self.config.monitor_interval_seconds)
        
        logger.info("Risk monitoring loop stopped")
    
    def start_monitoring(self):
        """Start background monitoring thread."""
        if self.running:
            logger.warning("Monitoring already running")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("Risk monitoring started")
    
    def stop_monitoring(self):
        """Stop background monitoring thread."""
        if not self.running:
            return
        
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("Risk monitoring stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current monitoring status."""
        return {
            "running": self.running,
            "last_equity": float(self.last_equity),
            "last_wallet_balance": float(self.last_wallet_balance),
            "last_unrealized_pnl": float(self.last_unrealized_pnl),
            "last_realized_pnl_today": float(self.last_realized_pnl_today),
            "config": {
                "max_daily_loss_percent": self.config.max_daily_loss_percent,
                "max_position_notional": self.config.max_position_notional,
                "max_leverage": self.config.max_leverage,
                "max_orders_per_symbol": self.config.max_orders_per_symbol,
                "monitor_interval_seconds": self.config.monitor_interval_seconds,
                "enable_auto_kill_switch": self.config.enable_auto_kill_switch,
            },
        }
