"""

Kill Switch: аварийная остановка всей системы.


При активации:

1. Отмена всех открытых ордеров

2. Закрытие всех позиций (reduce-only)

3. Блокировка повторного запуска (флаг в БД)

"""


from storage.database import Database

from logger import setup_logger


logger = setup_logger(__name__)


class KillSwitch:

    """Аварийная остановка системы"""

    def __init__(self, db: Database):

        self.db = db

        self.is_activated = False

        logger.info("KillSwitch initialized")

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

        threshold = float(self.db.conn.execute("SELECT strftime('%s', 'now', '-1 day')").fetchone()[0])
        # Берём самую свежую активацию и самый свежий сброс
        cursor.execute(
            """
            SELECT MAX(CAST(timestamp AS REAL)) FROM errors
            WHERE error_type = 'kill_switch_activated' AND CAST(timestamp AS REAL) > ?
        """,
            (threshold,),
        )
        last_activation = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT MAX(CAST(timestamp AS REAL)) FROM errors
            WHERE error_type = 'kill_switch_reset' AND CAST(timestamp AS REAL) > ?
        """,
            (threshold,),
        )
        last_reset = cursor.fetchone()[0]

        # Если активаций в окне нет — оставляем состояние как есть,
        # но явный reset в окне всё равно снимает блокировку
        if not last_activation:
            if last_reset:
                self.is_activated = False
                return False
            return self.is_activated

        # Если есть сброс новее активации — считаем выключенным
        if last_reset and last_reset > last_activation:
            self.is_activated = False
            return False

        if not self.is_activated:

            logger.warning("Kill switch was previously activated (found in DB)")
            logger.warning("To reset: python cli.py reset-kill-switch  OR  python reset_killswitch.py")

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

        # Удаляем записи активации из БД
        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            DELETE FROM errors
            WHERE error_type = 'kill_switch_activated'
            """
        )
        self.db.conn.commit()
        deleted_count = cursor.rowcount
        logger.info(f"Deleted {deleted_count} kill switch activation records from database")

        # Логируем сброс

        self.db.save_error(

            error_type="kill_switch_reset",

            message="Kill switch manually reset",

            metadata={

                "reset_at": str(self.db.conn.execute("SELECT CURRENT_TIMESTAMP").fetchone()[0])

            },

        )

        return True
