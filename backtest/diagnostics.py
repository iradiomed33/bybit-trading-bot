"""

Backtest diagnostics: почему нет сделок?

"""


from logger import setup_logger


logger = setup_logger(__name__)


class BacktestDiagnostics:

    """Диагностика работы стратегий в бэктесте"""

    def __init__(self):

        self.signal_attempts = 0

        self.blocked_reasons = {}

        self.strategy_signals = {}

    def log_signal_attempt(self, strategy: str, result: str):
        """Логировать попытку генерации сигнала"""

        self.signal_attempts += 1

        if strategy not in self.strategy_signals:

            self.strategy_signals[strategy] = {"attempts": 0, "generated": 0}

        self.strategy_signals[strategy]["attempts"] += 1

        if result == "generated":

            self.strategy_signals[strategy]["generated"] += 1

    def log_block(self, reason: str):
        """Логировать блокировку"""

        if reason not in self.blocked_reasons:

            self.blocked_reasons[reason] = 0

        self.blocked_reasons[reason] += 1

    def print_report(self):
        """Вывести отчёт"""

        logger.info("\n=== Backtest Diagnostics ===")

        logger.info(f"Total signal attempts: {self.signal_attempts}")

        logger.info("\nStrategy breakdown:")

        for strategy, stats in self.strategy_signals.items():

            if stats["attempts"] > 0:

                rate = stats["generated"] / stats["attempts"] * 100

            else:

                rate = 0

            logger.info(f"  {strategy}: {stats['generated']}/{stats['attempts']} ({rate:.1f}%)")

        if self.blocked_reasons:

            logger.info("\nBlocking reasons:")

            for reason, count in sorted(

                self.blocked_reasons.items(), key=lambda x: x[1], reverse=True

            ):

                logger.info(f"  {reason}: {count}")

        else:

            msg = "\nNo blocks detected (strategies didn't generate signals)"

            logger.info(msg)
