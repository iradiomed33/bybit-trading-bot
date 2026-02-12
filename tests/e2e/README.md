# E2E Testing для Bybit Trading Bot

## Описание

E2E тесты для проверки что настройки UI реально влияют на поведение бота.

### Что тестируется

1. **TC1: Basic Settings → Runtime Config**
   - Настройки UI корректно сохраняются
   - API отдаёт сохранённые значения
   - `effective-config` отражает изменения
   - `config_version` обновляется

2. **TC2: Advanced Settings → Order Intent**
   - Advanced настройки применяются в торговой логике
   - SL/TP рассчитываются через ATR-мультипликаторы
   - No-trade zone и MTF фильтры работают
   - Dry-run режим формирует intents без реальных ордеров

3. **TC4: Settings Validation**
   - Невалидные значения отклоняются
   - HTML5 и API валидация работают
   - Config не портится при ошибках

## Установка

```bash
cd tests/e2e
npm install
```

Playwright автоматически установит браузеры:

```bash
npx playwright install
```

## Запуск тестов

### Все тесты (headless)
```bash
npm test
```

### С UI (интерактивный режим)
```bash
npm run test:ui
```

### С видимым браузером
```bash
npm run test:headed
```

### Отладка отдельного теста
```bash
npm run test:debug
```

### Только определённый набор
```bash
npm run test:settings        # TC1
npm run test:advanced        # TC2
npm run test:validation      # TC4
```

## Отчёты

После запуска тестов:

```bash
npm run report
```

Откроет HTML отчёт с результатами, скриншотами и видео.

## Структура

```
tests/e2e/
├── package.json              # Зависимости (Playwright)
├── playwright.config.ts      # Конфигурация
├── tsconfig.json            # TypeScript конфиг
├── tests/
│   ├── settings.spec.ts           # TC1: Basic settings
│   ├── settings.advanced.spec.ts  # TC2: Advanced settings
│   └── settings.validation.spec.ts # TC4: Validation
└── README.md
```

## CI/CD Integration

Тесты автоматически запускаются в GitHub Actions при PR:

```yaml
- name: E2E Tests
  run: |
    cd tests/e2e
    npm ci
    npx playwright install --with-deps
    npm test
```

## Требования

- **Python API должен быть запущен** на `http://localhost:8000`
- Или установить `SKIP_SERVER_START=1` и `BASE_URL` для внешнего сервера
- Node.js 18+ для Playwright

## Debugging

### Посмотреть trace
```bash
npx playwright show-trace test-results/path-to-trace.zip
```

### Selector inspector
```bash
npx playwright codegen http://localhost:8000
```

## Best Practices

1. **data-testid** - используются для стабильных селекторов
2. **Dry-run режим** - тесты не размещают реальные ордера
3. **Изоляция** - каждый тест независим (но последовательно)
4. **Wait strategies** - `waitForTimeout` минимизирован, используются умные ожидания

## Troubleshooting

### Тесты падают с "Server not ready"
- Убедитесь что `python run_api.py` работает на порту 8000
- Проверьте логи сервера
- Увеличьте `timeout` в `playwright.config.ts`

### "Element not found"
- Проверьте что data-testid присутствуют в HTML
- Используйте `npx playwright codegen` для генерации селекторов

### Тесты проходят но не убеждены
- Проверьте что bot_instance создан (`/api/bot/start` вызван)
- Проверьте что БД не пуста (есть intents)
- Посмотрите логи бота в консоли

## Support

Вопросы и баги → создайте Issue в GitHub.
