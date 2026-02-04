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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

from config import get_config
from storage.database import Database
from logger import setup_logger
from signal_logger import get_signal_logger

logger = setup_logger(__name__)
signal_logger = get_signal_logger()

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
    logger.info("API server started")
    yield
    logger.info("API server shutdown")
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
        
        # Отправить обновление всем подключённым клиентам
        await broadcast_message({
            "type": "config_updated",
            "key": key,
            "value": body.value,
        })
        
        return {
            "status": "success",
            "message": f"Config updated: {key} = {body.value}",
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
            signals.append({
                "id": row[0],
                "timestamp": row[1],
                "strategy": row[2],
                "symbol": row[3],
                "signal_type": row[4],
                "price": row[5],
                "metadata": json.loads(row[6]) if row[6] else {},
                "created_at": row[7],
            })
        
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
            orders.append({
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
            })
        
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
            executions.append({
                "id": row[0],
                "exec_id": row[1],
                "symbol": row[2],
                "side": row[3],
                "price": row[4],
                "qty": row[5],
                "fee": row[6],
                "time": row[7],
            })
        
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
async def get_signal_logs(limit: int = 100, level: str = "all"):
    """
    Получить логи сигналов для отладки.
    
    Args:
        limit: Количество последних логов (до 500)
        level: Уровень логирования (all, info, warning, error)
    """
    try:
        limit = min(limit, 500)  # Максимум 500
        
        log_file = Path("logs") / f"signals_{datetime.now().strftime('%Y-%m-%d')}.log"
        
        if not log_file.exists():
            return {
                "status": "success",
                "data": [],
                "file": str(log_file),
                "count": 0,
                "message": "No signal logs yet"
            }
        
        # Читаем файл в обратном порядке (новые логи первыми)
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        # Фильтруем по уровню если нужно
        filtered_lines = []
        for line in reversed(all_lines):
            if level == "all":
                filtered_lines.append(line.strip())
            elif level.upper() in line:
                filtered_lines.append(line.strip())
            
            if len(filtered_lines) >= limit:
                break
        
        # Парсим логи в более удобный формат
        logs = []
        for line in filtered_lines:
            try:
                parts = line.split(" | ")
                if len(parts) >= 3:
                    timestamp = parts[0]
                    log_level = parts[1].strip()
                    message = " | ".join(parts[2:])
                    
                    logs.append({
                        "timestamp": timestamp,
                        "level": log_level,
                        "message": message,
                        "raw": line
                    })
            except:
                logs.append({"raw": line})
        
        return {
            "status": "success",
            "data": logs,
            "file": str(log_file),
            "count": len(logs),
            "limit": limit,
            "level_filter": level
        }
    except Exception as e:
        logger.error(f"Failed to get signal logs: {e}")
        return {
            "status": "error",
            "error": str(e),
            "data": []
        }


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
            positions.append({
                "symbol": row[0],
                "side": row[1],
                "size": row[2],
                "entry_price": row[3],
                "current_price": row[4],
                "pnl": row[5],
            })
        
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
    
    try:
        # Отправить начальные данные при подключении
        try:
            config = get_config()
            db = Database()
            cursor = db.conn.cursor()
            
            # Получить позиции
            cursor.execute("SELECT SUM(size), SUM(unrealised_pnl) FROM positions WHERE size > 0")
            pos_data = cursor.fetchone()
            total_size = pos_data[0] or 0.0
            total_pnl = pos_data[1] or 0.0
            
            db.close()
            
            # Отправить начальный баланс
            position_value = total_size * 45000 if total_size > 0 else 0.0
            total_balance = 10000.0
            await websocket.send_json({
                "type": "initial_balance",
                "balance": {
                    "total_balance": total_balance,
                    "available_balance": max(total_balance - position_value, 0),
                    "position_value": position_value,
                    "unrealized_pnl": total_pnl,
                    "currency": "USDT",
                    "margin_balance": position_value,
                },
            })
            
            # Отправить начальный статус
            await websocket.send_json({
                "type": "initial_status",
                "status": {
                    "account_id": "123456789",
                    "account_status": "normal",
                    "account_type": "Unified Trading Account",
                    "margin_status": "Regular Margin",
                    "mode": config.get("trading.mode") or "paper",
                    "symbol": config.get("trading.symbol") or "BTCUSDT",
                },
            })
        except Exception as e:
            logger.error(f"Failed to send initial data: {e}")
        
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Обработка команд от клиента
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif message.get("type") == "subscribe":
                channel = message.get("channel")
                await websocket.send_json({
                    "type": "subscribed",
                    "channel": channel,
                })
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
}


@app.get("/api/bot/status")
async def get_bot_status():
    """Получить статус бота"""
    return {
        "is_running": bot_status["is_running"],
        "mode": bot_status["mode"],
        "last_started": bot_status["last_started"],
        "last_stopped": bot_status["last_stopped"],
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/bot/start")
async def start_bot():
    """Запустить бота"""
    global bot_status
    
    if bot_status["is_running"]:
        return {"status": "already_running", "message": "Bot is already running"}
    
    try:
        bot_status["is_running"] = True
        bot_status["last_started"] = datetime.now().isoformat()
        
        # Отправляем обновление всем WebSocket клиентам
        await broadcast_to_clients({
            "type": "bot_status_changed",
            "is_running": True,
            "message": "🚀 Bot started",
            "timestamp": datetime.now().isoformat(),
        })
        
        logger.info("Bot started via API")
        return {
            "status": "started",
            "message": "Bot started successfully",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        bot_status["is_running"] = False
        logger.error(f"Failed to start bot: {e}")
        return {"status": "error", "message": str(e)}, 500


@app.post("/api/bot/stop")
async def stop_bot():
    """Остановить бота"""
    global bot_status
    
    if not bot_status["is_running"]:
        return {"status": "already_stopped", "message": "Bot is not running"}
    
    try:
        bot_status["is_running"] = False
        bot_status["last_stopped"] = datetime.now().isoformat()
        
        # Отправляем обновление всем WebSocket клиентам
        await broadcast_to_clients({
            "type": "bot_status_changed",
            "is_running": False,
            "message": "🛑 Bot stopped",
            "timestamp": datetime.now().isoformat(),
        })
        
        logger.info("Bot stopped via API")
        return {
            "status": "stopped",
            "message": "Bot stopped successfully",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to stop bot: {e}")
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
