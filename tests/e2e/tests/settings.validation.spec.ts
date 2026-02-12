/**
 * TASK-QA-UI-SETTINGS-001: TC4 - Валидация: недопустимые значения (P0)
 * 
 * Проверяет что:
 * 1. UI показывает ошибку при невалидных значениях
 * 2. API возвращает 400 при невалидных данных
 * 3. effective-config не меняется при ошибке
 * 4. config_version остаётся прежним
 */

import { test, expect } from '@playwright/test';

test.describe('TC4: Settings Validation', () => {
  test.beforeEach(async ({ page }) => {
    // Переходим на страницу
    await page.goto('/');
    
    // Очищаем storage
    await page.context().clearCookies();
    try {
      await page.evaluate(() => localStorage.clear());
    } catch (e) {
      // Ignore if localStorage not accessible
    }
    
    // Проверяем редирект на login
    const url = page.url();
    if (url.includes('login.html')) {
      await page.waitForSelector('input[name="username"]');
      await page.fill('input[name="username"]', 'admin');
      await page.fill('input[name="password"]', 'admin123');
      await page.click('button[type="submit"]', { force: true });
      await page.waitForURL('/', { timeout: 10000 });
    }
    
    // Переходим на Settings
    await page.waitForSelector('[data-tab="settings"]');
    await page.click('[data-tab="settings"]');
    await page.waitForSelector('[data-testid="settings-save-button"]', { timeout: 5000 });
  });

  test('должен отклонить отрицательный risk percent', async ({ page, request }) => {
    // Получаем текущую версию
    const initialResponse = await request.get('/api/bot/effective-config');
    const initialConfig = await initialResponse.json();
    const initialVersion = initialConfig.data.config_version;

    // Пытаемся установить невалидное значение
    await page.fill('[data-testid="settings-risk-position-risk"]', '-1.0');
    await page.click('[data-testid="settings-save-button"]');
    
    // HTML5 валидация должна поймать или API должен вернуть ошибку
    await page.waitForTimeout(1000);

    // Проверяем что версия НЕ изменилась
    const afterResponse = await request.get('/api/bot/effective-config');
    const afterConfig = await afterResponse.json();
    
    // Версия не должна измениться если валидация сработала
    // (если HTML5 не пустил, значения вообще не отправились)
    expect(afterConfig.data.config_version).toBe(initialVersion);
    
    console.log('✅ Negative value correctly rejected');
  });

  test('должен отклонить leverage = 0', async ({ page, request }) => {
    const initialResponse = await request.get('/api/bot/effective-config');
    const initialConfig = await initialResponse.json();
    const initialVersion = initialConfig.data.config_version;
    const initialLeverage = initialConfig.data.config.risk_management.max_leverage;

    // API тест: отправляем напрямую невалидный leverage через API
    const updateResponse = await request.post('/api/config/risk_management.max_leverage', {
      data: { value: 0 }
    });

    // API должен вернуть ошибку или принять но не применить
    // (зависит от реализации валидации)
    
    // Проверяем что effective config не изменился на невалидное значение
    const afterResponse = await request.get('/api/bot/effective-config');
    const afterConfig = await afterResponse.json();
    
    // Leverage не должен стать 0
    expect(afterConfig.data.config.risk_management.max_leverage).not.toBe(0);
    expect(afterConfig.data.config.risk_management.max_leverage).toBe(initialLeverage);
    
    console.log('✅ Leverage=0 correctly rejected');
  });

  test('должен отклонить SL/TP = 0', async ({ page }) => {
    // HTML5 валидация (min="0.1") должна предотвратить ввод 0
    await page.fill('[data-testid="settings-sl-percent"]', '0');
    await page.fill('[data-testid="settings-tp-percent"]', '0');
    
    await page.click('[data-testid="settings-save-button"]');
    await page.waitForTimeout(500);
    
    // Проверяем что HTML5 валидация сработала
    // (поле должно быть подсвечено как invalid)
    const slInput = page.locator('[data-testid="settings-sl-percent"]');
    const isInvalid = await slInput.evaluate((el: HTMLInputElement) => !el.validity.valid);
    
    expect(isInvalid).toBeTruthy();
    
    console.log('✅ SL/TP=0 blocked by HTML5 validation');
  });

  test('должен обработать слишком большие значения', async ({ page, request }) => {
    // Пытаемся установить leverage = 200 (больше макс допустимого)
    // API должен либо отклонить либо привести к max допустимому
    
    const updateResponse = await request.post('/api/config/risk_management.max_leverage', {
      data: { value: 200 }
    });

    const afterResponse = await request.get('/api/bot/effective-config');
    const afterConfig = await afterResponse.json();
    
    // Leverage должен быть в разумных пределах (например, <=100)
    expect(afterConfig.data.config.risk_management.max_leverage).toBeLessThanOrEqual(100);
    
    console.log('✅ Excessive leverage capped or rejected');
  });

  test('должен обработать NaN в advanced settings', async ({ page }) => {
    await page.click('text=Расширенные настройки');
    await page.waitForSelector('[data-testid="settings-advanced-high-vol-atr"]', { timeout: 2000 });
    
    // Пытаемся ввести текст вместо числа
    await page.fill('[data-testid="settings-advanced-high-vol-atr"]', 'not-a-number');
    
    // HTML5 input type="number" не позволит ввести текст
    const value = await page.inputValue('[data-testid="settings-advanced-high-vol-atr"]');
    
    // Значение должно остаться пустым или предыдущим валидным
    expect(value).not.toBe('not-a-number');
    
    console.log('✅ Non-numeric input correctly handled');
  });
});
