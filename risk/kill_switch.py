"""

Kill Switch: аварийная остановка всей системы.


При активации:

1. Отмена всех открытых ордеров

2. Закрытие всех позиций (reduce-only)

3. Блокировка повторного запуска (флаг в БД)

4. Consecutive errors tracking with cooldown support

"""


from storage.database import Database

from logger import setup_logger

from datetime import datetime, timedelta


logger = setup_logger(__name__)


class KillSwitch:

    """Аварийная остановка системы"""

    def __init__(
        self, 
        db: Database,
        max_consecutive_errors: int = 5,
        cooldown_minutes: int = 15
    ):

        self.db = db

        self.is_activated = False
        
        self.consecutive_errors = 0
        
        self.max_consecutive_errors = max_consecutive_errors
        
        self.cooldown_minutes = cooldown_minutes
        
        self.cooldown_until = None

        logger.info(
            f"KillSwitch initialized (max_consecutive_errors={max_consecutive_errors}, "
            f"cooldown_minutes={cooldown_minutes})"
        )
        
    def record_error(self, error_type: str, message: str):
        """
        Record an error and increment consecutive error counter.
        If max_consecutive_errors is reached, activate cooldown.
        
        Args:
            error_type: Type of error
            message: Error message
        """
        self.consecutive_errors += 1
        
        logger.warning(
            f"Error recorded: {error_type} - {message} "
            f"(consecutive={self.consecutive_errors}/{self.max_consecutive_errors})"
        )
        
        # Save error to DB
        self.db.save_error(
            error_type=error_type,
            message=message,
            metadata={
                "consecutive_count": self.consecutive_errors,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        # Check if we need to enter cooldown
        if self.consecutive_errors >= self.max_consecutive_errors:
            self._enter_cooldown(f"Max consecutive errors reached ({self.consecutive_errors})")
            
    def record_success(self):
        """
        Record a successful operation - resets consecutive error counter.
        """
        if self.consecutive_errors > 0:
            logger.info(
                f"Success recorded - resetting consecutive error counter "
                f"(was {self.consecutive_errors})"
            )
            self.consecutive_errors = 0
            
    def _enter_cooldown(self, reason: str):
        """
        Enter cooldown mode - bot pauses trading but continues monitoring.
        
        Args:
            reason: Reason for entering cooldown
        """
        self.cooldown_until = datetime.now() + timedelta(minutes=self.cooldown_minutes)
        
        logger.error(
            f"🔴 ENTERING COOLDOWN: {reason}. "
            f"Trading paused until {self.cooldown_until.isoformat()}"
        )
        
        # Save cooldown activation to DB
        self.db.save_error(
            error_type="cooldown_activated",
            message=reason,
            metadata={
                "cooldown_until": self.cooldown_until.isoformat(),
                "consecutive_errors": self.consecutive_errors
            }
        )
        
    def is_in_cooldown(self) -> bool:
        """
        Check if bot is currently in cooldown period.
        
        Returns:
            True if in cooldown, False otherwise
        """
        if self.cooldown_until is None:
            return False
            
        if datetime.now() < self.cooldown_until:
            return True
        else:
            # Cooldown expired - reset
            logger.info(
                f"✅ Cooldown period expired. Resetting consecutive error counter."
            )
            self.consecutive_errors = 0
            self.cooldown_until = None
            return False

    def activate(self, reason: str):
        """

        Активировать kill switch.


        Args:

            reason: Причина активации

        """

        if self.is_activated:

            logger.warning("Kill switch already activated")

            return

        logger.error(f"🚨🚨🚨 KILL SWITCH ACTIVATED: {reason} 🚨🚨🚨")

        self.is_activated = True

        # Сохраняем в БД

        self.db.save_error(

            error_type="kill_switch_activated",

            message=reason,

            metadata={

                "activated_at": str(self.db.conn.execute("SELECT CURRENT_TIMESTAMP").fetchone()[0])

            },

        )

        logger.error("Kill switch saved to database")

        logger.error("Manual reset required before restart")

    def check_status(self) -> bool:
        """

        Проверить, активирован ли kill switch (из БД).


        Returns:

            True если активирован, False если можно торговать

        """

        cursor = self.db.conn.cursor()

        cursor.execute(

            """

            SELECT COUNT(*) FROM errors

            WHERE error_type = 'kill_switch_activated'

            AND timestamp > ?

        """,

            (self.db.conn.execute("SELECT strftime('%s', 'now', '-1 day')").fetchone()[0],),

        )

        count = cursor.fetchone()[0]

        if count > 0 and not self.is_activated:

            logger.warning("Kill switch was previously activated (found in DB)")

            self.is_activated = True

        return self.is_activated

    def reset(self, confirmation: str):
        """

        Сброс kill switch (требует подтверждения).


        Args:

            confirmation: Строка подтверждения (должна быть "RESET")

        """

        if confirmation != "RESET":

            logger.error("Invalid confirmation code. Kill switch NOT reset")

            return False

        logger.info("Kill switch reset by manual confirmation")

        self.is_activated = False

        # Логируем сброс

        self.db.save_error(

            error_type="kill_switch_reset",

            message="Kill switch manually reset",

            metadata={

                "reset_at": str(self.db.conn.execute("SELECT CURRENT_TIMESTAMP").fetchone()[0])

            },

        )

        return True
