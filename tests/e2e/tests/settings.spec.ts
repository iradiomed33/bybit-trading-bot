/**
 * TASK-QA-UI-SETTINGS-001: TC1 - Basic settings влияют на runtime config (P0)
 * 
 * Проверяет что:
 * 1. Настройки UI корректно сохраняются
 * 2. API отдаёт сохранённые значения
 * 3. effective-config отражает эти значения
 * 4. config_version обновляется
 */

import { test, expect } from '@playwright/test';

test.describe('TC1: Basic Settings → Runtime Config', () => {
  test.beforeEach(async ({ page }) => {
    // Переходим на страницу (возможен редирект на login)
    await page.goto('/');
    
    // Очищаем storage только если мы на валидной странице
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
    
    // Переходим на вкладку Settings
    await page.waitForSelector('[data-tab="settings"]');
    await page.click('[data-tab="settings"]');
    await page.waitForSelector('[data-testid="settings-save-button"]', { timeout: 5000 });
  });

  test('должен сохранить и применить базовые настройки риска', async ({ page }) => {
    // === ARRANGE ===
    const testValues = {
      position_risk_percent: 2.5,
      max_positions: 5,
      max_total_notional: 75000,
    };

    // Получаем текущую версию конфига
    const initialConfigResponse = await page.request.get('/api/bot/effective-config');
    expect(initialConfigResponse.ok()).toBeTruthy();
    const initialConfig = await initialConfigResponse.json();
    const initialVersion = initialConfig.data.config_version;

    // === ACT ===
    // Изменяем базовые настройки в UI
    await page.fill('[data-testid="settings-risk-position-risk"]', testValues.position_risk_percent.toString());
    await page.fill('[data-testid="settings-risk-max-positions"]', testValues.max_positions.toString());
    await page.fill('[data-testid="settings-risk-max-notional"]', testValues.max_total_notional.toString());

    // Сохраняем
    await page.click('[data-testid="settings-save-button"]');

    // Ждём успешного сохранения (можно через toast или timeout)
    await page.waitForTimeout(1000);

    // === ASSERT ===
    // 1. API GET /api/settings отдаёт сохранённые значения
    const settingsResponse = await page.request.get('/api/config/risk_management');
    expect(settingsResponse.ok()).toBeTruthy();
    const settings = await settingsResponse.json();
    
    expect(settings.data.position_risk_percent).toBe(testValues.position_risk_percent);
    expect(settings.data.max_position_size).toBeDefined(); // Другое поле, но должно быть

    // 2. GET /api/bot/effective-config отражает эти значения
    const effectiveConfigResponse = await page.request.get('/api/bot/effective-config');
    expect(effectiveConfigResponse.ok()).toBeTruthy();
    const effectiveConfig = await effectiveConfigResponse.json();
    
    expect(effectiveConfig.data.config.risk_management.position_risk_percent).toBe(testValues.position_risk_percent);

    // 3. config_version обновился
    expect(effectiveConfig.data.config_version).toBeGreaterThan(initialVersion);
    
    // 4. updated_at обновился
    expect(effectiveConfig.data.updated_at).toBeDefined();
    
    console.log('✅ TC1 PASSED: Basic settings correctly persisted and applied');
    console.log(`   Version: ${initialVersion} → ${effectiveConfig.data.config_version}`);
    console.log(`   Risk: ${testValues.position_risk_percent}%`);
  });

  test('должен сохранить и применить настройки SL/TP', async ({ page }) => {
    // === ARRANGE ===
    const testValues = {
      stop_loss_percent: 1.2,
      take_profit_percent: 2.4,
    };

    // === ACT ===
    await page.fill('[data-testid="settings-sl-percent"]', testValues.stop_loss_percent.toString());
    await page.fill('[data-testid="settings-tp-percent"]', testValues.take_profit_percent.toString());
    
    await page.click('[data-testid="settings-save-button"]');
    await page.waitForTimeout(1000);

    // === ASSERT ===
    const effectiveConfigResponse = await page.request.get('/api/bot/effective-config');
    expect(effectiveConfigResponse.ok()).toBeTruthy();
    const effectiveConfig = await effectiveConfigResponse.json();
    
    expect(effectiveConfig.data.config.risk_management.stop_loss_percent).toBe(testValues.stop_loss_percent);
    expect(effectiveConfig.data.config.risk_management.take_profit_percent).toBe(testValues.take_profit_percent);
    
    console.log('✅ SL/TP settings correctly persisted');
  });
});
