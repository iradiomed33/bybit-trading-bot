"""

SQLite база данных для хранения состояния бота.


Таблицы:

- signals: Торговые сигналы от стратегий

- orders: Все ордера (локальная копия)

- executions: Исполненные сделки

- positions: Снапшоты позиций

- errors: Лог ошибок

- config_snapshots: История конфигураций

TASK-003 (P0): MultiSymbol безопасность

- WAL mode включен для конкурентного доступа

- busy_timeout = 5 сек для обработки lock'ов

- Глобальный кэш соединений по пути БД

"""


import sqlite3

import json

from datetime import datetime

from typing import Optional, Dict, Any, List

from pathlib import Path

from logger import setup_logger

import threading


logger = setup_logger(__name__)


# TASK-003: Глобальный кэш соединений и блокировка для безопасности потоков
_global_connections: Dict[str, sqlite3.Connection] = {}
_connections_lock = threading.Lock()


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

        # TASK-003: Используем кэшированное соединение для одного процесса
        self._ensure_cached_connection()
        
        self._init_db()

        logger.info(f"Database initialized: {db_path}")


    @staticmethod
    def _get_cached_connection(db_path: str) -> sqlite3.Connection:
        """
        TASK-003: Получить или создать кэшированное соединение для БД.
        
        Гарантирует что один файл БД используется через одно соединение в процессе.
        Разные файлы БД могут иметь разные соединения.
        
        Args:
            db_path: Путь к файлу БД
            
        Returns:
            sqlite3.Connection (кэшированное)
        """
        # Нормализуем путь
        normalized_path = str(Path(db_path).resolve())
        
        with _connections_lock:
            if normalized_path not in _global_connections:
                conn = sqlite3.connect(normalized_path, check_same_thread=False, timeout=5.0)
                # Включаем WAL mode (Write-Ahead Logging) для конкурентного доступа
                conn.execute("PRAGMA journal_mode=WAL")
                # Установляем timeout на занятость БД (в секундах)
                conn.execute("PRAGMA busy_timeout=5000")  # 5 секунд
                # Итоговое исполнение для убедительности
                conn.execute("PRAGMA synchronous=NORMAL")  # Балансируем между скоростью и надежностью
                
                _global_connections[normalized_path] = conn
                logger.debug(f"✓ Created cached connection for {normalized_path} (WAL + busy_timeout=5s)")
            
            return _global_connections[normalized_path]

    def _ensure_cached_connection(self):
        """TASK-003: Убедиться что используется кэшированное соединение"""
        self.conn = self._get_cached_connection(self.db_path)

    def _init_db(self):
        """Инициализация базы данных и создание таблиц"""

        # TASK-003: Используем уже кэшированное соединение (не переподключаемся)
        # self.conn уже установлено в _ensure_cached_connection()
        
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

        # Таблица для хранения ключ-значение конфигурации

        cursor.execute(

            """

            CREATE TABLE IF NOT EXISTS config (

                key TEXT PRIMARY KEY,

                value TEXT NOT NULL,

                updated_at TEXT DEFAULT CURRENT_TIMESTAMP

            )

        """

        )

        # Таблица order intents (для E2E тестов и dry-run режима)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS order_intents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,  -- 'Buy', 'Sell'
                order_type TEXT NOT NULL,  -- 'Market', 'Limit'
                qty TEXT,  -- Decimal as string
                price TEXT,  -- Decimal as string
                leverage INTEGER,
                stop_loss TEXT,  -- Decimal as string
                take_profit TEXT,  -- Decimal as string
                strategy TEXT,
                regime TEXT,  -- 'Trending', 'Ranging', 'HighVol'
                risk_percent REAL,
                atr_value REAL,
                sl_atr_mult REAL,
                tp_atr_mult REAL,
                no_trade_zone_enabled INTEGER,  -- 0/1
                mtf_score REAL,
                dry_run INTEGER DEFAULT 1,  -- 1 = dry-run, 0 = real
                metadata TEXT,  -- JSON с дополнительной информацией
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
        
        # Конвертируем metadata в JSON-совместимый формат
        def json_serialize(obj):
            """Helper для сериализации нестандартных типов"""
            if isinstance(obj, (bool, int, float, str, type(None))):
                return obj
            elif isinstance(obj, dict):
                return {k: json_serialize(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [json_serialize(item) for item in obj]
            else:
                # Преобразуем все остальное в строку
                return str(obj)
        
        safe_metadata = json_serialize(metadata)

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

                json.dumps(safe_metadata),

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

    def get_order_by_link_id(self, order_link_id: str) -> Optional[Dict[str, Any]]:
        """
        Получить ордер по orderLinkId.

        Args:
            order_link_id: Клиентский ID ордера

        Returns:
            Dict с данными ордера или None если не найден
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT order_id, order_link_id, symbol, side, order_type, price, qty,
                   filled_qty, status, time_in_force, created_time, updated_time, metadata
            FROM orders
            WHERE order_link_id = ?
            """,
            (order_link_id,)
        )
        row = cursor.fetchone()
        
        if row:
            return {
                "order_id": row[0],
                "order_link_id": row[1],
                "symbol": row[2],
                "side": row[3],
                "order_type": row[4],
                "price": row[5],
                "qty": row[6],
                "filled_qty": row[7],
                "status": row[8],
                "time_in_force": row[9],
                "created_time": row[10],
                "updated_time": row[11],
                "metadata": json.loads(row[12]) if row[12] else {},
            }
        
        return None

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

    def save_config(self, key: str, value: Any) -> None:
        """Сохранить значение конфигурации"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO config (key, value, updated_at)
            VALUES (?, ?, ?)
        """,
            (key, json.dumps(value), datetime.now().isoformat()),
        )
        self.conn.commit()
        logger.debug(f"Config saved: {key}={value}")

    def get_config(self, key: str, default: Any = None) -> Any:
        """Получить значение конфигурации"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT value FROM config WHERE key = ?
        """,
            (key,),
        )
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row[0])
            except json.JSONDecodeError:
                logger.warning(f"Failed to decode config value for {key}, returning as string")
                return row[0]
        return default

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

    def get_active_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Получить активные ордера для символа.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            List of active orders
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM orders
            WHERE symbol = ?
            AND status IN ('New', 'PartiallyFilled')
            ORDER BY created_time DESC
            """,
            (symbol,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def update_order_status(self, order_id: str, status: str) -> None:
        """
        Обновить статус ордера.
        
        Args:
            order_id: Order ID
            status: New status
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE orders
            SET status = ?, updated_time = ?
            WHERE order_id = ?
            """,
            (status, datetime.now().timestamp(), order_id),
        )
        self.conn.commit()
        logger.debug(f"Order {order_id} status updated to {status}")
    
    def order_exists(self, order_id: str) -> bool:
        """
        Проверить существование ордера в БД.
        
        Args:
            order_id: Order ID
            
        Returns:
            True if exists
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM orders WHERE order_id = ?",
            (order_id,),
        )
        return cursor.fetchone() is not None
    
    def execution_exists(self, exec_id: str) -> bool:
        """
        Проверить существование исполнения в БД.
        
        Args:
            exec_id: Execution ID
            
        Returns:
            True if exists
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id FROM executions WHERE exec_id = ?",
            (exec_id,),
        )
        return cursor.fetchone() is not None
    
    def save_execution(self, exec_data: Dict[str, Any]) -> int:
        """
        Сохранить исполнение (fill).
        
        Args:
            exec_data: Execution data from exchange
            
        Returns:
            Execution DB ID
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO executions
            (exec_id, order_id, order_link_id, symbol, side, price, qty,
             exec_fee, exec_time, is_maker, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exec_data.get("execId"),
                exec_data.get("orderId"),
                exec_data.get("orderLinkId"),
                exec_data.get("symbol"),
                exec_data.get("side"),
                float(exec_data.get("execPrice", 0)),
                float(exec_data.get("execQty", 0)),
                float(exec_data.get("execFee", 0)),
                float(exec_data.get("execTime", 0)) / 1000,  # ms to seconds
                1 if exec_data.get("isMaker") else 0,
                json.dumps(exec_data.get("metadata", {})),
            ),
        )
        self.conn.commit()
        exec_id = cursor.lastrowid
        logger.debug(f"Execution saved: {exec_data.get('execId')}")
        return exec_id

    def save_order_intent(self, intent_data: Dict[str, Any]) -> int:
        """
        Сохранить order intent (намерение разместить ордер).
        
        Используется для:
        - Dry-run режима (бот не размещает реальный ордер, но сохраняет intent)
        - E2E тестов (проверка что настройки влияют на решения бота)
        - Аудит логики (что бот хотел сделать)
        
        Args:
            intent_data: Dict with order intent details
                {
                    "symbol": str,
                    "side": str,  # "Buy" or "Sell"
                    "order_type": str,  # "Market" or "Limit"
                    "qty": str,  # Decimal as string
                    "price": str,  # Decimal as string (optional for Market)
                    "leverage": int,
                    "stop_loss": str,  # Decimal as string
                    "take_profit": str,  # Decimal as string
                    "strategy": str,
                    "regime": str,  # "Trending", "Ranging", "HighVol"
                    "risk_percent": float,
                    "atr_value": float,
                    "sl_atr_mult": float,
                    "tp_atr_mult": float,
                    "no_trade_zone_enabled": bool,
                    "mtf_score": float,
                    "dry_run": bool,
                    "metadata": dict,
                }
                
        Returns:
            Intent DB ID
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO order_intents
            (timestamp, symbol, side, order_type, qty, price, leverage,
             stop_loss, take_profit, strategy, regime, risk_percent,
             atr_value, sl_atr_mult, tp_atr_mult, no_trade_zone_enabled,
             mtf_score, dry_run, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().timestamp(),
                intent_data.get("symbol"),
                intent_data.get("side"),
                intent_data.get("order_type"),
                str(intent_data.get("qty", "")),
                str(intent_data.get("price", "")),
                intent_data.get("leverage"),
                str(intent_data.get("stop_loss", "")),
                str(intent_data.get("take_profit", "")),
                intent_data.get("strategy"),
                intent_data.get("regime"),
                intent_data.get("risk_percent"),
                intent_data.get("atr_value"),
                intent_data.get("sl_atr_mult"),
                intent_data.get("tp_atr_mult"),
                1 if intent_data.get("no_trade_zone_enabled") else 0,
                intent_data.get("mtf_score"),
                1 if intent_data.get("dry_run", True) else 0,
                json.dumps(intent_data.get("metadata", {})),
            ),
        )
        self.conn.commit()
        intent_id = cursor.lastrowid
        logger.debug(f"Order intent saved: {intent_data.get('side')} {intent_data.get('symbol')} (dry_run={intent_data.get('dry_run', True)})")
        return intent_id

    def get_last_order_intent(self, symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Получить последний order intent.
        
        Args:
            symbol: Фильтр по символу (опционально)
            
        Returns:
            Dict с данными intent или None
        """
        cursor = self.conn.cursor()
        
        if symbol:
            cursor.execute(
                """
                SELECT * FROM order_intents
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (symbol,),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM order_intents
                ORDER BY timestamp DESC
                LIMIT 1
                """
            )
        
        row = cursor.fetchone()
        if not row:
            return None
        
        # Преобразуем sqlite3.Row в dict
        intent = dict(row)
        
        # Парсим metadata JSON
        if intent.get("metadata"):
            try:
                intent["metadata"] = json.loads(intent["metadata"])
            except json.JSONDecodeError:
                intent["metadata"] = {}
        
        # Конвертируем boolean flags
        intent["no_trade_zone_enabled"] = bool(intent.get("no_trade_zone_enabled"))
        intent["dry_run"] = bool(intent.get("dry_run"))
        
        return intent

    def get_order_intents(self, limit: int = 100, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получить список order intents.
        
        Args:
            limit: Максимальное количество
            symbol: Фильтр по символу (опционально)
            
        Returns:
            Список Dict с данными intents
        """
        cursor = self.conn.cursor()
        
        if symbol:
            cursor.execute(
                """
                SELECT * FROM order_intents
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (symbol, limit),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM order_intents
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
        
        rows = cursor.fetchall()
        intents = []
        
        for row in rows:
            intent = dict(row)
            
            # Парсим metadata JSON
            if intent.get("metadata"):
                try:
                    intent["metadata"] = json.loads(intent["metadata"])
                except json.JSONDecodeError:
                    intent["metadata"] = {}
            
            # Конвертируем boolean flags
            intent["no_trade_zone_enabled"] = bool(intent.get("no_trade_zone_enabled"))
            intent["dry_run"] = bool(intent.get("dry_run"))
            
            intents.append(intent)
        
        return intents

    def close(self):
        """
        TASK-003: Закрыть данный экземпляр Database.
        
        Примечание: Кэшированное соединение остается активным для других 
        экземпляров Database с тем же db_path. Используйте close_all_cached() 
        чтобы полностью закрыть все кэшированные соединения.
        """
        logger.info(f"Database instance closed (cached connection remains active)")

    @staticmethod
    def close_all_cached():
        """
        TASK-003: Закрыть все кэшированные соединения.
        
        Используется в тестах для очистки состояния между тестами.
        """
        with _connections_lock:
            for db_path, conn in _global_connections.items():
                try:
                    conn.close()
                    logger.debug(f"✓ Closed cached connection for {db_path}")
                except Exception as e:
                    logger.warning(f"Error closing cached connection for {db_path}: {e}")
            _global_connections.clear()
            logger.info("All cached connections closed")

    @staticmethod
    def get_cached_connection_count() -> int:
        """TASK-003: Получить количество кэшированных соединений (для мониторинга)"""
        with _connections_lock:
            return len(_global_connections)
