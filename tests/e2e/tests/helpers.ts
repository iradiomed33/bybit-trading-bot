/**
 * Helper utilities for E2E tests
 */

import { Page, APIRequestContext } from '@playwright/test';

/**
 * Login to the application
 */
export async function login(page: Page, username = 'admin', password = 'admin123') {
  // Очищаем storage чтобы гарантировать свежую сессию
  await page.context().clearCookies();
  await page.evaluate(() => localStorage.clear());
  
  // Переходим на главную страницу
  await page.goto('/');
  
  // Проверяем, редиректнуло ли на login
  const currentUrl = page.url();
  if (currentUrl.includes('login.html')) {
    // Ждем загрузки формы логина
    await page.waitForSelector('input[name="username"]', { timeout: 5000 });
    
    // Запол няем форму
    await page.fill('input[name="username"]', username);
    await page.fill('input[name="password"]', password);
    
    // Нажимаем Sign In (force: true чтобы обойти анимацию кнопки)
    await page.click('button[type="submit"]', { force: true });
    
    // Ждем редиректа на главную страницу
    await page.waitForURL('/', { timeout: 10000 });
  }
  
  // Убеждаемся что мы на главной странице
  await page.waitForSelector('[data-tab="settings"]', { timeout: 5000 });
}

/**
 * Navigate to Settings tab
 */
export async function goToSettings(page: Page) {
  await page.click('[data-tab="settings"]');
  await page.waitForSelector('[data-testid="settings-save-button"]', { timeout: 5000 });
}

/**
 * Open Advanced Settings section
 */
export async function openAdvancedSettings(page: Page) {
  const advancedSection = page.locator('[data-testid="settings-advanced-high-vol-atr"]');
  const isVisible = await advancedSection.isVisible({ timeout: 500 }).catch(() => false);
  
  if (!isVisible) {
    await page.click('text=Расширенные настройки');
    await page.waitForSelector('[data-testid="settings-advanced-high-vol-atr"]', { timeout: 2000 });
  }
}

/**
 * Save settings and wait for confirmation
 */
export async function saveSettings(page: Page, waitMs = 1000) {
  await page.click('[data-testid="settings-save-button"]');
  await page.waitForTimeout(waitMs);
}

/**
 * Get effective config from API
 */
export async function getEffectiveConfig(request: APIRequestContext) {
  const response = await request.get('/api/bot/effective-config');
  if (!response.ok()) {
    throw new Error(`Failed to get effective config: ${response.status()}`);
  }
  return await response.json();
}

/**
 * Get last order intent from API
 */
export async function getLastOrderIntent(request: APIRequestContext) {
  const response = await request.get('/api/bot/last-order-intent');
  if (!response.ok()) {
    throw new Error(`Failed to get order intent: ${response.status()}`);
  }
  return await response.json();
}

/**
 * Start the bot
 */
export async function startBot(request: APIRequestContext) {
  const response = await request.post('/api/bot/start');
  const data = await response.json();
  
  if (data.status === 'already_running') {
    console.log('ℹ️  Bot already running');
    return true;
  }
  
  if (!response.ok()) {
    throw new Error(`Failed to start bot: ${response.status()}`);
  }
  
  return true;
}

/**
 * Stop the bot
 */
export async function stopBot(request: APIRequestContext) {
  const response = await request.post('/api/bot/stop');
  if (!response.ok()) {
    console.warn(`Failed to stop bot: ${response.status()}`);
  }
}

/**
 * Run one bot tick in dry-run mode
 */
export async function runBotOnce(request: APIRequestContext) {
  const response = await request.post('/api/bot/run-once');
  if (!response.ok()) {
    throw new Error(`Failed to run bot once: ${response.status()}`);
  }
  return await response.json();
}

/**
 * Wait for config version to change
 */
export async function waitForConfigVersionChange(
  request: APIRequestContext,
  initialVersion: number,
  maxWaitMs = 5000
): Promise<number> {
  const startTime = Date.now();
  
  while (Date.now() - startTime < maxWaitMs) {
    const config = await getEffectiveConfig(request);
    const currentVersion = config.data.config_version;
    
    if (currentVersion > initialVersion) {
      return currentVersion;
    }
    
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  
  throw new Error(`Config version did not change within ${maxWaitMs}ms`);
}

/**
 * Reset settings to defaults
 */
export async function resetSettings(page: Page) {
  await page.click('[data-testid="settings-reset-button"]');
  await page.waitForTimeout(1000);
}

/**
 * Set basic risk settings
 */
export async function setBasicRiskSettings(
  page: Page,
  settings: {
    positionRisk?: number;
    maxPositions?: number;
    maxNotional?: number;
    slPercent?: number;
    tpPercent?: number;
  }
) {
  if (settings.positionRisk !== undefined) {
    await page.fill('[data-testid="settings-risk-position-risk"]', settings.positionRisk.toString());
  }
  if (settings.maxPositions !== undefined) {
    await page.fill('[data-testid="settings-risk-max-positions"]', settings.maxPositions.toString());
  }
  if (settings.maxNotional !== undefined) {
    await page.fill('[data-testid="settings-risk-max-notional"]', settings.maxNotional.toString());
  }
  if (settings.slPercent !== undefined) {
    await page.fill('[data-testid="settings-sl-percent"]', settings.slPercent.toString());
  }
  if (settings.tpPercent !== undefined) {
    await page.fill('[data-testid="settings-tp-percent"]', settings.tpPercent.toString());
  }
}

/**
 * Set advanced settings
 */
export async function setAdvancedSettings(
  page: Page,
  settings: {
    highVolAtr?: number;
    noTradeMaxAtr?: number;
    noTradeMaxSpread?: number;
    useMtf?: boolean;
    mtfThreshold?: number;
  }
) {
  await openAdvancedSettings(page);
  
  if (settings.highVolAtr !== undefined) {
    await page.fill('[data-testid="settings-advanced-high-vol-atr"]', settings.highVolAtr.toString());
  }
  if (settings.noTradeMaxAtr !== undefined) {
    await page.fill('[data-testid="settings-advanced-no-trade-max-atr"]', settings.noTradeMaxAtr.toString());
  }
  if (settings.noTradeMaxSpread !== undefined) {
    await page.fill('[data-testid="settings-advanced-no-trade-max-spread"]', settings.noTradeMaxSpread.toString());
  }
  if (settings.useMtf !== undefined) {
    const mtfCheckbox = page.locator('[data-testid="settings-advanced-use-mtf"]');
    if (settings.useMtf) {
      await mtfCheckbox.check();
    } else {
      await mtfCheckbox.uncheck();
    }
  }
  if (settings.mtfThreshold !== undefined) {
    await page.fill('[data-testid="settings-advanced-mtf-threshold"]', settings.mtfThreshold.toString());
  }
}
