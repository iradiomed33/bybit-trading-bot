# TASK-UI-002: Исправление несовместимости схемы /api/account/positions

**Статус:** ✅ ВЫПОЛНЕНО  
**Дата:** 2026-02-09  
**Приоритет:** P0

## Проблема

UI ожидал поля `mark_price` и `pnl_pct`, а API возвращал `current_price` и только `pnl`.

### Несовместимость

**UI** (`static/js/app.js`):
```javascript
parseFloat(pos.mark_price).toFixed(2)    // ❌ API отдавал current_price
parseFloat(pos.pnl_pct || 0).toFixed(2)  // ❌ API не отдавал pnl_pct
```

**API** (`api/app.py`):
```python
{
    "current_price": row[4],  # ❌ должно быть mark_price
    "pnl": row[5],           # ✓ есть, но нет pnl_pct
}
```

**Результат:** В UI отображались `NaN` или пустые значения.

---

## Решение

### Изменения в `api/app.py`

**Файл:** `api/app.py`, функция `get_positions()` (строки ~1058-1078)

**До:**
```python
positions.append({
    "symbol": row[0],
    "side": row[1],
    "size": row[2],
    "entry_price": row[3],
    "current_price": row[4],  # ❌
    "pnl": row[5],           # ❌ нет pnl_pct
})
```

**После:**
```python
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
    "mark_price": mark_price,      # ✓ правильное имя поля
    "pnl": unrealised_pnl,
    "pnl_pct": pnl_pct,           # ✓ добавлен расчёт
})
```

### Ключевые изменения

1. **Переименование поля:**  
   `current_price` → `mark_price` (совместимо с UI)

2. **Добавление `pnl_pct`:**  
   - Формула: `pnl_pct = (unrealised_pnl / (entry_price * size)) * 100`
   - Защита от деления на ноль: `if position_value > 0 else 0.0`

3. **Контракт API (финальная схема):**
   ```json
   {
     "symbol": "BTCUSDT",
     "side": "Buy",
     "size": 0.1,
     "entry_price": 45000.0,
     "mark_price": 46000.0,
     "pnl": 100.0,
     "pnl_pct": 2.22
   }
   ```

---

## Тестирование

### Модульный тест

**Файл:** `test_ui_002_positions_schema.py`

**Результат:**
```
✓ Все проверки схемы пройдены!
  - mark_price: 46000.0
  - pnl: 100.0
  - pnl_pct: 2.22%
```

### Acceptance Criteria

| Критерий | Статус | Комментарий |
|----------|--------|-------------|
| В таблице позиций нет NaN/пустых значений по цене | ✅ | `mark_price` теперь возвращается API |
| В таблице позиций нет NaN/пустых значений по %PnL | ✅ | `pnl_pct` вычисляется на бэке |
| Данные обновляются | ✅ | UI poll'ит `/api/account/positions` каждые 15 сек |

---

## Проверка в боевом режиме

### Как проверить

1. Запустить API:
   ```bash
   python run_api.py
   ```

2. Открыть UI: `http://localhost:8000`

3. Перейти на вкладку **"Аккаунт"**

4. Если есть позиции в SQLite → должны отображаться с корректными:
   - `mark_price` (текущая цена)
   - `pnl_pct` (процент прибыли/убытка)

### Пример данных

| Symbol | Side | Size | Entry | Mark Price | PnL | PnL % |
|--------|------|------|-------|------------|-----|-------|
| BTCUSDT | Buy | 0.1 | $45,000 | $46,000 | $100 | **2.22%** |

---

## Дополнительные замечания

### Ограничения текущей реализации

⚠️ **Позиции всё ещё берутся из SQLite, а не с биржи**

Это будет исправлено в **TASK-UI-001**, которая добавит:
- Получение реальных позиций через `AccountClient.get_positions()`
- Актуальные `mark_price` с биржи
- Реальный PnL

### Текущее поведение

- ✅ Схема API ↔ UI **совместима**
- ⚠️ Данные **из SQLite** (могут быть устаревшими)
- ⚠️ `mark_price` берётся из локальной БД, а не с биржи

### После внедрения TASK-UI-001

- ✅ Позиции с биржи в реальном времени
- ✅ `mark_price` актуальная с Bybit
- ✅ `pnl_pct` на основе реальных данных

---

## Файлы изменены

- `api/app.py` — функция `get_positions()` (строки ~1058-1078)

## Файлы созданы

- `test_ui_002_positions_schema.py` — модульный тест схемы

## Коммит

```bash
git add api/app.py test_ui_002_positions_schema.py TASK_UI_002_COMPLETE.md
git commit -m "fix(api): TASK-UI-002 - fix positions schema compatibility with UI

- Rename current_price → mark_price
- Add pnl_pct calculation (unrealised_pnl / position_value * 100)
- Fix NaN values in UI positions table
- Add test_ui_002_positions_schema.py for validation"
```

---

## Связанные задачи

- **TASK-UI-001** (P0) — Получение реальных данных с биржи (вместо SQLite/демо)
- **TASK-UI-003** (P1) — WebSocket live updates для позиций

---

**Автор:** GitHub Copilot  
**Версия API:** v1.0
