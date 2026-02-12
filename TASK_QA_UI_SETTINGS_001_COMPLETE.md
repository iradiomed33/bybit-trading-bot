# TASK-QA-UI-SETTINGS-001: E2E Автотесты — Реализация Завершена ✅

## 📋 Обзор

Реализован комплексный набор E2E тестов для проверки того, что **настройки UI реально влияют на поведение бота**, включая Advanced настройки.

## 🎯 Цель (достигнута)

Создать набор автотестов, который проверяет полную цепочку:

```
UI (ввод) → Save → API (persist) → Bot runtime (effective config) → Действие бота (order intent)
```

## ✅ Что реализовано

### 1. Backend Introspection (Вариант A + B)

#### ✅ Endpoint: GET `/api/bot/effective-config`
- Возвращает фактический runtime config бота
- Включает `config_version` для отслеживания изменений
- Включает `updated_at` для временных меток
- Показывает runtime статус бота (is_running, mode, symbol)

**Пример ответа:**
```json
{
  "status": "success",
  "data": {
    "config": { ... },
    "config_version": 5,
    "updated_at": "2026-02-11T15:30:00",
    "bot_runtime": {
      "is_running": true,
      "mode": "paper",
      "symbol": "BTCUSDT"
    }
  }
}
```

#### ✅ Endpoint: GET `/api/bot/last-order-intent`
- Возвращает последнее решение бота (что хотел сделать)
- Показывает: leverage, SL/TP, qty, risk inputs, strategy, regime
- Идеально для проверки влияния advanced-настроек

**Пример ответа:**
```json
{
  "status": "success",
  "data": {
    "symbol": "BTCUSDT",
    "side": "Buy",
    "leverage": 7,
    "stop_loss": "95000.0",
    "take_profit": "98000.0",
    "strategy": "TrendPullback",
    "regime": "Trending",
    "atr_value": 500.0,
    "sl_atr_mult": 1.8,
    "tp_atr_mult": 2.6,
    "no_trade_zone_enabled": false,
    "mtf_score": 0.75,
    "dry_run": true
  }
}
```

#### ✅ Endpoint: POST `/api/bot/run-once`
- Запускает один цикл бота в dry-run режиме
- Проходит весь пайплайн стратегии/риска
- Формирует order intent
- **НЕ размещает реальный ордер** (безопасно для тестов)
- Сохраняет intent в БД

### 2. Database Schema: `order_intents`

Новая таблица для хранения намерений разместить ордера:

```sql
CREATE TABLE order_intents (
    id INTEGER PRIMARY KEY,
    timestamp REAL,
    symbol TEXT,
    side TEXT,
    leverage INTEGER,
    stop_loss TEXT,
    take_profit TEXT,
    strategy TEXT,
    regime TEXT,
    atr_value REAL,
    sl_atr_mult REAL,
    tp_atr_mult REAL,
    no_trade_zone_enabled INTEGER,
    mtf_score REAL,
    dry_run INTEGER,
    metadata TEXT
)
```

Методы:
- `db.save_order_intent(intent_data)` - сохранить intent
- `db.get_last_order_intent(symbol=None)` - получить последний
- `db.get_order_intents(limit, symbol)` - список intents

### 3. Config Versioning

`ConfigManager` теперь отслеживает версии:

- `_version` - инкрементируется при каждом `save()`
- `_updated_at` - timestamp последнего обновления
- Позволяет E2E тестам проверить что конфиг реально обновился

### 4. Dry-Run Режим в TradingBot

Новый метод `bot.run_single_tick()`:
- Выполняет один цикл обработки
- Работает в dry-run режиме (`_dry_run_mode=True`)
- Возвращает результат (сигнал + order intent)
- Безопасен для тестов (не размещает реальные ордера)

### 5. UI: data-testid атрибуты

Добавлены стабильные селекторы для всех критичных элементов:

**Basic Settings:**
- `settings-symbols`
- `settings-mode`
- `settings-risk-position-risk`
- `settings-risk-max-positions`
- `settings-risk-max-notional`
- `settings-sl-percent`
- `settings-tp-percent`

**Advanced Settings:**
- `settings-advanced-high-vol-atr`
- `settings-advanced-no-trade-max-atr`
- `settings-advanced-no-trade-max-spread`
- `settings-advanced-use-mtf`
- `settings-advanced-mtf-threshold`

**Actions:**
- `settings-save-button`
- `settings-reset-button`

### 6. E2E Test Suite (Playwright + TypeScript)

#### Структура:
```
tests/e2e/
├── package.json
├── playwright.config.ts
├── tsconfig.json
├── tests/
│   ├── settings.spec.ts           # TC1: Basic settings
│   ├── settings.advanced.spec.ts  # TC2: Advanced settings
│   └── settings.validation.spec.ts # TC4: Validation
└── README.md
```

#### TC1: Basic Settings влияют на Runtime Config ✅
- Изменяет `max_leverage`, `stop_loss_percent`, `take_profit_percent`
- Сохраняет через UI
- Проверяет что:
  - API `/api/config/{section}` отдаёт новые значения
  - `/api/bot/effective-config` отражает изменения
  - `config_version` обновился
  - `updated_at` обновился

#### TC2: Advanced Settings влияют на Order Intent ✅
- Включает/выключает MTF, меняет ATR пороги
- Запускает `POST /api/bot/run-once`
- Проверяет что:
  - SL/TP рассчитаны через ATR-мультипликаторы
  - `no_trade_zone_enabled` корректно установлен
  - `mtf_score` присутствует в intent
  - Leverage взят из настроек

#### TC4: Валидация недопустимых значений ✅
- Пытается установить отрицательные значения
- Пытается установить leverage=0, SL/TP=0
- Проверяет что:
  - HTML5 валидация блокирует невалидный ввод
  - API возвращает ошибку при прямой отправке
  - `config_version` не меняется при ошибке
  - Эффективный конфиг не портится

### 7. CI/CD Integration

GitHub Actions workflow (`.github/workflows/e2e.yml`):

```yaml
- Устанавливает Python + зависимости
- Устанавливает Node.js + Playwright
- Запускает API сервер в фоне
- Запускает E2E тесты
- Загружает артефакты (screenshots, videos, report)
- Комментирует PR с результатами
```

Триггеры:
- Pull Request в `main` или `develop`
- Push в `main`
- Manual dispatch

## 📦 Deliverables (все выполнены)

- ✅ `tests/e2e/tests/settings.spec.ts` — TC1
- ✅ `tests/e2e/tests/settings.advanced.spec.ts` — TC2
- ✅ `tests/e2e/tests/settings.validation.spec.ts` — TC4
- ✅ `.github/workflows/e2e.yml` — CI job
- ✅ `tests/e2e/README.md` — документация
- ✅ Все `data-testid` в HTML
- ✅ Introspection endpoints в API
- ✅ Dry-run режим в боте

## 🚀 Как запустить

### Локально

1. **Установить зависимости:**
```bash
cd tests/e2e
npm install
npx playwright install
```

2. **Запустить API:**
```bash
# В корне проекта
python run_api.py
```

3. **Запустить тесты:**
```bash
cd tests/e2e
npm test                # Headless
npm run test:ui         # Interactive mode
npm run test:headed     # With browser visible
```

4. **Посмотреть отчёт:**
```bash
npm run report
```

### В CI

Автоматически запускается при PR. Результаты в GitHub Actions.

## 🎓 Acceptance Criteria (выполнены)

- ✅ **Есть стабильные селекторы** `data-testid` для всех полей Settings + Advanced
- ✅ **Есть интроспекция** `effective-config` (Вариант A) ✓
- ✅ **Есть dry-run + last-order-intent** (Вариант B) ✓
- ✅ **Есть минимум 3 E2E теста** (TC1, TC2, TC4) ✓
- ✅ **Тесты падают если бот использует хардкод** (проверяют effective config) ✓
- ✅ **Тесты проходят если бот реально подхватывает UI-настройки** ✓
- ✅ **Тесты не требуют реальной Bybit** (dry-run mode) ✓
- ✅ **E2E job запускается в CI на PR** ✓

## 🔒 Безопасность

- **Все тесты в dry-run режиме** — не размещают реальные ордера
- **Используют testnet конфиг** в CI
- **Изолированы от production** данных

## 📊 Метрики покрытия

- **3 test suites** (settings, advanced, validation)
- **~10 test cases** суммарно
- **Покрывают критичные пути:**
  - Basic risk settings
  - Advanced ATR/MTF settings
  - SL/TP calculation
  - No-trade zones
  - Validation логика

## 🎯 Что гарантируют тесты

1. **UI → API → Storage**: настройки корректно сохраняются
2. **Storage → Bot Runtime**: бот подхватывает настройки из конфига
3. **Bot Runtime → Trading Actions**: настройки влияют на SL/TP/leverage/фильтры
4. **Regression Safety**: изменения в коде не сломают влияние UI на бота

## 🔧 Расширение

### Добавить новый тест-кейс:

```typescript
// tests/e2e/tests/my-feature.spec.ts
import { test, expect } from '@playwright/test';

test('должен проверить новую фичу', async ({ page, request }) => {
  // Arrange
  await page.goto('/');
  
  // Act
  // ... изменить настройки
  
  // Assert
  const config = await request.get('/api/bot/effective-config');
  // ... проверки
});
```

### Добавить новый endpoint для интроспекции:

```python
# api/app.py
@app.get("/api/bot/my-introspection")
async def get_my_introspection():
    # Вернуть runtime состояние
    return {"data": {...}}
```

## 📚 Полезные ссылки

- [Playwright Documentation](https://playwright.dev/)
- [tests/e2e/README.md](tests/e2e/README.md) — детали запуска
- [.github/workflows/e2e.yml](.github/workflows/e2e.yml) — CI конфигурация

## ✅ Статус: ВЫПОЛНЕНО

Все требования TASK-QA-UI-SETTINGS-001 (P0) реализованы и готовы к использованию.

🎉 **E2E тесты гарантируют что UI настройки реально влияют на бота!**
