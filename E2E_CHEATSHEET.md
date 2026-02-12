# 📝 E2E Tests - Шпаргалка команд

## ⚡ Quick Start

### Самый быстрый способ
```bash
# Windows
.\run_e2e_tests.bat

# Linux/Mac
./run_e2e_tests.sh
```

---

## 🛠️ Установка

```bash
cd tests/e2e
npm install                          # Установить зависимости
npx playwright install              # Установить браузеры
npx playwright install chromium     # Только Chrome (быстрее)
```

---

## ▶️ Запуск тестов

### Основные команды
```bash
cd tests/e2e

npm test                    # Все тесты (headless)
npm run test:ui             # Интерактивный UI режим (рекомендуется)
npm run test:headed         # С видимым браузером
npm run test:debug          # Debug режим с паузами
```

### Запуск отдельных test suites
```bash
npm run test:settings       # TC1: Basic settings
npm run test:advanced       # TC2: Advanced settings
npm run test:validation     # TC4: Validation
```

### Запуск конкретного файла
```bash
npx playwright test settings.spec.ts
npx playwright test settings.advanced.spec.ts
```

### Запуск конкретного теста
```bash
npx playwright test -g "должен сохранить leverage"
npx playwright test -g "ATR multiplier"
```

---

## 📊 Отчёты

```bash
npm run report              # Открыть HTML отчёт
npx playwright show-report  # То же самое

# Отчёт после запуска автоматически предлагается открыть
```

---

## 🐛 Debugging

### Просмотр trace
```bash
npx playwright show-trace test-results/path/to/trace.zip
```

### Генерация тестов (codegen)
```bash
npx playwright codegen http://localhost:8000
```

### Selector inspector
```bash
npx playwright codegen http://localhost:8000
# Кликаете на элемент → получаете селектор
```

### Запуск с паузами
```bash
# В коде теста добавить:
await page.pause();

# Или запустить в debug режиме:
npm run test:debug
```

### Замедление выполнения
```bash
npx playwright test --headed --slow-mo=1000
# Каждое действие будет с задержкой 1 сек
```

---

## 📸 Screenshots & Videos

### Сделать screenshot в тесте
```typescript
await page.screenshot({ path: 'my-screenshot.png' });
await page.screenshot({ path: 'full-page.png', fullPage: true });
```

### Настройка в playwright.config.ts
```typescript
use: {
  screenshot: 'only-on-failure',  // Только при ошибках
  video: 'retain-on-failure',    // Видео только при ошибках
}
```

---

## 🔧 API Server

### Запустить API локально
```bash
# В отдельном терминале
python run_api.py

# Проверить что работает
curl http://localhost:8000/health
```

### Пропустить автозапуск сервера
```bash
export SKIP_SERVER_START=1
npm test
```

### Использовать другой URL
```bash
export BASE_URL=http://192.168.1.100:8000
npm test
```

---

## 🧪 Тестовые API endpoints

### Проверить effective config
```bash
curl http://localhost:8000/api/bot/effective-config | jq .
```

### Проверить last order intent
```bash
curl http://localhost:8000/api/bot/last-order-intent | jq .
```

### Запустить один тик бота
```bash
curl -X POST http://localhost:8000/api/bot/run-once | jq .
```

### Стартовать/остановить бота
```bash
curl -X POST http://localhost:8000/api/bot/start | jq .
curl -X POST http://localhost:8000/api/bot/stop | jq .
```

---

## 📝 Написание тестов

### Базовый шаблон
```typescript
import { test, expect } from '@playwright/test';

test('должен проверить что-то', async ({ page, request }) => {
  // Arrange
  await page.goto('/');
  
  // Act
  await page.fill('[data-testid="my-input"]', 'value');
  await page.click('[data-testid="save-button"]');
  
  // Assert
  const response = await request.get('/api/bot/effective-config');
  const data = await response.json();
  
  expect(data.config.my_param).toBe('value');
});
```

### Использование helpers
```typescript
import { login, goToSettings, saveSettings } from './helpers';

test('с helpers', async ({ page, request }) => {
  await page.goto('/');
  await login(page);
  await goToSettings(page);
  
  // ... изменения
  
  await saveSettings(page);
});
```

---

## 🎯 Селекторы

### Все data-testid
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

### Использование
```typescript
await page.fill('[data-testid="settings-risk-position-risk"]', '2.5');
await page.click('[data-testid="settings-save-button"]');
```

---

## ⚙️ Конфигурация

### playwright.config.ts
```typescript
workers: 1,                    // Последовательное выполнение
retries: process.env.CI ? 2 : 0,    // Retry в CI
timeout: 30000,                // Таймаут теста
baseURL: 'http://localhost:8000',
```

### package.json scripts
```json
{
  "test": "playwright test",
  "test:headed": "playwright test --headed",
  "test:ui": "playwright test --ui",
  "test:debug": "playwright test --debug"
}
```

---

## 🚀 CI/CD

### Локально симулировать CI
```bash
CI=1 npm test
```

### GitHub Actions
Автоматически запускается при:
- Pull Request в `main`/`develop`
- Push в `main`
- Manual dispatch

Посмотреть результаты:
- GitHub → Actions → E2E Tests

Скачать artifacts:
- Screenshots
- Videos
- HTML report

---

## 🔍 Troubleshooting

### "Server not ready"
```bash
# Проверить что API работает
curl http://localhost:8000/health

# Увеличить timeout в playwright.config.ts
webServer: {
  timeout: 180000,  // 3 минуты
}
```

### "Element not found"
```bash
# Сгенерировать новый селектор
npx playwright codegen http://localhost:8000

# Проверить что data-testid есть в HTML
curl http://localhost:8000 | grep data-testid
```

### "Test timeout"
```typescript
// Увеличить timeout для конкретного теста
test('slow test', async ({ page }) => {
  test.setTimeout(60000);  // 60 секунд
  // ...
});
```

### Очистить кэш
```bash
# Удалить результаты предыдущих запусков
rm -rf test-results playwright-report

# Переустановить зависимости
rm -rf node_modules package-lock.json
npm install
```

---

## 📚 Полезные ссылки

- [Playwright Docs](https://playwright.dev/)
- [Playwright API](https://playwright.dev/docs/api/class-playwright)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)

---

## 💡 Pro Tips

1. **Используйте test:ui для разработки** — видно что происходит
2. **Добавляйте page.pause() для debugging** — остановка в нужном месте
3. **Смотрите trace при падении** — детальная информация
4. **Используйте helpers** — переиспользуемый код
5. **Проверяйте effective-config** — гарантия что настройки применены

---

## 📋 Чеклист перед коммитом

- [ ] Все тесты проходят локально (`npm test`)
- [ ] API сервер запускается (`python run_api.py`)
- [ ] Нет hardcoded значений (порты, URL, etc.)
- [ ] data-testid присутствуют для новых элементов
- [ ] Добавлены тесты для новых настроек
- [ ] Документация обновлена (если нужно)

---

**Всё самое нужное в одном месте! 🎯**
