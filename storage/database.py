"""

SQLite база данных для хранения состояния бота.


Таблицы:

- signals: Торговые сигналы от стратегий

- orders: Все ордера (локальная копия)

- executions: Исполненные сделки

- positions: Снапшоты позиций

- errors: Лог ошибок

- config_snapshots: История конфигураций

"""


import sqlite3

import json

from datetime import datetime

from typing import Optional, Dict, Any, List

from pathlib import Path

from logger import setup_logger


logger = setup_logger(__name__)


class Database:

    """Управление SQLite базой данных"""

    def __init__(self, db_path: str = "storage/bot_state.db"):
        """

        Args:

            db_path: Путь к файлу базы данных

        """

        self.db_path = db_path

        # Создаём директорию storage если её нет

        Path(db_path).parent.mkdir(exist_ok=True)

        self.conn: Optional[sqlite3.Connection] = None

        self._init_db()

        logger.info(f"Database initialized: {db_path}")

    def _init_db(self):
        """Инициализация базы данных и создание таблиц"""

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)

        self.conn.row_factory = sqlite3.Row  # Доступ к колонкам по имени

        cursor = self.conn.cursor()

        # Таблица сигналов

        cursor.execute(

            """

            CREATE TABLE IF NOT EXISTS signals (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                timestamp REAL NOT NULL,

                strategy TEXT NOT NULL,

                symbol TEXT NOT NULL,

                signal_type TEXT NOT NULL,  -- 'long', 'short', 'close'

                price REAL,

                metadata TEXT,  -- JSON с дополнительными данными

                created_at TEXT DEFAULT CURRENT_TIMESTAMP

            )

        """

        )

        # Таблица ордеров

        cursor.execute(

            """

            CREATE TABLE IF NOT EXISTS orders (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                order_id TEXT UNIQUE NOT NULL,  -- ID от биржи

                order_link_id TEXT UNIQUE,      -- Наш клиентский ID

                symbol TEXT NOT NULL,

                side TEXT NOT NULL,             -- 'Buy', 'Sell'

                order_type TEXT NOT NULL,       -- 'Limit', 'Market'

                price REAL,

                qty REAL NOT NULL,

                filled_qty REAL DEFAULT 0,

                status TEXT NOT NULL,           -- 'New', 'PartiallyFilled', 'Filled', 'Cancelled'

                time_in_force TEXT,

                created_time REAL,

                updated_time REAL,

                metadata TEXT,                  -- JSON

                created_at TEXT DEFAULT CURRENT_TIMESTAMP

            )

        """

        )

        # Таблица исполнений (executions/trades)

        cursor.execute(

            """

            CREATE TABLE IF NOT EXISTS executions (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                exec_id TEXT UNIQUE NOT NULL,

                order_id TEXT NOT NULL,

                order_link_id TEXT,

                symbol TEXT NOT NULL,

                side TEXT NOT NULL,

                price REAL NOT NULL,

                qty REAL NOT NULL,

                exec_fee REAL,

                exec_time REAL NOT NULL,

                is_maker INTEGER,  -- 0 = taker, 1 = maker

                metadata TEXT,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (order_id) REFERENCES orders(order_id)

            )

        """

        )

        # Таблица позиций (snapshots)

        cursor.execute(

            """

            CREATE TABLE IF NOT EXISTS positions (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                timestamp REAL NOT NULL,

                symbol TEXT NOT NULL,

                side TEXT NOT NULL,          -- 'Buy', 'Sell', 'None'

                size REAL NOT NULL,

                entry_price REAL,

                mark_price REAL,

                liquidation_price REAL,

                leverage REAL,

                unrealised_pnl REAL,

                realised_pnl REAL,

                metadata TEXT,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP

            )

        """

        )

        # Таблица ошибок

        cursor.execute(

            """

            CREATE TABLE IF NOT EXISTS errors (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                timestamp REAL NOT NULL,

                error_type TEXT NOT NULL,

                message TEXT NOT NULL,

                traceback TEXT,

                metadata TEXT,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP

            )

        """

        )

        # Таблица снапшотов конфигурации

        cursor.execute(

            """

            CREATE TABLE IF NOT EXISTS config_snapshots (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                timestamp REAL NOT NULL,

                config_json TEXT NOT NULL,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP

            )

        """

        )

        # Таблица SL/TP уровней (для отслеживания и истории)

        cursor.execute(

            """

            CREATE TABLE IF NOT EXISTS sl_tp_levels (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                position_id TEXT UNIQUE NOT NULL,  -- order_id позиции

                symbol TEXT NOT NULL,

                side TEXT NOT NULL,                -- 'Long', 'Short'

                entry_price TEXT NOT NULL,         -- Decimal as string

                entry_qty TEXT NOT NULL,

                atr TEXT,                          -- Decimal, может быть NULL

                sl_price TEXT NOT NULL,

                tp_price TEXT NOT NULL,

                sl_hit INTEGER DEFAULT 0,

                tp_hit INTEGER DEFAULT 0,

                closed_qty TEXT DEFAULT '0',

                sl_order_id TEXT,                  -- ID ордера SL на бирже

                tp_order_id TEXT,                  -- ID ордера TP на бирже

                created_at TEXT DEFAULT CURRENT_TIMESTAMP

            )

        """

        )

        self.conn.commit()

        logger.info("Database schema initialized")

    def save_signal(

        self, strategy: str, symbol: str, signal_type: str, price: float, metadata: Dict[str, Any]

    ) -> int:
        """Сохранить торговый сигнал"""

        cursor = self.conn.cursor()

        cursor.execute(

            """

            INSERT INTO signals (timestamp, strategy, symbol, signal_type, price, metadata)

            VALUES (?, ?, ?, ?, ?, ?)

        """,

            (

                datetime.now().timestamp(),

                strategy,

                symbol,

                signal_type,

                price,

                json.dumps(metadata),

            ),

        )

        self.conn.commit()

        signal_id = cursor.lastrowid

        logger.debug(f"Signal saved: {signal_type} {symbol} by {strategy}")

        return signal_id

    def save_order(self, order_data: Dict[str, Any]) -> int:
        """Сохранить ордер"""

        cursor = self.conn.cursor()

        # Проверяем, существует ли ордер

        cursor.execute("SELECT id FROM orders WHERE order_id = ?", (order_data["order_id"],))

        existing = cursor.fetchone()

        if existing:

            # Обновляем существующий

            cursor.execute(

                """

                UPDATE orders

                SET filled_qty = ?, status = ?, updated_time = ?, metadata = ?

                WHERE order_id = ?

            """,

                (

                    order_data.get("filled_qty", 0),

                    order_data["status"],

                    order_data.get("updated_time"),

                    json.dumps(order_data.get("metadata", {})),

                    order_data["order_id"],

                ),

            )

            order_id = existing[0]

        else:

            # Создаём новый

            cursor.execute(

                """

                INSERT INTO orders

                (order_id, order_link_id, symbol, side, order_type, price, qty,

                 filled_qty, status, time_in_force, created_time, updated_time, metadata)

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            """,

                (

                    order_data["order_id"],

                    order_data.get("order_link_id"),

                    order_data["symbol"],

                    order_data["side"],

                    order_data["order_type"],

                    order_data.get("price"),

                    order_data["qty"],

                    order_data.get("filled_qty", 0),

                    order_data["status"],

                    order_data.get("time_in_force"),

                    order_data.get("created_time"),

                    order_data.get("updated_time"),

                    json.dumps(order_data.get("metadata", {})),

                ),

            )

            order_id = cursor.lastrowid

        self.conn.commit()

        logger.debug(f"Order saved: {order_data['order_id']} ({order_data['status']})")

        return order_id

    def save_execution(self, exec_data: Dict[str, Any]) -> int:
        """Сохранить исполнение (trade)"""

        cursor = self.conn.cursor()

        cursor.execute(

            """

            INSERT OR IGNORE INTO executions

            (exec_id, order_id, order_link_id, symbol, side, price, qty,

             exec_fee, exec_time, is_maker, metadata)

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

        """,

            (

                exec_data["exec_id"],

                exec_data["order_id"],

                exec_data.get("order_link_id"),

                exec_data["symbol"],

                exec_data["side"],

                exec_data["price"],

                exec_data["qty"],

                exec_data.get("exec_fee"),

                exec_data["exec_time"],

                1 if exec_data.get("is_maker") else 0,

                json.dumps(exec_data.get("metadata", {})),

            ),

        )

        self.conn.commit()

        exec_id = cursor.lastrowid

        logger.debug(f"Execution saved: {exec_data['exec_id']}")

        return exec_id

    def save_position_snapshot(self, position_data: Dict[str, Any]) -> int:
        """Сохранить снапшот позиции"""

        cursor = self.conn.cursor()

        cursor.execute(

            """

            INSERT INTO positions

            (timestamp, symbol, side, size, entry_price, mark_price,

             liquidation_price, leverage, unrealised_pnl, realised_pnl, metadata)

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

        """,

            (

                datetime.now().timestamp(),

                position_data["symbol"],

                position_data["side"],

                position_data["size"],

                position_data.get("entry_price"),

                position_data.get("mark_price"),

                position_data.get("liquidation_price"),

                position_data.get("leverage"),

                position_data.get("unrealised_pnl"),

                position_data.get("realised_pnl"),

                json.dumps(position_data.get("metadata", {})),

            ),

        )

        self.conn.commit()

        pos_id = cursor.lastrowid

        logger.debug(f"Position snapshot saved: {position_data['symbol']}")

        return pos_id

    def save_error(self, error_type: str, message: str, traceback: str = "", metadata: Dict = None):
        """Сохранить ошибку"""

        cursor = self.conn.cursor()

        cursor.execute(

            """

            INSERT INTO errors (timestamp, error_type, message, traceback, metadata)

            VALUES (?, ?, ?, ?, ?)

        """,

            (

                datetime.now().timestamp(),

                error_type,

                message,

                traceback,

                json.dumps(metadata or {}),

            ),

        )

        self.conn.commit()

        logger.debug(f"Error logged: {error_type}")

    def get_active_orders(self) -> List[Dict[str, Any]]:
        """Получить активные ордера из БД"""

        cursor = self.conn.cursor()

        cursor.execute(

            """

            SELECT * FROM orders

            WHERE status IN ('New', 'PartiallyFilled')

            ORDER BY created_time DESC

        """

        )

        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def save_sl_tp_levels(self, sl_tp_data: Dict[str, Any]) -> int:
        """Сохранить SL/TP уровни позиции"""

        cursor = self.conn.cursor()

        cursor.execute(

            """

            INSERT OR REPLACE INTO sl_tp_levels 

            (position_id, symbol, side, entry_price, entry_qty, atr, 

             sl_price, tp_price, sl_hit, tp_hit, closed_qty, sl_order_id, tp_order_id)

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

        """,

            (

                sl_tp_data.get("position_id"),

                sl_tp_data.get("symbol"),

                sl_tp_data.get("side"),

                sl_tp_data.get("entry_price"),

                sl_tp_data.get("entry_qty"),

                sl_tp_data.get("atr"),

                sl_tp_data.get("sl_price"),

                sl_tp_data.get("tp_price"),

                sl_tp_data.get("sl_hit", False),

                sl_tp_data.get("tp_hit", False),

                sl_tp_data.get("closed_qty", "0"),

                sl_tp_data.get("sl_order_id"),

                sl_tp_data.get("tp_order_id"),

            ),

        )

        self.conn.commit()

        return cursor.lastrowid

    def get_sl_tp_levels(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Получить SL/TP уровни для позиции"""

        cursor = self.conn.cursor()

        cursor.execute("SELECT * FROM sl_tp_levels WHERE position_id = ?", (position_id,))

        row = cursor.fetchone()

        return dict(row) if row else None

    def update_sl_tp_triggered(

        self, position_id: str, trigger_type: str, closed_qty: str = "0"

    ) -> bool:
        """Обновить статус SL/TP триггера"""

        cursor = self.conn.cursor()

        if trigger_type == "sl":

            cursor.execute(

                "UPDATE sl_tp_levels SET sl_hit = 1, closed_qty = ? WHERE position_id = ?",

                (closed_qty, position_id),

            )

        elif trigger_type == "tp":

            cursor.execute(

                "UPDATE sl_tp_levels SET tp_hit = 1, closed_qty = ? WHERE position_id = ?",

                (closed_qty, position_id),

            )

        else:

            return False

        self.conn.commit()

        return cursor.rowcount > 0

    def get_sl_tp_history(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Получить историю SL/TP для символа"""

        cursor = self.conn.cursor()

        cursor.execute(

            """

            SELECT * FROM sl_tp_levels

            WHERE symbol = ?

            ORDER BY created_at DESC

            LIMIT ?

        """,

            (symbol, limit),

        )

        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_latest_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Получить последний снапшот позиции"""

        cursor = self.conn.cursor()

        cursor.execute(

            """

            SELECT * FROM positions

            WHERE symbol = ?

            ORDER BY timestamp DESC

            LIMIT 1

        """,

            (symbol,),

        )

        row = cursor.fetchone()

        return dict(row) if row else None

    def close(self):
        """Закрыть соединение с БД"""

        if self.conn:

            self.conn.close()

            logger.info("Database connection closed")
