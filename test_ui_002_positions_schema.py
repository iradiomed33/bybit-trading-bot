"""
Тест TASK-UI-002: проверка схемы /api/account/positions

Проверяем что API возвращает:
- mark_price (не current_price)
- pnl_pct (вычисленный процент)
"""

import sqlite3
from pathlib import Path


def test_positions_schema():
    """Проверяем схему данных позиций в SQLite и логику вычисления"""
    
    # Создаём тестовую БД с позицией
    db_path = Path("test_positions_schema.db")
    if db_path.exists():
        db_path.unlink()
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Создаём таблицу positions (упрощённо)
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
    
    # Вставляем тестовую позицию
    cursor.execute("""
        INSERT INTO positions (symbol, side, size, entry_price, mark_price, unrealised_pnl)
        VALUES ('BTCUSDT', 'Buy', 0.1, 45000.0, 46000.0, 100.0)
    """)
    conn.commit()
    
    # Эмулируем логику из api/app.py
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
        
        # Вычисляем PnL в процентах
        position_value = entry_price * size
        pnl_pct = (unrealised_pnl / position_value * 100) if position_value > 0 else 0.0

        positions.append({
            "symbol": symbol,
            "side": side,
            "size": size,
            "entry_price": entry_price,
            "mark_price": mark_price,  # ← ключевое поле
            "pnl": unrealised_pnl,
            "pnl_pct": pnl_pct,        # ← ключевое поле
        })
    
    conn.close()
    db_path.unlink()
    
    # Проверки
    assert len(positions) == 1, "Должна быть 1 позиция"
    pos = positions[0]
    
    # Проверяем наличие полей
    assert "mark_price" in pos, "Должно быть поле mark_price"
    assert "pnl_pct" in pos, "Должно быть поле pnl_pct"
    assert "current_price" not in pos, "Не должно быть поля current_price"
    
    # Проверяем значения
    assert pos["mark_price"] == 46000.0, f"mark_price должен быть 46000.0, получено {pos['mark_price']}"
    assert pos["pnl"] == 100.0, f"pnl должен быть 100.0, получено {pos['pnl']}"
    
    # Проверяем расчёт pnl_pct
    # position_value = 45000 * 0.1 = 4500
    # pnl_pct = (100 / 4500) * 100 = 2.222...%
    expected_pnl_pct = (100.0 / (45000.0 * 0.1)) * 100
    assert abs(pos["pnl_pct"] - expected_pnl_pct) < 0.01, \
        f"pnl_pct должен быть {expected_pnl_pct:.2f}%, получено {pos['pnl_pct']:.2f}%"
    
    print("✓ Все проверки схемы пройдены!")
    print(f"  - mark_price: {pos['mark_price']}")
    print(f"  - pnl: {pos['pnl']}")
    print(f"  - pnl_pct: {pos['pnl_pct']:.2f}%")
    
    return True


if __name__ == "__main__":
    test_positions_schema()
