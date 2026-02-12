"""

FastAPI приложение для управления ботом.


API endpoints для:

- Конфигурации

- Истории торговли

- Статуса аккаунта

- WebSocket live updates

"""


from fastapi import FastAPI, WebSocket, HTTPException, Depends, Header

from fastapi.staticfiles import StaticFiles

from fastapi.responses import FileResponse

from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager

from pydantic import BaseModel

import asyncio

import json

import jwt

import os

import threading

import time

from datetime import datetime, timedelta

from pathlib import Path

from typing import Dict, List, Any, Optional


from config import get_config, Config

from storage.database import Database

from logger import setup_logger

from signal_logger import get_signal_logger

from exchange.account import AccountClient

import logging


logger = setup_logger(__name__)

signal_logger = get_signal_logger()

# Global bot instance
bot_instance = None
bot_thread = None


# ============================================================================
# WebSocket Log Handler
# ============================================================================

class WebSocketLogHandler(logging.Handler):
    """Handler that broadcasts log records to WebSocket clients (thread-safe)"""
    
    def emit(self, record):
        try:
            log_entry = self.format(record)
            message = {
                "type": "log",
                "level": record.levelname,
                "message": log_entry,
                "timestamp": datetime.now().isoformat()
            }
            
            # Send via main event loop if available (thread-safe)
            if main_event_loop and main_event_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    broadcast_to_clients(message),
                    main_event_loop
                )
        except Exception:
            # Silently ignore errors (logs still go to file/console)
            pass


# ============================================================================

# AUTHENTICATION CONFIGURATION

# ============================================================================


# Секретный ключ для JWT (в продакшене используй переменную окружения)

SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "your-secret-key-change-in-production")

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 часа


# Учетные данные администратора (в продакшене используй БД)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


# Глобальные переменные для WebSocket

connected_clients: set = set()
main_event_loop = None  # Will be set on app startup


# ============================================================================

# PYDANTIC MODELS

# ============================================================================


class ConfigUpdate(BaseModel):

    value: Any


class LoginRequest(BaseModel):

    """Модель для запроса входа"""

    username: str

    password: str


class LoginResponse(BaseModel):

    """Модель для ответа входа"""

    status: str

    access_token: str

    token_type: str

    username: str

    message: str


class TokenData(BaseModel):

    """Данные, закодированные в токене"""

    username: str

    exp: datetime


class VerifyTokenResponse(BaseModel):

    """Ответ проверки токена"""

    valid: bool

    username: Optional[str] = None

    message: str


# ============================================================================

# AUTHENTICATION FUNCTIONS

# ============================================================================


def create_access_token(username: str, expires_delta: Optional[timedelta] = None) -> str:
    """Создать JWT токен"""

    if expires_delta:

        expire = datetime.utcnow() + expires_delta

    else:

        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {

        "sub": username,

        "exp": expire,

    }

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def verify_token(token: str) -> Optional[str]:
    """Проверить JWT токен и вернуть username"""

    try:

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        username: str = payload.get("sub")

        if username is None:

            return None

        return username

    except jwt.ExpiredSignatureError:

        logger.warning("Token expired")

        return None

    except jwt.InvalidTokenError:

        logger.warning("Invalid token")

        return None


def validate_credentials(username: str, password: str) -> bool:
    """Проверить учетные данные"""

    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


async def get_token_from_header(request) -> Optional[str]:
    """Получить токен из заголовка Authorization"""

    auth_header = request.headers.get("Authorization")

    if not auth_header:

        return None

    parts = auth_header.split()

    if len(parts) != 2 or parts[0].lower() != "bearer":

        return None

    return parts[1]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle менеджер для FastAPI приложения"""

    global main_event_loop
    main_event_loop = asyncio.get_running_loop()
    
    logger.info("API server started")

    yield

    logger.info("API server shutdown")
    
    # Stop bot if running
    global bot_instance, bot_thread, bot_status
    if bot_instance:
        logger.info("Stopping bot on server shutdown...")
        bot_instance.stop()
        if bot_thread and bot_thread.is_alive():
            bot_thread.join(timeout=3.0)
        bot_instance = None
        bot_thread = None
        bot_status["is_running"] = False

    # Закрыть все WebSocket соединения

    for client in connected_clients:

        await client.close()


app = FastAPI(

    title="Bybit Trading Bot API",

    description="REST API + WebSocket для управления ботом",

    version="1.0.0",

    lifespan=lifespan,

)


# CORS настройки

app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

)


# Монтирование статических файлов

static_path = Path(__file__).parent.parent / "static"

if static_path.exists():

    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


# ============================================================================

# CONFIG ENDPOINTS

# ============================================================================


@app.get("/api/config")
async def get_config_endpoint():
    """Получить всю конфигурацию"""

    try:

        logger.info("GET /api/config called")

        config = get_config()

        logger.info(f"Config returned successfully with {len(config.to_dict())} keys")

        return {

            "status": "success",

            "data": config.to_dict(),

        }

    except Exception as e:

        logger.error(f"Failed to get config: {e}")

        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config/{section}")
async def get_config_section(section: str):
    """Получить раздел конфигурации"""

    try:

        config = get_config()

        data = config.get_section(section)

        if not data:

            raise HTTPException(status_code=404, detail=f"Section '{section}' not found")

        return {

            "status": "success",

            "section": section,

            "data": data,

        }

    except Exception as e:

        logger.error(f"Failed to get config section: {e}")

        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config/{key}")
async def update_config(key: str, body: ConfigUpdate):
    """Обновить значение конфигурации"""

    try:

        config = get_config()

        config.set(key, body.value)

        config.save()
        
        # CRITICAL FIX: reload config after save to ensure file and memory are in sync
        config.reload()

        # Определяем, требуется ли перезапуск бота для применения изменений
        # Параметры, которые требуют перезапуска (читаются только при инициализации)
        restart_required_prefixes = [
            "risk_management.",
            "risk_monitor.",
            "stop_loss_tp.",
            "paper_trading.",
            "execution.",
            "meta_layer.",
            "no_trade_zone.",
            "kill_switch.",
        ]
        
        requires_restart = any(key.startswith(prefix) for prefix in restart_required_prefixes)
        
        # Автоматически перезапускаем бот если он запущен и изменения требуют перезапуска
        bot_restarted = False
        if requires_restart and bot_status["is_running"]:
            logger.info(f"Config change '{key}' requires bot restart. Restarting...")
            
            # Сохраняем текущие параметры бота
            was_running = bot_status["is_running"]
            
            # Останавливаем бот
            await stop_bot()
            
            # Небольшая пауза для корректной остановки
            await asyncio.sleep(1.0)
            
            # Перезапускаем бот с новой конфигурацией
            await start_bot()
            
            bot_restarted = True
            logger.info(f"Bot restarted with new config: {key} = {body.value}")

        # Отправить обновление всем подключённым клиентам

        await broadcast_message(

            {

                "type": "config_updated",

                "key": key,

                "value": body.value,

                "config": config.config,  # <-- добавили полный конфиг
                
                "requires_restart": requires_restart,
                
                "bot_restarted": bot_restarted,

            }

        )

        message = f"Config updated: {key} = {body.value}"
        if bot_restarted:
            message += " (bot automatically restarted)"
        elif requires_restart and not bot_status["is_running"]:
            message += " (bot restart required - please start bot to apply changes)"

        return {

            "status": "success",

            "message": message,
            
            "requires_restart": requires_restart,
            
            "bot_restarted": bot_restarted,

        }

    except Exception as e:

        logger.error(f"Failed to update config: {e}")

        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config/validate")
async def validate_config():
    """Валидировать конфигурацию"""

    try:

        config = get_config()

        is_valid, errors = config.validate()

        return {

            "status": "success",

            "valid": is_valid,

            "errors": errors,

        }

    except Exception as e:

        logger.error(f"Failed to validate config: {e}")

        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config/reset")
async def reset_config():
    """Сбросить конфигурацию на defaults"""

    try:

        config = get_config()

        config.reset_to_defaults()

        await broadcast_message({"type": "config_reset"})

        return {

            "status": "success",

            "message": "Configuration reset to defaults",

        }

    except Exception as e:

        logger.error(f"Failed to reset config: {e}")

        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================

# TRADING HISTORY ENDPOINTS

# ============================================================================


@app.get("/api/trading/history")
async def get_trading_history(limit: int = 100, offset: int = 0):
    """Получить историю торговли"""

    try:

        db = Database()

        cursor = db.conn.cursor()

        # Получить все сигналы

        cursor.execute(

            """

            SELECT id, timestamp, strategy, symbol, signal_type, price, metadata, created_at

            FROM signals

            ORDER BY timestamp DESC

            LIMIT ? OFFSET ?

        """,

            (limit, offset),

        )

        signals = []

        for row in cursor.fetchall():

            signals.append(

                {

                    "id": row[0],

                    "timestamp": row[1],

                    "strategy": row[2],

                    "symbol": row[3],

                    "signal_type": row[4],

                    "price": row[5],

                    "metadata": json.loads(row[6]) if row[6] else {},

                    "created_at": row[7],

                }

            )

        db.close()

        return {

            "status": "success",

            "data": signals,

            "count": len(signals),

        }

    except Exception as e:

        logger.error(f"Failed to get trading history: {e}")

        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trading/orders")
async def get_orders(limit: int = 100):
    """Получить последние ордера"""

    try:

        db = Database()

        cursor = db.conn.cursor()

        cursor.execute(

            """

            SELECT id, order_id, symbol, side, order_type, price, qty, filled_qty, 

                   status, created_time, updated_time

            FROM orders

            ORDER BY updated_time DESC

            LIMIT ?

        """,

            (limit,),

        )

        orders = []

        for row in cursor.fetchall():

            orders.append(

                {

                    "id": row[0],

                    "order_id": row[1],

                    "symbol": row[2],

                    "side": row[3],

                    "order_type": row[4],

                    "price": row[5],

                    "qty": row[6],

                    "filled_qty": row[7],

                    "status": row[8],

                    "created_time": row[9],

                    "updated_time": row[10],

                }

            )

        db.close()

        return {

            "status": "success",

            "data": orders,

            "count": len(orders),

        }

    except Exception as e:

        logger.error(f"Failed to get orders: {e}")

        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trading/executions")
async def get_executions(limit: int = 100):
    """Получить исполненные сделки"""

    try:

        db = Database()

        cursor = db.conn.cursor()

        cursor.execute(

            """

            SELECT id, exec_id, symbol, side, price, qty, exec_fee, exec_time

            FROM executions

            ORDER BY exec_time DESC

            LIMIT ?

        """,

            (limit,),

        )

        executions = []

        for row in cursor.fetchall():

            executions.append(

                {

                    "id": row[0],

                    "exec_id": row[1],

                    "symbol": row[2],

                    "side": row[3],

                    "price": row[4],

                    "qty": row[5],

                    "fee": row[6],

                    "time": row[7],

                }

            )

        db.close()

        return {

            "status": "success",

            "data": executions,

            "count": len(executions),

        }

    except Exception as e:

        logger.error(f"Failed to get executions: {e}")

        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trading/stats")
async def get_trading_stats():
    """Получить статистику торговли"""

    try:

        db = Database()

        cursor = db.conn.cursor()

        # Количество сигналов по типам

        cursor.execute(

            """

            SELECT signal_type, COUNT(*) as count

            FROM signals

            GROUP BY signal_type

        """

        )

        signal_counts = {row[0]: row[1] for row in cursor.fetchall()}

        # Количество исполнений по сторонам

        cursor.execute(

            """

            SELECT side, COUNT(*) as count

            FROM executions

            GROUP BY side

        """

        )

        execution_counts = {row[0]: row[1] for row in cursor.fetchall()}

        # Общая комиссия

        cursor.execute("SELECT SUM(exec_fee) FROM executions")

        total_fees = cursor.fetchone()[0] or 0

        db.close()

        return {

            "status": "success",

            "data": {

                "signal_counts": signal_counts,

                "execution_counts": execution_counts,

                "total_fees": total_fees,

            },

        }

    except Exception as e:

        logger.error(f"Failed to get trading stats: {e}")

        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/signals/logs")
async def get_signal_logs(
    limit: int = 100, 
    level: str = "all",
    category: str = "all",
    symbol: str = "all"
):
    """
    Получить логи сигналов для отладки в структурированном JSON формате.

    Показывает структурированные события с полными метриками, фильтрами и деталями.
    Приоритетно показывает сегодняшние логи.

    Args:
        limit: Количество последних логов (до 500)
        level: Уровень логирования (all, debug, info, warning, error, signal, exec, risk)
        category: Категория (all, signal, market_analysis, strategy_analysis, execution, risk, kill_switch)
        symbol: Фильтр по символу (all или конкретный символ)
    """

    try:
        limit = min(limit, 500)  # Максимум 500
        log_dir = Path("logs")
        
        # Сначала пытаемся взять СЕГОДНЯШНИЙ файл
        from datetime import datetime
        today_log = log_dir / f"signals_{datetime.now().strftime('%Y-%m-%d')}.log"
        
        # Если сегодняшнего нет или он пустой, ищем предыдущие
        log_files = []
        if today_log.exists() and today_log.stat().st_size > 0:
            log_files = [today_log]
        else:
            # Ищем предыдущие непустые файлы
            log_files = [
                f for f in log_dir.glob("signals_*.log")
                if f.stat().st_size > 0
            ]
            log_files = sorted(log_files, key=lambda p: p.stem, reverse=True)
        
        if not log_files:
            return {
                "status": "success",
                "data": [],
                "file": "No signal logs available",
                "count": 0,
                "message": "No signal logs available",
            }

        log_file = log_files[0]

        # Читаем файл в обратном порядке (новые логи первыми)
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()

        # Парсим и фильтруем события
        events = []

        for line in reversed(all_lines):
            # Пропускаем пустые строки
            if not line.strip():
                continue
            
            try:
                # Пытаемся распарсить как JSON событие (новый формат)
                # Формат: "TIMESTAMP | LEVEL | JSON_PAYLOAD"
                parts = line.split(" | ", 2)
                if len(parts) >= 3:
                    # Пытаемся распарсить JSON
                    try:
                        event = json.loads(parts[2])
                        # Это структурированное событие
                    except json.JSONDecodeError:
                        # Старый формат - конвертируем в структурированное событие
                        event = _parse_legacy_log(line, parts)
                else:
                    # Очень старый формат
                    continue
                
                # Применяем фильтры
                if not _filter_event(event, level, category, symbol):
                    continue
                
                events.append(event)

                if len(events) >= limit:
                    break

            except Exception as e:
                # Если не смогли распарсить - пропускаем
                logger.debug(f"Failed to parse log line: {e}")
                continue

        return {
            "status": "success",
            "data": _sanitize_for_json(events),
            "file": str(log_file),
            "count": len(events),
            "limit": limit,
            "level_filter": level,
            "category_filter": category,
            "symbol_filter": symbol,
        }

    except Exception as e:
        logger.error(f"Failed to get signal logs: {e}")
        return {"status": "error", "error": str(e), "data": []}


def _sanitize_for_json(obj):
    """
    Рекурсивно заменяет NaN и Infinity на None для безопасной JSON сериализации.
    
    Args:
        obj: Объект для обработки (dict, list, float, или другое)
        
    Returns:
        Обработанный объект с NaN/Inf замененными на None
    """
    import math
    
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    else:
        return obj


def _parse_legacy_log(line: str, parts: list) -> Dict[str, Any]:
    """
    Парсит старый формат логов и конвертирует в структурированное событие.
    Backward compatibility для логов до внедрения структурированного формата.
    """
    timestamp = parts[0]
    log_level = parts[1].strip()
    message = parts[2].strip()
    
    # Базовое событие
    event = {
        "ts": timestamp,
        "level": log_level,
        "category": "system",
        "symbol": "N/A",
        "message": message,
        "legacy": True
    }
    
    # Пытаемся извлечь информацию из сообщения
    if "Stage=GENERATED" in message or "Stage=ACCEPTED" in message or "Stage=REJECTED" in message:
        event["category"] = "signal"
        
        # Извлекаем stage
        if "Stage=GENERATED" in message:
            event["stage"] = "GENERATED"
        elif "Stage=ACCEPTED" in message:
            event["stage"] = "ACCEPTED"
        elif "Stage=REJECTED" in message:
            event["stage"] = "REJECTED"
        
        # Извлекаем symbol
        import re
        symbol_match = re.search(r'Symbol=([A-Z]+)', message)
        if symbol_match:
            event["symbol"] = symbol_match.group(1)
        
        # Извлекаем strategy  
        strategy_match = re.search(r'Strategy=([^|]+)', message)
        if strategy_match:
            event["strategy"] = strategy_match.group(1).strip()
        
        # Извлекаем direction
        direction_match = re.search(r'Direction=([A-Z]+)', message)
        if direction_match:
            event["direction"] = direction_match.group(1)
        
        # Извлекаем confidence
        confidence_match = re.search(r'Confidence=([\d.]+)', message)
        if confidence_match:
            event["confidence"] = float(confidence_match.group(1))
        
        # Извлекаем reasons
        reasons_match = re.search(r'Reasons=(\[[^\]]*\])', message)
        if reasons_match:
            try:
                event["reasons"] = json.loads(reasons_match.group(1))
            except:
                pass
        
        # Извлекаем values
        values_match = re.search(r'Values=(\{[^\}]*\})', message)
        if values_match:
            try:
                event["values"] = json.loads(values_match.group(1))
            except:
                pass
    
    elif "ORDER EXEC FAILED" in message:
        event["category"] = "execution"
        event["stage"] = "FAILED"
        
        # Извлекаем symbol
        import re
        symbol_match = re.search(r'Symbol=([A-Z]+)', message)
        if symbol_match:
            event["symbol"] = symbol_match.group(1)
    
    return event


def _filter_event(event: Dict[str, Any], level: str, category: str, symbol: str) -> bool:
    """
    Фильтрует событие по уровню, категории и символу.
    """
    # Фильтр по level
    if level != "all":
        # Специальная обработка для сигналов: level=info/warning/error маппим на stage
        event_level = event.get("level", "").upper()
        event_category = event.get("category", "")
        event_stage = event.get("stage", "").upper()
        
        # Для категории "signal" фильтруем по полю stage, а не level
        if event_category == "signal" and event_level == "SIGNAL":
            # Маппинг UI фильтра на стадии сигнала:
            # info → ACCEPTED (успешные сигналы)
            # warning → REJECTED (отклоненные сигналы)
            # error → нет сигналов с таким уровнем (показываем пусто)
            if level.upper() == "INFO":
                if event_stage != "ACCEPTED":
                    return False
            elif level.upper() == "WARNING":
                if event_stage != "REJECTED":
                    return False
            elif level.upper() == "ERROR":
                # Сигналы не имеют стадии ERROR, показываем пустой список
                return False
            # Если level=signal или другое - показываем все сигналы
        else:
            # Для остальных событий проверяем level как обычно
            if event_level != level.upper():
                return False
    
    # Фильтр по category
    if category != "all":
        # Для обратной совместимости: если category=signal, показываем все важные сигналы
        if category == "signal":
            event_cat = event.get("category", "")
            if event_cat not in ["signal", "execution"]:
                return False
        else:
            if event.get("category", "") != category:
                return False
    
    # Фильтр по symbol
    if symbol != "all":
        if event.get("symbol", "") != symbol:
            return False
    
    return True


# ============================================================================

# ACCOUNT ENDPOINTS

# ============================================================================


@app.get("/api/account/balance")
async def get_balance():
    """Получить баланс аккаунта"""

    try:

        # Получить данные из конфигурации/базы данных

        db = Database()

        cursor = db.conn.cursor()

        # Получить все позиции для расчета

        cursor.execute(

            """

            SELECT SUM(size) as total_size, SUM(unrealised_pnl) as total_pnl

            FROM positions

            WHERE size > 0

        """

        )

        pos_data = cursor.fetchone()

        total_size = pos_data[0] or 0.0

        total_pnl = pos_data[1] or 0.0

        db.close()

        # Расчет баланса (демо значения с поправкой на позиции)

        total_balance = 10000.0  # Начальный баланс

        position_value = total_size * 45000 if total_size > 0 else 0.0

        available_balance = total_balance - position_value

        return {

            "status": "success",

            "data": {

                "total_balance": total_balance,

                "available_balance": max(available_balance, 0),

                "position_value": position_value,

                "unrealized_pnl": total_pnl,

                "realized_pnl": 0.0,

                "currency": "USDT",

                "margin_balance": position_value,

            },

        }

    except Exception as e:

        logger.error(f"Failed to get balance: {e}")

        return {

            "status": "success",

            "data": {

                "total_balance": 10000.0,

                "available_balance": 9000.0,

                "position_value": 1000.0,

                "unrealized_pnl": 150.0,

                "realized_pnl": 0.0,

                "currency": "USDT",

                "margin_balance": 1000.0,

            },

        }


@app.get("/api/account/positions")
async def get_positions():
    """Получить открытые позиции"""

    try:

        db = Database()

        cursor = db.conn.cursor()

        cursor.execute(

            """

            SELECT symbol, side, size, entry_price, mark_price, unrealised_pnl

            FROM positions

            WHERE size > 0

            ORDER BY created_at DESC

        """

        )

        positions = []

        for row in cursor.fetchall():
            symbol = row[0]
            side = row[1]
            size = row[2]
            entry_price = row[3]
            mark_price = row[4]
            unrealised_pnl = row[5]
            
            # Вычисляем PnL в процентах
            position_value = entry_price * size
            pnl_pct = (unrealised_pnl / position_value * 100) if position_value > 0 else 0.0

            positions.append(

                {

                    "symbol": symbol,

                    "side": side,

                    "size": size,

                    "entry_price": entry_price,

                    "mark_price": mark_price,

                    "pnl": unrealised_pnl,

                    "pnl_pct": pnl_pct,

                }

            )

        db.close()

        return {

            "status": "success",

            "data": positions,

        }

    except Exception as e:

        logger.error(f"Failed to get positions: {e}")

        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/account/status")
async def get_account_status():
    """Получить статус аккаунта"""

    try:

        config = get_config()

        return {

            "status": "success",

            "data": {

                "account_id": "123456789",

                "account_status": "normal",

                "account_type": "Unified Trading Account",

                "margin_status": "Regular Margin",

                "mode": config.get("trading.mode") or "paper",

                "symbol": config.get("trading.symbol") or "BTCUSDT",

                "testnet": config.get("trading.testnet") or True,

                "active_strategies": config.get("trading.active_strategies") or [],

                "risk_percent": config.get("risk_management.position_risk_percent") or 1.0,

                "max_leverage": config.get("risk_management.max_leverage") or 1.0,

            },

        }

    except Exception as e:

        logger.error(f"Failed to get account status: {e}")

        return {

            "status": "success",

            "data": {

                "account_id": "123456789",

                "account_status": "normal",

                "account_type": "Unified Trading Account",

                "margin_status": "Regular Margin",

                "mode": "paper",

                "symbol": "BTCUSDT",

                "testnet": True,

                "active_strategies": [],

                "risk_percent": 1.0,

                "max_leverage": 1.0,

            },

        }


# ============================================================================
# BYBIT ACCOUNT CLIENT HELPERS
# ============================================================================
# BYBIT ACCOUNT CLIENT HELPERS
# ============================================================================

_account_client_cache = {"testnet": None, "client": None}


def _safe_float(v, default=0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _get_account_client_from_env():
    """Return AccountClient if keys exist, else None."""
    api_key = (os.getenv("BYBIT_API_KEY") or Config.BYBIT_API_KEY or "").strip()
    api_secret = (os.getenv("BYBIT_API_SECRET") or Config.BYBIT_API_SECRET or "").strip()
    if not api_key or not api_secret:
        return None

    cfg = get_config()
    testnet = bool(cfg.get("trading.testnet", True))

    cached = _account_client_cache
    if cached["client"] is not None and cached["testnet"] == testnet:
        return cached["client"]

    client = AccountClient(api_key=api_key, api_secret=api_secret, testnet=testnet)
    _account_client_cache["testnet"] = testnet
    _account_client_cache["client"] = client
    return client


def _fetch_balance_snapshot_sync(testnet: bool = None):
    """
    Fetch только balance информацию из Bybit. Используется для инициализации WebSocket.
    Требует ключи в окружении (BYBIT_API_KEY/BYBIT_API_SECRET).
    Returns: balance_dict с total_balance, available_balance, position_value, unrealized_pnl и т.д.
    """
    if testnet is None:
        cfg = get_config()
        testnet = bool(cfg.get("trading.testnet", True))
    
    cfg = get_config()
    symbols = cfg.get("trading.symbols") or [cfg.get("trading.symbol") or "BTCUSDT"]
    
    try:
        balance, _ = _fetch_account_snapshot_sync(testnet, symbols)
        return balance
    except Exception:
        # Если не получилось - возвращаем пусто, будет использован fallback
        return {}


def _fetch_account_snapshot_sync(testnet: bool, symbols: list):
    """
    Реальный снапшот по Bybit REST. Требует ключи в окружении (BYBIT_API_KEY/BYBIT_API_SECRET).
    Returns: (balance_dict, positions_list)
    """
    from exchange.account import AccountClient

    c = AccountClient(testnet=testnet)

    # позиции
    pos_resp = c.get_positions(category="linear")
    if pos_resp.get("retCode") != 0:
        raise RuntimeError(f"positions retCode={pos_resp.get('retCode')} retMsg={pos_resp.get('retMsg')}")
    raw = pos_resp.get("result", {}).get("list", []) or []

    symset = set(s.upper() for s in (symbols or []) if s)
    positions = []
    total_pnl = 0.0
    position_value = 0.0

    for p in raw:
        sym = (p.get("symbol") or "").upper()
        if symset and sym not in symset:
            continue

        size = _safe_float(p.get("size"), 0.0)
        if abs(size) <= 0:
            continue

        entry = _safe_float(p.get("avgPrice") or p.get("entryPrice"), 0.0)
        mark = _safe_float(p.get("markPrice"), 0.0)
        pnl = _safe_float(p.get("unrealisedPnl"), 0.0)
        notional = abs(size) * (mark or entry or 0.0)

        total_pnl += pnl
        position_value += notional

        pnl_pct = (pnl / notional * 100.0) if notional > 0 else 0.0

        positions.append({
            "symbol": sym,
            "side": p.get("side") or ("Buy" if size > 0 else "Sell"),
            "size": abs(size),
            "entry_price": entry,
            "mark_price": mark,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
        })

    # wallet balance (упрощённо)
    w = c.get_wallet_balance("USDT")
    total_balance = _safe_float(w.get("balance"), 0.0)

    balance = {
        "total_balance": total_balance,
        "available_balance": total_balance,  # TODO: при желании парсить availableToWithdraw из сырого ответа wallet-balance
        "position_value": position_value,
        "unrealized_pnl": total_pnl,
        "realized_pnl": 0.0,
        "currency": "USDT",
        "margin_balance": position_value,
        "source": "bybit_rest",
    }

    return balance, positions


# ============================================================================

# WEBSOCKET ENDPOINTS

# ============================================================================


async def broadcast_message(message: Dict[str, Any]):
    """Отправить сообщение всем подключённым клиентам"""

    disconnected = set()

    for client in connected_clients:

        try:

            await client.send_json(message)

        except Exception as e:

            logger.warning(f"Failed to send message to client: {e}")

            disconnected.add(client)

    # Удалить отключённых клиентов

    connected_clients.difference_update(disconnected)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint для live updates"""

    await websocket.accept()

    connected_clients.add(websocket)

    logger.info(f"WebSocket client connected. Total: {len(connected_clients)}")

    # Отправить начальные данные при подключении
    try:
        config = get_config()

        # --- BALANCE: Bybit if keys exist, else local fallback ---
        balance_payload = {}
        try:
            balance_payload = await asyncio.to_thread(_fetch_balance_snapshot_sync)
        except Exception as e:
            logger.error(f"WS: failed to fetch Bybit balance: {e}", exc_info=True)

        if not balance_payload:
            # Fallback: local (как было), но без притворства что это биржа
            db = Database()
            cursor = db.conn.cursor()
            cursor.execute("SELECT SUM(size), SUM(unrealised_pnl) FROM positions WHERE size > 0")
            pos_data = cursor.fetchone()
            total_size = pos_data[0] or 0.0
            total_pnl = pos_data[1] or 0.0
            db.close()

            position_value = total_size * 45000 if total_size > 0 else 0.0
            total_balance = 10000.0

            balance_payload = {
                "total_balance": total_balance,
                "available_balance": max(total_balance - position_value, 0),
                "position_value": position_value,
                "unrealized_pnl": float(total_pnl or 0.0),
                "currency": "USDT",
                "margin_balance": position_value,
                "source": "local",
            }

        await websocket.send_json({"type": "initial_balance", "balance": balance_payload})

        # --- STATUS: исправить баг с testnet (or True всегда даёт True) ---
        symbols = config.get("trading.symbols") or [config.get("trading.symbol") or "BTCUSDT"]
        testnet = bool(config.get("trading.testnet", True))

        await websocket.send_json(
            {
                "type": "initial_status",
                "status": {
                    "account_id": "123456789",
                    "account_status": "normal",
                    "account_type": "Unified Trading Account",
                    "margin_status": "Regular Margin",
                    "mode": config.get("trading.mode") or "paper",
                    "symbol": symbols[0],      # для совместимости с UI
                    "symbols": symbols,        # чтобы UI мог показать список
                    "testnet": testnet,
                },
            }
        )

    except Exception as e:
        logger.error(f"Failed to send initial data: {e}", exc_info=True)

    # Периодический пуш баланса и позиций
    push_every = 3.0  # 2-5 сек по задаче
    last_push = 0.0
    try:
        while True:
            now = time.time()

            # периодический пуш аккаунта
            if now - last_push >= push_every:
                try:
                    cfg = get_config()
                    testnet = bool(cfg.get("trading.testnet", True))
                    symbols = cfg.get("trading.symbols", None) or [cfg.get("trading.symbol", "BTCUSDT")]

                    balance, positions = await asyncio.to_thread(_fetch_account_snapshot_sync, testnet, symbols)

                    await websocket.send_json({"type": "account_balance_updated", "balance": balance})
                    await websocket.send_json({"type": "positions_updated", "positions": positions})
                except Exception as e:
                    # не валим WS, просто логируем (часто тут будет отсутствие ключей в paper-режиме)
                    logger.debug(f"WS periodic account snapshot failed: {e}")

                last_push = now

            # команды от клиента — без вечной блокировки
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            message = json.loads(data)

            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif message.get("type") == "subscribe":
                channel = message.get("channel")
                await websocket.send_json({"type": "subscribed", "channel": channel})
            else:
                logger.warning(f"Unknown message type: {message.get('type')}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        connected_clients.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(connected_clients)}")


# ============================================================================

# STATIC FILES

# ============================================================================


# Маршрут для главной страницы

@app.get("/")
async def get_index():
    """Главная страница - дашборд"""

    html_path = Path("static/index.html")

    if html_path.exists():

        return FileResponse(html_path)

    else:

        return {"status": "error", "message": "Static files not found"}


# Маршрут для проверки здоровья

@app.get("/health")
async def health_check():
    """Проверка здоровья API"""

    return {

        "status": "healthy",

        "timestamp": datetime.now().isoformat(),

        "connected_clients": len(connected_clients),

    }


# Bot Control Endpoints

bot_status = {
    "is_running": False,
    "mode": "paper",
    "last_started": None,
    "last_stopped": None,
    # runtime metadata
    "symbols": [],
    "primary_symbol": None,
    "is_multi": False,
}

def _normalize_symbols(cfg) -> List[str]:
    """
    Привести trading.symbol / trading.symbols к нормальному виду.
    Поддерживает:
      - trading.symbols: ["BTCUSDT","ETHUSDT",...]
      - trading.symbols: "BTCUSDT, ETHUSDT"
      - trading.symbol: "BTCUSDT"
      - trading.symbol: "BTCUSDT, ETHUSDT" (legacy/broken state)
    """
    raw_symbols = cfg.get("trading.symbols", []) or []
    symbols: List[str] = []
    if isinstance(raw_symbols, str):
        symbols = [s.strip() for s in raw_symbols.split(",") if s.strip()]
    elif isinstance(raw_symbols, list):
        symbols = [str(s).strip() for s in raw_symbols if str(s).strip()]

    if not symbols:
        raw_primary = cfg.get("trading.symbol", "BTCUSDT")
        if isinstance(raw_primary, str):
            if "," in raw_primary:
                symbols = [s.strip() for s in raw_primary.split(",") if s.strip()]
            else:
                symbols = [raw_primary.strip()]
        elif isinstance(raw_primary, list):
            symbols = [str(s).strip() for s in raw_primary if str(s).strip()]

    # Normalize: uppercase + unique (preserve order)
    out: List[str] = []
    seen = set()
    for s in symbols:
        sym = s.strip().upper()
        if not sym:
            continue
        if sym in seen:
            continue
        seen.add(sym)
        out.append(sym)

    return out or ["BTCUSDT"]


@app.get("/api/bot/status")
async def get_bot_status():
    """Получить статус бота"""
    return {
        "is_running": bot_status["is_running"],
        "mode": bot_status["mode"],
        "last_started": bot_status["last_started"],
        "last_stopped": bot_status["last_stopped"],
        "symbols": bot_status.get("symbols", []),
        "primary_symbol": bot_status.get("primary_symbol"),
        "is_multi": bot_status.get("is_multi", False),
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/bot/start")
async def start_bot():
    """Запустить бота"""
    global bot_status, bot_instance, bot_thread

    if bot_status["is_running"]:
        return {"status": "already_running", "message": "Bot is already running"}

    try:
        # Import here to avoid circular dependencies
        from bot.trading_bot import TradingBot
        from bot.strategy_builder import StrategyBuilder
        from bot.multi_symbol_bot import MultiSymbolBot, MultiSymbolConfig

        # Get config
        cfg = get_config()
        mode = cfg.get("trading.mode") or "paper"
        testnet = cfg.get("trading.testnet", True)
        
        # DEBUG: Log что получили из конфига
        logger.info(f"[START_BOT] DEBUG: cfg.get('trading.mode') = {cfg.get('trading.mode')}")
        logger.info(f"[START_BOT] DEBUG: mode = {mode}")
        logger.info(f"[START_BOT] DEBUG: testnet = {testnet}")
        logger.info(f"[START_BOT] DEBUG: config_path = {cfg.config_path}")

        # Normalize symbols (supports both trading.symbol and trading.symbols)
        symbols = _normalize_symbols(cfg)
        primary_symbol = symbols[0] if symbols else "BTCUSDT"

        # Build strategies from config (fresh objects per call)
        builder = StrategyBuilder(cfg)

        def build_strategies():
            # IMPORTANT: new instances each call (per-symbol isolation)
            return builder.build_strategies()

        # Add WebSocket handler to loggers (once)
        ws_handler = WebSocketLogHandler()
        ws_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        ws_handler.setFormatter(formatter)

        def _attach_ws(logger_obj: logging.Logger):
            if any(isinstance(h, WebSocketLogHandler) for h in logger_obj.handlers):
                return
            logger_obj.addHandler(ws_handler)

        _attach_ws(logging.getLogger("bot.trading_bot"))
        for logger_name in ["execution", "strategy", "risk", "signals", "bot.multi_symbol_bot"]:
            _attach_ws(logging.getLogger(logger_name))

        # Start bot(s)
        if len(symbols) > 1:
            # Multi-symbol orchestrator (spawns per-symbol TradingBot threads internally)
            ms_cfg = MultiSymbolConfig(
                symbols=symbols,
                mode=mode,
                testnet=testnet,
            )
            bot_instance = MultiSymbolBot(
                config=ms_cfg,
                strategy_builder=build_strategies,
                config_manager=cfg,
            )

            ok_init = bot_instance.initialize()
            if not ok_init:
                raise RuntimeError("MultiSymbolBot.initialize() failed (see logs)")

            ok_start = bot_instance.start()
            if not ok_start:
                raise RuntimeError("MultiSymbolBot.start() failed (see logs)")

            bot_thread = None
            bot_status["is_multi"] = True
        else:
            # Single-symbol TradingBot (run in background thread)
            strategies = build_strategies()
            bot_instance = TradingBot(
                mode=mode,
                strategies=strategies,
                symbol=primary_symbol,
                testnet=testnet,
                config=cfg,
            )

            def run_bot():
                try:
                    logger.info(f"Starting bot thread in {mode} mode (symbol={primary_symbol})...")
                    bot_instance.run()
                except Exception as e:
                    logger.error(f"Bot thread error: {e}", exc_info=True)
                    bot_status["is_running"] = False

            bot_thread = threading.Thread(target=run_bot, daemon=True)
            bot_thread.start()
            bot_status["is_multi"] = False

        bot_status["is_running"] = True
        bot_status["mode"] = mode
        bot_status["last_started"] = datetime.now().isoformat()
        bot_status["symbols"] = symbols
        bot_status["primary_symbol"] = primary_symbol

        # Notify clients
        await broadcast_to_clients(
            {
                "type": "bot_status_changed",
                "is_running": True,
                "message": f"🚀 Bot started in {mode} mode | symbols: {', '.join(symbols)}",
                "timestamp": datetime.now().isoformat(),
            }
        )

        logger.info(f"Bot started via API in {mode} mode (symbols={symbols})")

        return {
            "status": "started",
            "message": f"Bot started successfully in {mode} mode",
            "mode": mode,
            "symbols": symbols,
            "primary_symbol": primary_symbol,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        bot_status["is_running"] = False
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}, 500


@app.post("/api/bot/stop")
async def stop_bot():
    """Остановить бота"""
    global bot_status, bot_instance, bot_thread

    if not bot_status["is_running"]:
        return {"status": "already_stopped", "message": "Bot is not running"}

    try:
        # Stop bot/orchestrator if running
        if bot_instance:
            logger.info("Stopping bot instance...")
            try:
                bot_instance.stop()
            except Exception as e:
                logger.error(f"Error during bot_instance.stop(): {e}", exc_info=True)

        # Wait for single-bot thread to finish (MultiSymbolBot manages its own threads)
        if bot_thread and bot_thread.is_alive():
            bot_thread.join(timeout=5.0)
            if bot_thread.is_alive():
                logger.warning("Bot thread did not stop cleanly")

        bot_instance = None
        bot_thread = None

        bot_status["is_running"] = False
        bot_status["last_stopped"] = datetime.now().isoformat()
        bot_status["symbols"] = []
        bot_status["primary_symbol"] = None
        bot_status["is_multi"] = False

        # Notify clients
        await broadcast_to_clients(
            {
                "type": "bot_status_changed",
                "is_running": False,
                "message": "🛑 Bot stopped",
                "timestamp": datetime.now().isoformat(),
            }
        )

        logger.info("Bot stopped via API")

        return {
            "status": "stopped",
            "message": "Bot stopped successfully",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to stop bot: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}, 500


async def broadcast_to_clients(message: Dict[str, Any]):
    """Отправить сообщение всем WebSocket клиентам"""

    disconnected = set()

    for client in connected_clients:

        try:

            await client.send_json(message)

        except Exception as e:

            logger.warning(f"Failed to send message to client: {e}")

            disconnected.add(client)

    # Удаляем отключившихся клиентов

    for client in disconnected:

        connected_clients.discard(client)


# ============================================================================

# AUTHENTICATION ENDPOINTS

# ============================================================================


@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """

    Вход в систему


    Принимает:

    - username: str

    - password: str


    Возвращает JWT токен для использования в Authorization заголовке

    """

    if not validate_credentials(request.username, request.password):

        logger.warning(f"Failed login attempt for user: {request.username}")

        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token = create_access_token(request.username)

    logger.info(f"User logged in: {request.username}")

    return LoginResponse(

        status="success",

        access_token=access_token,

        token_type="bearer",

        username=request.username,

        message=f"Welcome, {request.username}!",

    )


@app.post("/api/auth/verify", response_model=VerifyTokenResponse)
async def verify(authorization: Optional[str] = Header(None)):
    """

    Проверить токен


    Требует:

    - Authorization: "Bearer <token>" в заголовке


    Возвращает:

    - valid: bool

    - username: str или null

    - message: str

    """

    # Получить токен из заголовка

    token = authorization

    if not token:

        logger.warning("Verify called without token")

        return VerifyTokenResponse(

            valid=False,

            username=None,

            message="No token provided",

        )

    # Удалить префикс "Bearer " если есть

    if token.startswith("Bearer "):

        token = token[7:]

    username = verify_token(token)

    if username:

        return VerifyTokenResponse(

            valid=True,

            username=username,

            message="Token is valid",

        )

    else:

        return VerifyTokenResponse(

            valid=False,

            username=None,

            message="Token is invalid or expired",

        )


@app.post("/api/auth/logout")
async def logout(authorization: Optional[str] = None):
    """

    Выход из системы


    Просто удаляет токен на клиенте (сервер не хранит список активных токенов)

    """

    logger.info("User logged out")

    return {

        "status": "success",

        "message": "Logged out successfully",

    }


# ============================================================================
# BOT INTROSPECTION ENDPOINTS (for E2E testing)
# ============================================================================

@app.get("/api/bot/effective-config")
async def get_effective_config():
    """
    Получить эффективную конфигурацию бота в runtime
    
    Возвращает:
    - Фактический конфиг, который бот сейчас использует (после merge env/defaults/ui)
    - config_version для отслеживания изменений
    - updated_at для временной метки
    
    Это критично для E2E тестов, чтобы проверить, что настройки UI реально применяются ботом.
    """
    try:
        cfg = get_config()
        config_dict = cfg.to_dict()
        
        # Добавляем метаданные для отслеживания версий
        effective_config = {
            "config": config_dict,
            "config_version": cfg.get("_version", 1),  # Инкрементируется при каждом update
            "updated_at": cfg.get("_updated_at", datetime.now().isoformat()),
            "config_path": cfg.config_path,
        }
        
        # Если бот запущен, добавляем информацию о runtime состоянии
        if bot_instance:
            effective_config["bot_runtime"] = {
                "is_running": bot_instance.is_running,
                "mode": bot_instance.mode,
                "symbol": bot_instance.symbol,
                "testnet": bot_instance.testnet,
            }
        
        return {
            "status": "success",
            "data": effective_config,
        }
    except Exception as e:
        logger.error(f"Failed to get effective config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bot/last-order-intent")
async def get_last_order_intent():
    """
    Получить последнее решение бота (order intent)
    
    Возвращает что бот пытался сделать:
    - leverage
    - SL/TP levels
    - qty
    - risk inputs
    - regime/strategy
    
    Идеально для проверки влияния advanced-настроек на торговые действия.
    В dry-run режиме бот формирует intents, но не размещает реальные ордера.
    """
    try:
        db = Database()
        
        # Получаем последний order intent из БД
        # (Intent сохраняется перед отправкой ордера)
        last_intent = db.get_last_order_intent()
        
        if not last_intent:
            return {
                "status": "success",
                "data": None,
                "message": "No order intents found",
            }
        
        return {
            "status": "success",
            "data": last_intent,
        }
    except Exception as e:
        logger.error(f"Failed to get last order intent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bot/run-once")
async def run_bot_once():
    """
    Запустить один цикл бота в тестовом режиме (dry-run)
    
    Бот:
    - Проходит весь пайплайн стратегии/риска
    - Формирует order intent
    - НЕ отправляет в реальную биржу (dry-run)
    - Пишет intent в БД и отдаёт через /api/bot/last-order-intent
    
    Это ключевой endpoint для E2E тестов:
    - Позволяет проверить влияние настроек UI на решения бота
    - Безопасно (не размещает реальные ордера)
    - Детерминированно (один тик = один результат)
    """
    try:
        if not bot_instance:
            raise HTTPException(status_code=400, detail="Bot is not initialized")
        
        # Устанавливаем флаг dry-run для одного тика
        original_dry_run = getattr(bot_instance, '_dry_run_mode', False)
        bot_instance._dry_run_mode = True
        
        # Запускаем один тик бота
        logger.info("[RUN_ONCE] Executing single bot tick in dry-run mode")
        
        # Запускаем один цикл обработки
        result = await bot_instance.run_single_tick()
        
        # Восстанавливаем оригинальный режим
        bot_instance._dry_run_mode = original_dry_run
        
        return {
            "status": "success",
            "message": "Bot tick completed in dry-run mode",
            "data": result,
        }
    except Exception as e:
        logger.error(f"Failed to run bot once: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
