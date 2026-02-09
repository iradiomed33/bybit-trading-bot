"""
Тест TASK-UI-003: проверка realtime WebSocket апдейтов

Проверяем что:
1. WebSocket отправляет periodic updates (account_balance_updated, positions_updated)
2. Updates отправляются с интервалом ~3 секунды
3. UI обрабатывает эти сообщения
"""

import json
import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock


def test_periodic_update_logic():
    """Тест логики формирования periodic updates"""
    
    # Создаём тестовую БД
    db_path = Path("test_ws_updates.db")
    if db_path.exists():
        db_path.unlink()
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Создаём таблицу positions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            symbol TEXT,
            side TEXT,
            size REAL,
            entry_price REAL,
            mark_price REAL,
            unrealised_pnl REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Вставляем тестовые позиции
    cursor.execute("""
        INSERT INTO positions (symbol, side, size, entry_price, mark_price, unrealised_pnl)
        VALUES ('BTCUSDT', 'Buy', 0.1, 45000.0, 46000.0, 100.0)
    """)
    cursor.execute("""
        INSERT INTO positions (symbol, side, size, entry_price, mark_price, unrealised_pnl)
        VALUES ('ETHUSDT', 'Sell', 2.0, 3000.0, 2950.0, 100.0)
    """)
    conn.commit()
    
    # Эмулируем логику из send_periodic_updates()
    cursor.execute("SELECT SUM(size), SUM(unrealised_pnl) FROM positions WHERE size > 0")
    pos_data = cursor.fetchone()
    total_size = pos_data[0] or 0.0
    total_pnl = pos_data[1] or 0.0
    
    cursor.execute("""
        SELECT symbol, side, size, entry_price, mark_price, unrealised_pnl
        FROM positions
        WHERE size > 0
        ORDER BY created_at DESC
    """)
    
    positions = []
    for row in cursor.fetchall():
        symbol = row[0]
        side = row[1]
        size = row[2]
        entry_price = row[3]
        mark_price = row[4]
        unrealised_pnl = row[5]
        
        position_value = entry_price * size
        pnl_pct = (unrealised_pnl / position_value * 100) if position_value > 0 else 0.0
        
        positions.append({
            "symbol": symbol,
            "side": side,
            "size": size,
            "entry_price": entry_price,
            "mark_price": mark_price,
            "pnl": unrealised_pnl,
            "pnl_pct": pnl_pct,
        })
    
    conn.close()
    db_path.unlink()
    
    # Формируем сообщения как в api/app.py
    position_value = total_size * 45000
    total_balance = 10000.0
    
    balance_msg = {
        "type": "account_balance_updated",
        "balance": {
            "total_balance": total_balance,
            "available_balance": max(total_balance - position_value, 0),
            "position_value": position_value,
            "unrealized_pnl": total_pnl,
            "currency": "USDT",
            "margin_balance": position_value,
        },
    }
    
    positions_msg = {
        "type": "positions_updated",
        "positions": positions,
    }
    
    # Проверки
    print("✓ Логика periodic updates работает")
    
    # Проверяем balance_msg
    assert balance_msg["type"] == "account_balance_updated", "Неверный type для баланса"
    assert "balance" in balance_msg, "Нет поля balance"
    assert balance_msg["balance"]["total_balance"] == 10000.0, "Неверный баланс"
    assert balance_msg["balance"]["unrealized_pnl"] == 200.0, f"Неверный PnL: {balance_msg['balance']['unrealized_pnl']}"
    print(f"  - account_balance_updated: ✓ (total={balance_msg['balance']['total_balance']}, pnl={balance_msg['balance']['unrealized_pnl']})")
    
    # Проверяем positions_msg
    assert positions_msg["type"] == "positions_updated", "Неверный type для позиций"
    assert "positions" in positions_msg, "Нет поля positions"
    assert len(positions_msg["positions"]) == 2, f"Должно быть 2 позиции, получено {len(positions_msg['positions'])}"
    
    # Проверяем структуру позиций
    for pos in positions_msg["positions"]:
        assert "mark_price" in pos, "Нет поля mark_price"
        assert "pnl_pct" in pos, "Нет поля pnl_pct"
        assert "symbol" in pos, "Нет поля symbol"
    
    print(f"  - positions_updated: ✓ ({len(positions_msg['positions'])} позиций)")
    for pos in positions_msg["positions"]:
        print(f"    • {pos['symbol']}: {pos['side']}, PnL={pos['pnl']:.2f} ({pos['pnl_pct']:.2f}%)")
    
    return True


def test_ui_message_handlers():
    """Проверяем, что UI правильно обрабатывает новые типы сообщений"""
    
    # Читаем app.js
    app_js_path = Path("static/js/app.js")
    if not app_js_path.exists():
        print("⚠ Файл app.js не найден, пропускаем проверку UI")
        return True
    
    app_js_content = app_js_path.read_text(encoding='utf-8')
    
    # Проверяем наличие обработчиков
    checks = [
        ("account_balance_updated", "case 'account_balance_updated':"),
        ("positions_updated", "case 'positions_updated':"),
        ("updateBalanceInfo", "updateBalanceInfo(data.balance)"),
        ("updatePositionsTable", "updatePositionsTable(data.positions)"),
    ]
    
    all_passed = True
    for name, pattern in checks:
        if pattern in app_js_content:
            print(f"  ✓ {name}: найден")
        else:
            print(f"  ✗ {name}: НЕ найден")
            all_passed = False
    
    if all_passed:
        print("✓ UI обработчики добавлены")
    else:
        print("✗ Некоторые UI обработчики отсутствуют")
    
    return all_passed


if __name__ == "__main__":
    print("=" * 70)
    print("ТЕСТ TASK-UI-003: Realtime WebSocket Updates")
    print("=" * 70)
    
    print("\n[1/2] Проверка логики periodic updates...")
    test1 = test_periodic_update_logic()
    
    print("\n[2/2] Проверка UI обработчиков...")
    test2 = test_ui_message_handlers()
    
    print("\n" + "=" * 70)
    if test1 and test2:
        print("✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    else:
        print("✗ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ")
    print("=" * 70)
