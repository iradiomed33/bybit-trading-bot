# 💡 E2E Testing: Практические Примеры

## Пример 1: Проверить что новая настройка работает

### Сценарий
Добавили новую настройку `max_daily_trades` в UI. Нужно проверить что бот её использует.

### Шаги

**1. Добавить data-testid в HTML:**
```html
<input 
  type="number" 
  id="settingMaxDailyTrades" 
  data-testid="settings-max-daily-trades"
  min="1" 
  max="100" 
  value="10"
/>
```

**2. Убедиться что ConfigManager сохраняет:**
```python
# Обычно не нужно менять, ConfigManager автоматически сохраняет
# Но можно добавить валидацию:
config.set("execution.max_daily_trades", value)
config.save()  # Автоматически инкрементирует _version
```

**3. Использовать в trading_bot.py:**
```python
class TradingBot:
    def __init__(self, ...):
        self.max_daily_trades = self.config.get("execution.max_daily_trades", 10)
    
    def _process_signal(self, signal):
        today_trades = self.db.get_today_trades_count()
        
        if today_trades >= self.max_daily_trades:
            logger.warning(f"Max daily trades reached: {today_trades}/{self.max_daily_trades}")
            return
        
        # ... продолжить обработку
```

**4. Добавить E2E тест:**
```typescript
// tests/e2e/tests/settings.spec.ts
test('должен соблюдать max_daily_trades', async ({ page, request }) => {
  // Arrange
  const maxTrades = 3;
  
  await page.goto('/');
  await login(page);
  await goToSettings(page);
  
  // Act
  await page.fill('[data-testid="settings-max-daily-trades"]', maxTrades.toString());
  await saveSettings(page);
  
  // Assert 1: Config updated
  const config = await getEffectiveConfig(request);
  expect(config.data.config.execution.max_daily_trades).toBe(maxTrades);
  
  // Assert 2: Bot respects limit
  await startBot(request);
  
  // Simulate multiple signals
  for (let i = 0; i < 5; i++) {
    await runBotOnce(request);
  }
  
  // Check that only maxTrades were executed
  const intents = await request.get('/api/bot/order-intents?limit=10');
  const data = await intents.json();
  
  const todayIntents = data.data.filter(intent => 
    new Date(intent.created_at).toDateString() === new Date().toDateString()
  );
  
  expect(todayIntents.length).toBeLessThanOrEqual(maxTrades);
  
  await stopBot(request);
});
```

**5. Запустить тест:**
```bash
cd tests/e2e
npm test -- settings.spec.ts -g "max_daily_trades"
```

---

## Пример 2: Проверить Advanced настройку (ATR)

### Сценарий
Изменили ATR multiplier для SL. Нужно убедиться что SL реально рассчитывается через новый коэффициент.

### E2E Тест

```typescript
// tests/e2e/tests/settings.advanced.spec.ts
test('должен использовать новый ATR multiplier для SL', async ({ page, request }) => {
  await page.goto('/');
  await login(page);
  await goToSettings(page);
  await openAdvancedSettings(page);
  
  // Act: Устанавливаем новый ATR mult
  const newSlMult = 2.5;
  
  // Находим поле для SL ATR multiplier
  // (предполагаем что оно есть в Advanced, если нет - добавить)
  await page.fill('[data-testid="settings-advanced-sl-atr-mult"]', newSlMult.toString());
  await saveSettings(page);
  
  // Assert 1: Config сохранился
  const config = await getEffectiveConfig(request);
  expect(config.data.config.stop_loss_tp.sl_atr_multiplier).toBe(newSlMult);
  
  // Assert 2: Бот использует в расчётах
  await startBot(request);
  
  const runResult = await runBotOnce(request);
  
  if (runResult.data?.order_intent) {
    const intent = runResult.data.order_intent;
    
    // Проверяем что SL рассчитан с новым multiplier
    expect(intent.sl_atr_mult).toBe(newSlMult);
    
    // Проверяем математику: SL должен быть на расстоянии ATR * mult от цены
    const price = parseFloat(intent.price);
    const sl = parseFloat(intent.stop_loss);
    const atr = intent.atr_value;
    
    const expectedDistance = atr * newSlMult;
    const actualDistance = Math.abs(price - sl);
    
    // Допускаем небольшую погрешность из-за округления
    expect(actualDistance).toBeCloseTo(expectedDistance, 1);
    
    console.log(`✅ SL корректно рассчитан: price=${price}, sl=${sl}, distance=${actualDistance} (expected=${expectedDistance})`);
  }
  
  await stopBot(request);
});
```

---

## Пример 3: Негативный тест (валидация)

### Сценарий
Убедиться что нельзя установить leverage > 100.

### E2E Тест

```typescript
// tests/e2e/tests/settings.validation.spec.ts
test('должен блокировать leverage > 100', async ({ page, request }) => {
  await page.goto('/');
  await login(page);
  
  // Получаем начальную версию
  const initialConfig = await getEffectiveConfig(request);
  const initialVersion = initialConfig.data.config_version;
  const initialLeverage = initialConfig.data.config.risk_management.max_leverage;
  
  // Пытаемся установить недопустимое значение через API
  // (обходим HTML5 валидацию чтобы проверить backend)
  const updateResponse = await request.post('/api/config/risk_management.max_leverage', {
    data: { value: 150 }
  });
  
  // Backend должен либо отклонить либо привести к макс значению
  const afterConfig = await getEffectiveConfig(request);
  
  // Leverage НЕ должен стать 150
  expect(afterConfig.data.config.risk_management.max_leverage).not.toBe(150);
  
  // Должен остаться либо прежним либо быть <= 100
  expect(afterConfig.data.config.risk_management.max_leverage).toBeLessThanOrEqual(100);
  
  // Можно также проверить что версия не изменилась если валидация сработала на этапе set()
  // (зависит от реализации валидации)
  
  console.log(`✅ Leverage остался безопасным: ${afterConfig.data.config.risk_management.max_leverage}`);
});
```

---

## Пример 4: Проверить влияние No-Trade Zone

### Сценарий
При высоком ATR (>14%) бот должен блокировать торговлю.

### E2E Тест

```typescript
test('должен блокировать торговлю при высоком ATR', async ({ page, request }) => {
  await page.goto('/');
  await login(page);
  await goToSettings(page);
  await openAdvancedSettings(page);
  
  // Устанавливаем низкий порог no-trade zone
  const maxAtr = 5.0;  // Очень низкий порог - любой рынок будет заблокирован
  
  await page.fill('[data-testid="settings-advanced-no-trade-max-atr"]', maxAtr.toString());
  await saveSettings(page);
  
  // Запускаем бота
  await startBot(request);
  
  // Запускаем один тик
  const result = await runBotOnce(request);
  
  // Ожидаем что сигнал заблокирован
  // (может быть "no_signal" или result.status содержит информацию о блокировке)
  
  // Вариант 1: Проверяем order_intent - его не должно быть или должен быть флаг блокировки
  const intentResponse = await request.get('/api/bot/last-order-intent');
  const intentData = await intentResponse.json();
  
  if (intentData.data) {
    // Если intent есть, проверяем что no_trade_zone_enabled = true
    expect(intentData.data.no_trade_zone_enabled).toBe(true);
  }
  
  // Вариант 2: Проверяем логи или статус run-once
  if (result.status === 'no_signal') {
    // Ок, сигнал заблокирован
    console.log('✅ No-trade zone correctly blocked signal');
  }
  
  await stopBot(request);
});
```

---

## Пример 5: Полный сценарий изменения профиля риска

### Сценарий
Пользователь меняет риск-профиль с "Balanced" на "Aggressive". Проверить что все параметры обновились.

### E2E Тест

```typescript
test('должен применить все параметры Aggressive профиля', async ({ page, request }) => {
  await page.goto('/');
  await login(page);
  await goToSettings(page);
  
  // Получаем начальное состояние
  const initialConfig = await getEffectiveConfig(request);
  
  // Меняем профиль на Aggressive
  await page.selectOption('[data-testid="settings-risk-profile"]', 'Aggressive');
  
  // Ожидаем что UI автоматически обновил advanced settings
  // (если есть JS логика которая делает это)
  await page.waitForTimeout(500);
  
  // Сохраняем
  await saveSettings(page);
  
  // Проверяем что конфиг обновился
  const config = await getEffectiveConfig(request);
  
  // Aggressive профиль должен иметь:
  const expectedAggressive = {
    high_vol_event_atr_pct: 10.0,
    max_atr_pct: 20.0,
    max_spread_pct: 1.0,
    mtf_score_threshold: 0.5,
  };
  
  const actualConfig = config.data.config;
  
  expect(actualConfig.meta_layer.high_vol_event_atr_pct).toBe(expectedAggressive.high_vol_event_atr_pct);
  expect(actualConfig.no_trade_zone.max_atr_pct).toBe(expectedAggressive.max_atr_pct);
  expect(actualConfig.no_trade_zone.max_spread_pct).toBe(expectedAggressive.max_spread_pct);
  expect(actualConfig.meta_layer.mtf_score_threshold).toBe(expectedAggressive.mtf_score_threshold);
  
  console.log('✅ Все параметры Aggressive профиля применены');
  
  // Проверяем что бот использует эти параметры в торговле
  await startBot(request);
  await runBotOnce(request);
  
  const intent = await getLastOrderIntent(request);
  if (intent.data) {
    // MTF threshold должен быть из Aggressive профиля
    expect(intent.data.mtf_score).toBeGreaterThanOrEqual(expectedAggressive.mtf_score_threshold);
  }
  
  await stopBot(request);
});
```

---

## Пример 6: Использование helpers для чистого кода

### Используя helpers.ts

```typescript
import { test, expect } from '@playwright/test';
import {
  login,
  goToSettings,
  setBasicRiskSettings,
  setAdvancedSettings,
  saveSettings,
  getEffectiveConfig,
  startBot,
  stopBot,
  runBotOnce,
} from './helpers';

test('компактный тест с helpers', async ({ page, request }) => {
  // Setup
  await page.goto('/');
  await login(page);
  await goToSettings(page);
  
  // Act
  await setBasicRiskSettings(page, {
    positionRisk: 3.0,
    maxPositions: 5,
    slPercent: 1.5,
    tpPercent: 3.0,
  });
  
  await setAdvancedSettings(page, {
    highVolAtr: 8.0,
    noTradeMaxAtr: 16.0,
    useMtf: true,
    mtfThreshold: 0.7,
  });
  
  await saveSettings(page);
  
  // Assert
  const config = await getEffectiveConfig(request);
  
  expect(config.data.config.risk_management.position_risk_percent).toBe(3.0);
  expect(config.data.config.meta_layer.mtf_score_threshold).toBe(0.7);
  
  // Test bot behavior
  await startBot(request);
  const result = await runBotOnce(request);
  
  console.log('Bot result:', result.status);
  
  await stopBot(request);
});
```

---

## Полезные паттерны

### Pattern 1: Проверка математики SL/TP

```typescript
function assertSlTpMath(intent: OrderIntent, expectedSlMult: number, expectedTpMult: number) {
  const price = parseFloat(intent.price);
  const sl = parseFloat(intent.stop_loss);
  const tp = parseFloat(intent.take_profit);
  const atr = intent.atr_value;
  
  const slDistance = Math.abs(price - sl);
  const tpDistance = Math.abs(price - tp);
  
  expect(slDistance).toBeCloseTo(atr * expectedSlMult, 1);
  expect(tpDistance).toBeCloseTo(atr * expectedTpMult, 1);
  
  return { slDistance, tpDistance };
}

// Использование
const intent = await getLastOrderIntent(request);
const { slDistance, tpDistance } = assertSlTpMath(intent.data, 1.8, 2.6);
console.log(`SL: ${slDistance}, TP: ${tpDistance}`);
```

### Pattern 2: Ожидание изменения версии

```typescript
async function waitForConfigUpdate(request, initialVersion, timeout = 5000) {
  const start = Date.now();
  
  while (Date.now() - start < timeout) {
    const config = await getEffectiveConfig(request);
    if (config.data.config_version > initialVersion) {
      return config;
    }
    await new Promise(r => setTimeout(r, 500));
  }
  
  throw new Error('Config version did not update');
}

// Использование
const initial = await getEffectiveConfig(request);
await saveSettings(page);
const updated = await waitForConfigUpdate(request, initial.data.config_version);
```

### Pattern 3: Проверка нескольких тиков подряд

```typescript
async function runMultipleTicks(request, count: number) {
  const results = [];
  
  for (let i = 0; i < count; i++) {
    const result = await runBotOnce(request);
    results.push(result);
    await new Promise(r => setTimeout(r, 1000)); // Cooldown между тиками
  }
  
  return results;
}

// Использование
const results = await runMultipleTicks(request, 5);
const successfulIntents = results.filter(r => r.status === 'success');
console.log(`Generated ${successfulIntents.length}/5 intents`);
```

---

## Debugging Tips

### 1. Сделать screenshot в произвольном месте
```typescript
await page.screenshot({ path: 'debug-screenshot.png' });
```

### 2. Остановить выполнение для инспекции
```typescript
await page.pause();  // Откроет Playwright Inspector
```

### 3. Вывести состояние конфига
```typescript
console.log('Config:', JSON.stringify(config, null, 2));
```

### 4. Проверить network запросы
```typescript
page.on('response', response => {
  if (response.url().includes('/api/')) {
    console.log(`API: ${response.status()} ${response.url()}`);
  }
});
```

---

Эти примеры покрывают типичные сценарии E2E тестирования настроек бота. 🚀
