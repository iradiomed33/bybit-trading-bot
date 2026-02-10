// API Configuration
const API_BASE = window.location.origin + '/api';
const WS_URL = window.location.origin.replace('http', 'ws') + '/ws';
const API_URL = window.location.origin;
const TOKEN_KEY = 'auth_token';
const USERNAME_KEY = 'auth_username';

// Global state
let ws = null;
let config = {};
let isConnected = false;
let botIsRunning = false;
let currentUsername = null;
let advancedTouched = false; // Track if user manually edited advanced settings

// Risk Profile Presets
const RISK_PROFILES = {
    'Conservative': {
        high_vol_event_atr_pct: 5.0,
        max_atr_pct: 10.0,
        max_spread_pct: 0.30,
        orderbook_sanity_max_deviation_pct: 2.0,
        use_mtf: true,
        mtf_score_threshold: 0.75
    },
    'Balanced': {
        high_vol_event_atr_pct: 7.0,
        max_atr_pct: 14.0,
        max_spread_pct: 0.50,
        orderbook_sanity_max_deviation_pct: 3.0,
        use_mtf: true,
        mtf_score_threshold: 0.65
    },
    'Aggressive': {
        high_vol_event_atr_pct: 9.0,
        max_atr_pct: 18.0,
        max_spread_pct: 0.80,
        orderbook_sanity_max_deviation_pct: 5.0,
        use_mtf: false,
        mtf_score_threshold: 0.55
    }
};

// DOM Elements (declared globally so they can be used in any function)
let connectionStatus = null;
let currentTimeEl = null;
let tabButtons = null;
let tabContents = null;

// ============================================================================
// AUTHENTICATION FUNCTIONS
// ============================================================================

/**
 * Получить сохраненный токен
 */
function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

/**
 * Получить имя пользователя
 */
function getCurrentUsername() {
    return localStorage.getItem(USERNAME_KEY);
}

/**
 * Проверить, авторизован ли пользователь
 */
async function checkAuth() {
    const token = getToken();
    console.log('[AUTH] Checking auth, token exists:', !!token);
    
    if (!token) {
        // Нет токена, редирект на логин
        console.log('[AUTH] No token found, redirecting to login');
        redirectToLogin('Session expired. Please log in again.');
        return false;
    }

    try {
        // Проверить токен на сервере
        console.log('[AUTH] Verifying token with server...');
        const response = await fetch(`${API_URL}/api/auth/verify`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
            },
        });

        const data = await response.json();
        console.log('[AUTH] Verify response:', data);

        if (!data.valid) {
            // Токен невалиден
            console.log('[AUTH] Token is invalid, redirecting to login');
            clearAuthToken();
            redirectToLogin('Session expired. Please log in again.');
            return false;
        }

        // Токен действителен
        console.log('[AUTH] Token is valid for user:', data.username);
        currentUsername = data.username;
        updateUserInfo();
        return true;

    } catch (error) {
        console.error('[AUTH] Auth check error:', error);
        // При ошибке оставить пользователя на месте, но логировать
        return true;
    }
}

/**
 * Очистить токен авторизации
 */
function clearAuthToken() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USERNAME_KEY);
}

/**
 * Редирект на страницу входа
 */
function redirectToLogin(message = '') {
    clearAuthToken();
    if (message) {
        sessionStorage.setItem('loginMessage', message);
    }
    window.location.href = '/static/login.html';
}

/**
 * Выход из системы
 */
async function logout() {
    try {
        const token = getToken();
        if (token) {
            await fetch(`${API_URL}/api/auth/logout`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            });
        }
    } catch (error) {
        console.error('Logout error:', error);
    } finally {
        clearAuthToken();
        redirectToLogin('You have been logged out.');
    }
}

/**
 * Обновить информацию о пользователе в UI
 */
function updateUserInfo() {
    const username = getCurrentUsername();
    const userInfo = document.getElementById('userInfo');
    const logoutBtn = document.getElementById('logoutBtn');

    if (username && userInfo) {
        userInfo.innerHTML = `<i class="bi bi-person-circle"></i> ${username}`;
    }
    if (logoutBtn) {
        logoutBtn.style.display = 'inline-block';
    }
}

// ============================================================================
// BOT CONTROL FUNCTIONS
// ============================================================================
async function startBot() {
    try {
        const response = await fetch(`${API_BASE}/bot/start`, { method: 'POST' });
        const data = await response.json();
        
        if (response.ok) {
            botIsRunning = true;
            updateBotControlButtons();
            showBotStatusMessage('🚀 Bot started successfully!', 'success');
        } else {
            showBotStatusMessage(`Error: ${data.message}`, 'danger');
        }
    } catch (error) {
        console.error('Error starting bot:', error);
        showBotStatusMessage('Failed to start bot', 'danger');
    }
}

async function stopBot() {
    try {
        const response = await fetch(`${API_BASE}/bot/stop`, { method: 'POST' });
        const data = await response.json();
        
        if (response.ok) {
            botIsRunning = false;
            updateBotControlButtons();
            showBotStatusMessage('🛑 Bot stopped successfully!', 'warning');
        } else {
            showBotStatusMessage(`Error: ${data.message}`, 'danger');
        }
    } catch (error) {
        console.error('Error stopping bot:', error);
        showBotStatusMessage('Failed to stop bot', 'danger');
    }
}

function updateBotControlButtons() {
    const startBtn = document.getElementById('startBotBtn');
    const stopBtn = document.getElementById('stopBotBtn');
    const statusBadge = document.getElementById('botStatus');
    
    if (botIsRunning) {
        startBtn.disabled = true;
        stopBtn.disabled = false;
        statusBadge.textContent = 'Running';
        statusBadge.className = 'badge bg-success';
    } else {
        startBtn.disabled = false;
        stopBtn.disabled = true;
        statusBadge.textContent = 'Stopped';
        statusBadge.className = 'badge bg-warning';
    }
}

function showBotStatusMessage(message, type) {
    const messageEl = document.getElementById('botStatusMessage');
    if (messageEl) {
        messageEl.innerHTML = `<div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>`;
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            if (messageEl.firstChild) {
                messageEl.firstChild.remove();
            }
        }, 5000);
    }
}

async function checkBotStatus() {
    try {
        const response = await fetch(`${API_BASE}/bot/status`);
        const data = await response.json();
        botIsRunning = data.is_running;
        updateBotControlButtons();
    } catch (error) {
        console.error('Error checking bot status:', error);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    try {
        console.log('[DOMContentLoaded] Starting initialization...');
        
        // Проверить авторизацию ДО загрузки остального
        console.log('[DOMContentLoaded] Checking authentication...');
        const isAuthenticated = await checkAuth();
        if (!isAuthenticated) {
            console.log('[DOMContentLoaded] Not authenticated, stopping initialization');
            return; // checkAuth сделает редирект
        }

        console.log('[DOMContentLoaded] Authenticated, proceeding...');

        // Получить переменные DOM после проверки авторизации
        connectionStatus = document.getElementById('connectionStatus');
        currentTimeEl = document.getElementById('currentTime');
        tabButtons = document.querySelectorAll('[data-tab]');
        tabContents = document.querySelectorAll('.tab-content');

        // Обновить информацию о пользователе
        updateUserInfo();

        // Запустить остальную инициализацию
        console.log('[DOMContentLoaded] Checking bot status...');
        checkBotStatus();
        
        console.log('[DOMContentLoaded] Initializing event listeners...');
        initEventListeners();
        
        console.log('[DOMContentLoaded] Loading initial data...');
        await loadInitialData();
        
        console.log('[DOMContentLoaded] Connecting WebSocket...');
        connectWebSocket();
        
        console.log('[DOMContentLoaded] Updating time...');
        updateTime();
        setInterval(updateTime, 1000);
        
        console.log('[DOMContentLoaded] Initialization complete!');
    } catch (error) {
        console.error('[DOMContentLoaded] Fatal error during initialization:', error);
        showNotification('Fatal error during initialization: ' + error.message, 'danger');
    }
});

// Event Listeners
function initEventListeners() {
    // Tab navigation
    tabButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            const tabName = e.currentTarget.dataset.tab;
            switchTab(tabName);
        });
    });

    // Settings
    document.getElementById('savSettingsBtn').addEventListener('click', saveSettings);
    document.getElementById('resetSettingsBtn').addEventListener('click', resetSettings);
    
    // Risk profile change handler
    document.getElementById('settingRiskProfile').addEventListener('change', onRiskProfileChange);
    
    // Reset to profile button
    document.getElementById('resetToProfileBtn').addEventListener('click', resetToProfile);
    
    // Track advanced settings changes
    const advancedInputs = document.querySelectorAll('.advanced-input');
    advancedInputs.forEach(input => {
        input.addEventListener('change', () => {
            advancedTouched = true;
        });
    });
}

// Tab switching
function switchTab(tabName) {
    // Hide all tabs
    tabContents.forEach(tab => {
        tab.classList.remove('active');
        tab.style.display = 'none';
    });

    // Remove active from buttons
    tabButtons.forEach(btn => btn.classList.remove('active'));

    // Show selected tab
    const tabElement = document.getElementById(tabName);
    if (tabElement) {
        tabElement.classList.add('active');
        tabElement.style.display = 'block';
    }

    // Mark button as active
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

    // Load data for specific tabs
    if (tabName === 'history') {
        loadTradeHistory();
    } else if (tabName === 'account') {
        loadAccountInfo();
    } else if (tabName === 'settings') {
        loadSettings();
    }
}

// API Functions
async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const token = getToken();
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            }
        };

        // Добавить токен в заголовок если существует
        if (token) {
            options.headers['Authorization'] = `Bearer ${token}`;
        }

        if (data && method !== 'GET') {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(`${API_BASE}${endpoint}`, options);
        const result = await response.json();

        if (!response.ok) {
            console.error('API Error:', result);
            
            // Если ошибка авторизации - редирект на логин
            if (response.status === 401) {
                console.warn('[apiCall] Got 401 Unauthorized, redirecting to login');
                redirectToLogin('Session expired. Please log in again.');
                return null;
            }
            
            showNotification('Ошибка API: ' + (result.detail || 'Неизвестная ошибка'), 'danger');
            return null;
        }

        return result.data || result;
    } catch (error) {
        console.error('[apiCall] Error:', error);
        showNotification('Ошибка подключения: ' + error.message, 'danger');
        return null;
    }
}

// WebSocket Connection
function connectWebSocket() {
    try {
        ws = new WebSocket(WS_URL);

        ws.onopen = () => {
            isConnected = true;
            updateConnectionStatus(true);
            console.log('WebSocket connected');
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            } catch (e) {
                console.error('WebSocket parse error:', e);
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            updateConnectionStatus(false);
        };

        ws.onclose = () => {
            isConnected = false;
            updateConnectionStatus(false);
            console.log('WebSocket disconnected, retrying in 5s...');
            setTimeout(connectWebSocket, 5000);
        };
    } catch (error) {
        console.error('WebSocket connection error:', error);
        updateConnectionStatus(false);
    }
}

// Handle WebSocket messages
function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'initial_balance':
            // Обновить баланс при подключении
            updateBalanceInfo(data.balance);
            break;
        case 'initial_status':
            // Обновить статус при подключении
            updateAccountInfo(data.status);
            break;
        case 'account_balance_updated': {
            // Realtime обновление баланса
            const b = data.balance || {};
            updateBalanceInfo(b);
            const total = parseFloat(b.total_balance || 0).toFixed(2);
            const upnl = parseFloat(b.unrealized_pnl || 0).toFixed(2);
            if (document.getElementById('totalBalance')) {
                document.getElementById('totalBalance').textContent = '$' + total;
            }
            if (document.getElementById('unrealizedPnl')) {
                document.getElementById('unrealizedPnl').textContent = '$' + upnl;
            }
            break;
        }
        case 'positions_updated': {
            // Realtime обновление позиций
            const positions = data.positions || [];
            if (document.getElementById('positionCount')) {
                document.getElementById('positionCount').textContent = (positions.length || 0).toString();
            }
            updatePositionsTable(positions);
            break;
        }
        case 'bot_status_changed':
            // Обновить статус бота
            botIsRunning = data.is_running;
            updateBotControlButtons();
            showBotStatusMessage(data.message, data.is_running ? 'success' : 'warning');
            break;
        case 'config_updated':
            if (data.config) config = data.config;
            updateDashboardFromConfig();
            break;
        case 'trade_executed':
            showNotification(`Сделка исполнена: ${data.trade.symbol}`, 'success');
            loadTradeHistory();
            break;
        case 'position_updated':
            loadAccountInfo();
            break;
        case 'log':
            // Добавить WebSocket лог в контейнер в реальном времени
            addLiveLog(data);
            break;
        default:
            console.log('Unknown message type:', data.type);
    }
}

// Update UI
function updateConnectionStatus(connected) {
    const statusEl = document.querySelector('#connectionStatus .badge');
    if (connected) {
        statusEl.className = 'badge bg-success';
        statusEl.textContent = 'Online';
        statusEl.parentElement.classList.add('connection-online');
    } else {
        statusEl.className = 'badge bg-danger';
        statusEl.textContent = 'Offline';
        statusEl.parentElement.classList.remove('connection-online');
    }
    
    // Bot status badge should reflect actual bot running state, not WebSocket connection
    // It's updated by checkBotStatus() and updateBotControlButtons()
}

function updateTime() {
    const now = new Date();
    currentTimeEl.textContent = now.toLocaleTimeString('ru-RU');
}

function showNotification(message, type = 'info') {
    const alertClass = `alert-${type}`;
    const alertEl = document.createElement('div');
    alertEl.className = `alert ${alertClass} alert-dismissible fade show`;
    alertEl.role = 'alert';
    alertEl.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Insert after navbar
    document.querySelector('.navbar').insertAdjacentElement('afterend', alertEl);
    
    // Auto dismiss after 5 seconds
    setTimeout(() => {
        alertEl.remove();
    }, 5000);
}

// Load initial data
async function loadInitialData() {
    try {
        console.log('[loadInitialData] Starting to load initial data...');
        
        // Load config
        console.log('[loadInitialData] Loading config...');
        const configData = await apiCall('/config');
        if (configData) {
            console.log('[loadInitialData] Config loaded:', configData);
            config = configData;
            updateDashboardFromConfig();
        } else {
            console.warn('[loadInitialData] No config data returned');
        }

        // Load account info
        console.log('[loadInitialData] Loading account info...');
        await loadAccountInfo();
        console.log('[loadInitialData] Account info loaded');
        
        // Load signal logs
        console.log('[loadInitialData] Loading signal logs...');
        await loadSignalLogs();
        console.log('[loadInitialData] Signal logs loaded');
        
        // Start auto-reload of signal logs every 5 seconds
        setInterval(() => {
            loadSignalLogs().catch(err => console.debug('[autoReload] Signal logs error:', err));
        }, 5000);
        
    } catch (error) {
        console.error('[loadInitialData] Error:', error);
    }
}

// Update dashboard from config
function updateDashboardFromConfig() {
    // Protect against undefined config (WebSocket messages may arrive before config loads)
    if (!config) {
        console.warn('[updateDashboardFromConfig] Config not loaded yet, ignoring update');
        return;
    }
    
    document.getElementById('botMode').textContent = config.trading?.mode || '-';
    
    // Display all trading pairs
    const symbols = config.trading?.symbols || [];
    const symbolDisplay = symbols.length > 0 ? symbols.join(', ') : (config.trading?.symbol || '-');
    document.getElementById('botSymbol').textContent = symbolDisplay;
    
    document.getElementById('riskPercent').textContent = (config.risk_management?.position_risk_percent || 0) + '%';
// Не перетираем реальный running state.
// Статус бота управляется через /api/bot/status и updateBotControlButtons().
updateBotControlButtons();

console.log('[updateDashboardFromConfig] Updated with symbols:', symbols);
}

// Load settings form
async function loadSettings() {
    const configData = await apiCall('/config');
    if (!configData) return;

    // Load symbols
    const symbols = configData.trading?.symbols || [];
    if (symbols.length > 0) {
        document.getElementById('settingSymbols').value = symbols.join(', ');
    } else if (configData.trading?.symbol) {
        // Fallback: if no symbols array, use single symbol
        document.getElementById('settingSymbols').value = configData.trading.symbol;
    }
    
    // Load basic settings
    document.getElementById('settingTimeframe').value = configData.market_data?.kline_interval || '60';
    document.getElementById('settingMode').value = configData.trading?.mode || 'paper';
    document.getElementById('settingMaxPositions').value = configData.risk_monitor?.max_positions || 3;
    document.getElementById('settingMaxTotalNotional').value = configData.risk_monitor?.max_total_notional || 100000;
    document.getElementById('settingRiskProfile').value = configData.meta_layer?.risk_profile || 'Balanced';
    
    // Load execution settings
    document.getElementById('settingOrderType').value = configData.execution?.order_type || 'limit';
    document.getElementById('settingTimeInForce').value = configData.execution?.time_in_force || 'GTC';
    document.getElementById('settingPostOnly').checked = configData.execution?.post_only || false;
    
    // Load kill-switch settings
    document.getElementById('settingDailyLossLimit').value = configData.risk_management?.daily_loss_limit_percent || 5.0;
    document.getElementById('settingMaxConsecErrors').value = configData.kill_switch?.max_consecutive_errors || 5;
    document.getElementById('settingCooldownMinutes').value = configData.kill_switch?.cooldown_minutes || 15;
    
    // Load advanced settings
    document.getElementById('settingHighVolEventAtr').value = configData.meta_layer?.high_vol_event_atr_pct || 7.0;
    document.getElementById('settingNoTradeMaxAtr').value = configData.no_trade_zone?.max_atr_pct || 14.0;
    document.getElementById('settingNoTradeMaxSpread').value = configData.no_trade_zone?.max_spread_pct || 0.50;
    document.getElementById('settingOrderbookSanity').value = configData.market_data?.orderbook_sanity_max_deviation_pct || 3.0;
    document.getElementById('settingUseMTF').checked = configData.meta_layer?.use_mtf || false;
    document.getElementById('settingMtfScoreThreshold').value = configData.meta_layer?.mtf_score_threshold || 0.65;
    
    // Load legacy settings
    document.getElementById('settingStopLoss').value = configData.risk_management?.stop_loss_percent || 2.0;
    document.getElementById('settingTakeProfit').value = configData.risk_management?.take_profit_percent || 5.0;
    
    console.log('[loadSettings] Loaded symbols:', symbols);
    
    // Reset advancedTouched flag after loading
    advancedTouched = false;
}


// Save settings
async function saveSettings() {
    // Parse multiple symbols from comma/space separated input
    const symbolsInput = document.getElementById('settingSymbols').value;
    const symbols = symbolsInput
        .split(/[,\s]+/)  // Split by comma or space
        .map(s => s.trim().toUpperCase())  // Trim and uppercase
        .filter(s => s.length > 0);  // Remove empty strings
    
    const updates = {
        // Trading settings
        'trading.symbols': symbols,
        'trading.symbol': symbols.length > 0 ? symbols[0] : 'BTCUSDT',
        'trading.mode': document.getElementById('settingMode').value,
        
        // Market data settings
        'market_data.kline_interval': document.getElementById('settingTimeframe').value,
        'market_data.orderbook_sanity_max_deviation_pct': parseFloat(document.getElementById('settingOrderbookSanity').value),
        
        // Risk monitor settings
        'risk_monitor.max_positions': parseInt(document.getElementById('settingMaxPositions').value),
        'risk_monitor.max_total_notional': parseFloat(document.getElementById('settingMaxTotalNotional').value),
        
        // Execution settings
        'execution.order_type': document.getElementById('settingOrderType').value,
        'execution.time_in_force': document.getElementById('settingTimeInForce').value,
        'execution.post_only': document.getElementById('settingPostOnly').checked,
        
        // Risk management settings
        'risk_management.daily_loss_limit_percent': parseFloat(document.getElementById('settingDailyLossLimit').value),
        'risk_management.stop_loss_percent': parseFloat(document.getElementById('settingStopLoss').value),
        'risk_management.take_profit_percent': parseFloat(document.getElementById('settingTakeProfit').value),
        
        // Kill-switch settings
        'kill_switch.max_consecutive_errors': parseInt(document.getElementById('settingMaxConsecErrors').value),
        'kill_switch.cooldown_minutes': parseInt(document.getElementById('settingCooldownMinutes').value),
        
        // Meta layer settings
        'meta_layer.risk_profile': document.getElementById('settingRiskProfile').value,
        'meta_layer.high_vol_event_atr_pct': parseFloat(document.getElementById('settingHighVolEventAtr').value),
        'meta_layer.use_mtf': document.getElementById('settingUseMTF').checked,
        'meta_layer.mtf_score_threshold': parseFloat(document.getElementById('settingMtfScoreThreshold').value),
        
        // No-trade zone settings
        'no_trade_zone.max_atr_pct': parseFloat(document.getElementById('settingNoTradeMaxAtr').value),
        'no_trade_zone.max_spread_pct': parseFloat(document.getElementById('settingNoTradeMaxSpread').value),
    };

    console.log('[saveSettings] Saving with symbols:', symbols);
    
    let saved = true;
    for (const [key, value] of Object.entries(updates)) {
        const result = await apiCall(`/config/${key}`, 'POST', { value });
        if (!result) {
            saved = false;
            console.error(`[saveSettings] Failed to save ${key}`);
            break;
        }
    }

    if (saved) {
        showNotification(`Настройки сохранены! Пары: ${symbols.join(', ')}`, 'success');
        config = await apiCall('/config');
        updateDashboardFromConfig();
        
        // Уведомление о перезапуске если бот работает
        if (botIsRunning) {
            showNotification('⚠️ Настройки применятся после перезапуска бота', 'warning');
        }
        
        // Reset advancedTouched flag after save
        advancedTouched = false;
    }
}

// Handle risk profile change
function onRiskProfileChange() {
    const profile = document.getElementById('settingRiskProfile').value;
    
    // Only apply preset if advanced settings haven't been manually touched
    if (!advancedTouched) {
        applyRiskProfile(profile);
    } else {
        showNotification(
            'Расширенные настройки изменены вручную. Нажмите "Сбросить на значения профиля" для применения пресета.',
            'info'
        );
    }
}

// Apply risk profile preset to advanced settings
function applyRiskProfile(profileName) {
    const preset = RISK_PROFILES[profileName];
    if (!preset) {
        console.error('[applyRiskProfile] Unknown profile:', profileName);
        return;
    }
    
    document.getElementById('settingHighVolEventAtr').value = preset.high_vol_event_atr_pct;
    document.getElementById('settingNoTradeMaxAtr').value = preset.max_atr_pct;
    document.getElementById('settingNoTradeMaxSpread').value = preset.max_spread_pct;
    document.getElementById('settingOrderbookSanity').value = preset.orderbook_sanity_max_deviation_pct;
    document.getElementById('settingUseMTF').checked = preset.use_mtf;
    document.getElementById('settingMtfScoreThreshold').value = preset.mtf_score_threshold;
    
    console.log('[applyRiskProfile] Applied preset:', profileName);
}

// Reset advanced settings to current risk profile
function resetToProfile() {
    const profile = document.getElementById('settingRiskProfile').value;
    applyRiskProfile(profile);
    advancedTouched = false;
    showNotification(`Расширенные настройки сброшены на профиль ${profile}`, 'success');
}

// Reset settings
async function resetSettings() {
    if (confirm('Вы уверены? Все настройки будут сброшены на дефолты.')) {
        const result = await apiCall('/config/reset', 'POST');
        if (result) {
            showNotification('Настройки сброшены на дефолты', 'success');
            config = await apiCall('/config');
            updateDashboardFromConfig();
            loadSettings();
        }
    }
}

// Load trade history
async function loadTradeHistory() {
    // Load signals
    const signals = await apiCall('/trading/history');
    if (signals) {
        updateSignalsTable(signals);
        updateSignalStats(signals);
    }

    // Load orders
    const orders = await apiCall('/trading/orders');
    if (orders) {
        updateOrdersTable(orders);
    }

    // Load executions
    const executions = await apiCall('/trading/executions');
    if (executions) {
        updateExecutionsTable(executions);
    }
}

// Update signals table
function updateSignalsTable(signals) {
    const tbody = document.getElementById('signalsTable');
    tbody.innerHTML = '';

    if (!signals || signals.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Нет данных</td></tr>';
        return;
    }

    signals.slice(0, 10).forEach(signal => {
        const badgeClass = signal.signal_type === 'buy' ? 'badge-buy' : 'badge-sell';
        const row = `
            <tr>
                <td>${new Date(signal.created_at).toLocaleString('ru-RU')}</td>
                <td>${signal.strategy || '-'}</td>
                <td>${signal.symbol}</td>
                <td><span class="badge ${badgeClass}">${signal.signal_type.toUpperCase()}</span></td>
                <td>$${parseFloat(signal.entry_price).toFixed(2)}</td>
            </tr>
        `;
        tbody.innerHTML += row;
    });
}

// Update signal stats
function updateSignalStats(signals) {
    const statsEl = document.getElementById('signalStats');
    
    if (!signals || signals.length === 0) {
        statsEl.innerHTML = '<p class="text-muted">Нет данных</p>';
        return;
    }

    const buys = signals.filter(s => s.signal_type === 'buy').length;
    const sells = signals.filter(s => s.signal_type === 'sell').length;
    const strategies = [...new Set(signals.map(s => s.strategy))];

    statsEl.innerHTML = `
        <div class="row">
            <div class="col-6">
                <p><strong>Всего сигналов:</strong> ${signals.length}</p>
                <p><strong>Покупок:</strong> <span class="badge bg-success">${buys}</span></p>
                <p><strong>Продаж:</strong> <span class="badge bg-danger">${sells}</span></p>
            </div>
            <div class="col-6">
                <p><strong>Стратегии:</strong></p>
                <ul class="list-unstyled">
                    ${strategies.map(s => `<li><span class="badge bg-info">${s}</span></li>`).join('')}
                </ul>
            </div>
        </div>
    `;
}

// Update recent signals in dashboard
async function updateRecentSignalsWidget() {
    const signals = await apiCall('/trading/history');
    const container = document.getElementById('recentSignals');

    if (!signals || signals.length === 0) {
        container.innerHTML = '<p class="text-muted">Нет сигналов</p>';
        return;
    }

    let html = '';
    signals.slice(0, 5).forEach(signal => {
        const badgeClass = signal.signal_type === 'buy' ? 'badge-buy' : 'badge-sell';
        html += `
            <div class="mb-2">
                <small class="text-muted">${new Date(signal.created_at).toLocaleTimeString('ru-RU')}</small><br>
                <strong>${signal.symbol}</strong> 
                <span class="badge ${badgeClass} float-end">${signal.signal_type.toUpperCase()}</span>
                <br>
                <small class="text-muted">${signal.strategy}</small>
            </div>
            <hr>
        `;
    });

    container.innerHTML = html;
}

// Update orders table
function updateOrdersTable(orders) {
    const tbody = document.getElementById('ordersTable');
    tbody.innerHTML = '';

    if (!orders || orders.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">Нет ордеров</td></tr>';
        return;
    }

    orders.slice(0, 20).forEach(order => {
        const sideClass = order.side === 'Buy' ? 'text-success' : 'text-danger';
        const row = `
            <tr>
                <td>${order.order_id}</td>
                <td>${order.symbol}</td>
                <td><span class="${sideClass}"><strong>${order.side}</strong></span></td>
                <td>${order.order_type}</td>
                <td>$${parseFloat(order.price).toFixed(2)}</td>
                <td>${parseFloat(order.qty).toFixed(4)}</td>
                <td><span class="badge bg-warning">${order.order_status}</span></td>
            </tr>
        `;
        tbody.innerHTML += row;
    });
}

// Update executions table
function updateExecutionsTable(executions) {
    const tbody = document.getElementById('executionsTable');
    tbody.innerHTML = '';

    if (!executions || executions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">Нет исполнений</td></tr>';
        return;
    }

    executions.slice(0, 20).forEach(exec => {
        const sideClass = exec.side === 'Buy' ? 'text-success' : 'text-danger';
        const row = `
            <tr>
                <td>${exec.exec_id}</td>
                <td>${exec.symbol}</td>
                <td><span class="${sideClass}"><strong>${exec.side}</strong></span></td>
                <td>$${parseFloat(exec.exec_price).toFixed(2)}</td>
                <td>${parseFloat(exec.exec_qty).toFixed(4)}</td>
                <td>$${parseFloat(exec.exec_fee).toFixed(4)}</td>
                <td>${new Date(exec.exec_time).toLocaleString('ru-RU')}</td>
            </tr>
        `;
        tbody.innerHTML += row;
    });
}

// Load account info
async function loadAccountInfo() {
    console.log('[loadAccountInfo] Starting...');
    
    // Get balance
    console.log('[loadAccountInfo] Getting balance...');
    const balance = await apiCall('/account/balance');
    if (balance) {
        console.log('[loadAccountInfo] Balance received:', balance);
        document.getElementById('totalBalance').textContent = '$' + parseFloat(balance.total_balance || 0).toFixed(2);
        document.getElementById('unrealizedPnl').textContent = '$' + parseFloat(balance.unrealized_pnl || 0).toFixed(2);
        updateBalanceInfo(balance);
    } else {
        console.warn('[loadAccountInfo] No balance data');
    }

    // Get positions
    console.log('[loadAccountInfo] Getting positions...');
    const positions = await apiCall('/account/positions');
    if (positions) {
        console.log('[loadAccountInfo] Positions received:', positions);
        document.getElementById('positionCount').textContent = (positions.length || 0).toString();
        updatePositionsTable(positions);
    } else {
        console.warn('[loadAccountInfo] No positions data');
    }

    // Get account status
    console.log('[loadAccountInfo] Getting account status...');
    const status = await apiCall('/account/status');
    if (status) {
        console.log('[loadAccountInfo] Status received:', status);
        updateAccountInfo(status);
    } else {
        console.warn('[loadAccountInfo] No status data');
    }
    
    console.log('[loadAccountInfo] Done');
}

// Update balance info
function updateBalanceInfo(balance) {
    const balanceEl = document.getElementById('balanceInfo');
    balanceEl.innerHTML = `
        <p><strong>Всего:</strong> $${parseFloat(balance.total_balance || 0).toFixed(2)}</p>
        <p><strong>Доступно:</strong> $${parseFloat(balance.available_balance || 0).toFixed(2)}</p>
        <p><strong>На маржу:</strong> $${parseFloat(balance.margin_balance || 0).toFixed(2)}</p>
        <p><strong>Нереализованный PnL:</strong> 
            <span class="${parseFloat(balance.unrealized_pnl) >= 0 ? 'text-success' : 'text-danger'}">
                $${parseFloat(balance.unrealized_pnl || 0).toFixed(2)}
            </span>
        </p>
    `;
}

// Update account info
function updateAccountInfo(status) {
    const accountEl = document.getElementById('accountInfo');
    accountEl.innerHTML = `
        <p><strong>ID аккаунта:</strong> ${status.account_id || '-'}</p>
        <p><strong>Статус:</strong> <span class="badge bg-info">${status.account_status || '-'}</span></p>
        <p><strong>Типе аккаунта:</strong> ${status.account_type || '-'}</p>
        <p><strong>Маржа:</strong> ${status.margin_status || '-'}</p>
    `;
}

// Update positions table
function updatePositionsTable(positions) {
    const tbody = document.getElementById('positionsTable');
    tbody.innerHTML = '';

    if (!positions || positions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">Нет открытых позиций</td></tr>';
        return;
    }

    positions.forEach(pos => {
        const sideClass = pos.side === 'Buy' ? 'text-success' : 'text-danger';
        const pnlClass = parseFloat(pos.pnl || 0) >= 0 ? 'text-success' : 'text-danger';
        const row = `
            <tr>
                <td>${pos.symbol}</td>
                <td><span class="${sideClass}"><strong>${pos.side}</strong></span></td>
                <td>${parseFloat(pos.size).toFixed(4)}</td>
                <td>$${parseFloat(pos.entry_price).toFixed(2)}</td>
                <td>$${parseFloat(pos.mark_price).toFixed(2)}</td>
                <td><span class="${pnlClass}">$${parseFloat(pos.pnl || 0).toFixed(2)}</span></td>
                <td><span class="${pnlClass}">${parseFloat(pos.pnl_pct || 0).toFixed(2)}%</span></td>
            </tr>
        `;
        tbody.innerHTML += row;
    });
}

// Periodic data refresh
setInterval(() => {
    if (document.getElementById('dashboard').style.display !== 'none') {
        updateRecentSignalsWidget();
    }
}, 10000);

setInterval(() => {
    if (document.getElementById('account').style.display !== 'none') {
        loadAccountInfo();
    }
}, 15000);
// ============================================================================
// SIGNAL LOGS FUNCTIONS (для отладки)
// ============================================================================

/**
 * Загрузить логи сигналов
 */
async function loadSignalLogs() {
    try {
        // Получить значения или использовать defaults
        const limitEl = document.getElementById('signalLogLimit');
        const levelEl = document.getElementById('signalLogLevel');
        
        const limit = limitEl ? (parseInt(limitEl.value) || 50) : 50;
        const level = levelEl ? (levelEl.value || 'all') : 'all';
        
        console.log('[loadSignalLogs] Loading logs with limit:', limit, 'level:', level);
        
        const response = await fetch(`${API_BASE}/signals/logs?limit=${limit}&level=${level}`, {
            headers: {
                'Authorization': `Bearer ${getToken()}`
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        console.log('[loadSignalLogs] Received logs:', data.data?.length || 0, 'items');
        displaySignalLogs(data);
    } catch (error) {
        console.error('[SIGNALS] Error loading logs:', error);
        document.getElementById('signalLogsContainer').innerHTML = 
            `<div class="alert alert-danger">Ошибка загрузки логов: ${error.message}</div>`;
    }
}

/**
 * Отобразить логи сигналов с поддержкой структурированных событий
 */
function displaySignalLogs(data) {
    const container = document.getElementById('signalLogsContainer');
    
    // Если контейнера нет, это нормально (может быть на другой вкладке)
    if (!container) {
        console.debug('[displaySignalLogs] Container not found, ignoring display');
        return;
    }
    
    if (!data.data || data.data.length === 0) {
        container.innerHTML = '<p class="text-muted">Нет логов</p>';
        const countEl = document.getElementById('signalLogCount');
        if (countEl) countEl.textContent = '0 событий';
        return;
    }
    
    let html = '';
    
    data.data.forEach((event, index) => {
        // Каждое событие - это структурированный JSON объект
        const cardHtml = createEventCard(event, index);
        html += cardHtml;
    });
    
    container.innerHTML = html;
    
    const countEl = document.getElementById('signalLogCount');
    if (countEl) countEl.textContent = `${data.data.length} событий`;
    
    console.log('[displaySignalLogs] Displayed', data.data.length, 'structured events');
}

/**
 * Создает HTML карточку для структурированного события
 */
function createEventCard(event, index) {
    const {
        ts,
        level,
        category,
        symbol,
        message,
        stage,
        strategy,
        direction,
        confidence,
        reasons,
        values,
        metrics,
        filters,
        details
    } = event;
    
    // Определяем иконку и цвет по category + level + stage
    let icon = '📝';
    let borderColor = 'secondary';
    let badgeClass = 'bg-secondary';
    
    if (category === 'signal') {
        if (stage === 'GENERATED') {
            icon = '✅';
            borderColor = 'info';
            badgeClass = 'bg-info';
        } else if (stage === 'ACCEPTED') {
            icon = '✅'; borderColor = 'success';
            badgeClass = 'bg-success';
        } else if (stage === 'REJECTED') {
            icon = '❌';
            borderColor = 'danger';
            badgeClass = 'bg-danger';
        }
    } else if (category === 'execution') {
        icon = '⚡';
        borderColor = 'warning';
        badgeClass = 'bg-warning';
        if (stage === 'FAILED') {
            icon = '❌';
            borderColor = 'danger';
            badgeClass = 'bg-danger';
        }
    } else if (category === 'risk') {
        icon = '⚠️';
        borderColor = 'warning';
        badgeClass = 'bg-warning';
    } else if (category === 'kill_switch') {
        icon = '🛑';
        borderColor = 'danger';
        badgeClass = 'bg-danger';
    } else if (category === 'market_analysis') {
        icon = '📊';
        borderColor = 'info';
        badgeClass = 'bg-info';
    } else if (category === 'strategy_analysis') {
        icon = '🔍';
        borderColor = 'primary';
        badgeClass = 'bg-primary';
    }
    
    // Summary line (всегда видна)
    const summaryHtml = `
        <div class="d-flex justify-content-between align-items-center">
            <div class="d-flex align-items-center gap-2">
                <span class="fs-4">${icon}</span>
                <span class="badge ${badgeClass}">${category}</span>
                <strong class="text-white">${symbol}</strong>
                <span class="text-light">${message}</span>
            </div>
            <small class="text-light">${ts}</small>
        </div>
    `;
    
    // Expanded details (раскрываются по клику)
    let expandedHtml = '';
    
    // Базовая информация о сигнале
    if (category === 'signal' && strategy) {
        expandedHtml += `
            <div class="row mt-2">
                <div class="col-md-3">
                    <small class="text-light">Strategy:</small><br>
                    <strong class="text-white">${strategy}</strong>
                </div>
                ${direction ? `
                <div class="col-md-3">
                    <small class="text-light">Direction:</small><br>
                    <strong class="text-white">${direction}</strong>
                </div>
                ` : ''}
                ${confidence !== undefined ? `
                <div class="col-md-3">
                    <small class="text-light">Confidence:</small><br>
                    <strong class="text-white">${(confidence * 100).toFixed(1)}%</strong>
                </div>
                ` : ''}
                ${stage ? `
                <div class="col-md-3">
                    <small class="text-light">Stage:</small><br>
                    <span class="badge ${badgeClass}">${stage}</span>
                </div>
                ` : ''}
            </div>
        `;
    }
    
    // Reasons (причины отклонения или предупреждения)
    if (reasons && reasons.length > 0) {
        expandedHtml += `
            <div class="mt-2">
                <small class="text-light d-block mb-1">Reasons:</small>
                ${reasons.map(r => `<span class="badge bg-warning text-dark me-1">${r}</span>`).join('')}
            </div>
        `;
    }
    
    // Metrics (метрики рынка/стратегии)
    if (metrics && Object.keys(metrics).length > 0) {
        const metricsRows = Object.entries(metrics).map(([key, value]) => {
            const formattedValue = typeof value === 'number' ? value.toFixed(4) : String(value);
            return `
                <div class="col-md-3 mb-1">
                    <small class="text-light">${key}:</small>
                    <strong class="ms-2 text-white">${formattedValue}</strong>
                </div>
            `;
        }).join('');
        
        expandedHtml += `
            <div class="mt-2">
                <small class="text-light d-block mb-1">📊 Metrics:</small>
                <div class="row small">${metricsRows}</div>
            </div>
        `;
    }
    
    // Values (значения переменных с порогами)
    if (values && Object.keys(values).length > 0) {
        const valuesRows = Object.entries(values).map(([key, value]) => {
            const formattedValue = typeof value === 'number' ? value.toFixed(4) : String(value);
            return `
                <div class="col-md-4 mb-1">
                    <small class="text-light">${key}:</small>
                    <strong class="ms-2 text-white">${formattedValue}</strong>
                </div>
            `;
        }).join('');
        
        expandedHtml += `
            <div class="mt-2">
                <small class="text-light d-block mb-1">🔢 Values:</small>
                <div class="row small">${valuesRows}</div>
            </div>
        `;
    }
    
    // Filters (результаты фильтров стратегии)
    if (filters && filters.length > 0) {
        const filtersRows = filters.map(f => {
            const passIcon = f.pass ? '✅' : '❌';
            const passClass = f.pass ? 'text-success' : 'text-danger';
            const valueStr = f.value !== undefined ? f.value : 'N/A';
            const thresholdStr = f.threshold !== undefined ? f.threshold : 'N/A';
            
            return `
                <tr>
                    <td class="${passClass}">${passIcon} ${f.name}</td>
                    <td>${valueStr}</td>
                    <td>${thresholdStr}</td>
                    <td class="${passClass}">${f.pass ? 'PASS' : 'FAIL'}</td>
                </tr>
            `;
        }).join('');
        
        expandedHtml += `
            <div class="mt-2">
                <small class="text-light d-block mb-1">🔍 Filters:</small>
                <table class="table table-sm table-dark table-bordered">
                    <thead>
                        <tr>
                            <th>Filter</th>
                            <th>Value</th>
                            <th>Threshold</th>
                            <th>Result</th>
                        </tr>
                    </thead>
                    <tbody>${filtersRows}</tbody>
                </table>
            </div>
        `;
    }
    
    // Details (дополнительная информация)
    if (details && Object.keys(details).length > 0) {
        const detailsStr = JSON.stringify(details, null, 2);
        expandedHtml += `
            <div class="mt-2">
                <small class="text-light d-block mb-1">📋 Details:</small>
                <pre class="bg-dark text-light p-2 rounded small">${detailsStr}</pre>
            </div>
        `;
    }
    
    // Создаем карточку с возможностью раскрытия
    const cardId = `event-card-${index}`;
    const collapseId = `collapse-${index}`;
    
    return `
        <div id="${cardId}" class="card bg-dark border-${borderColor} border-start border-3 mb-2">
            <div class="card-body p-2 cursor-pointer" data-bs-toggle="collapse" data-bs-target="#${collapseId}">
                ${summaryHtml}
            </div>
            ${expandedHtml ? `
                <div id="${collapseId}" class="collapse">
                    <div class="card-body pt-0 pb-2">
                        ${expandedHtml}
                    </div>
                </div>
            ` : ''}
        </div>
    `;
}

/**
 * Очистить логи (на самом деле - перезагрузить пустыми)
 */
function clearSignalLogs() {
    if (confirm('Вы уверены? Это не удалит файл, только очистит представление.')) {
        const container = document.getElementById('signalLogsContainer');
        if (container) {
            container.innerHTML = '';
        }
        const countEl = document.getElementById('signalLogCount');
        if (countEl) {
            countEl.textContent = '0 событий';
        }
    }
}

/**
 * Добавить лог в контейнер в реальном времени (из WebSocket)
 */
function addLiveLog(logData) {
    const container = document.getElementById('signalLogsContainer');
    if (!container) return;
    
    let event;
    
    // Если logData уже структурированное событие (есть category)
    if (logData.category) {
        event = logData;
    } else {
        // Парсим legacy формат или создаем базовое событие
        const message = logData.message || 'Unknown log';
        const timestamp = logData.timestamp || new Date().toISOString();
        
        // Фильтруем только ВАЖНЫЕ логи для legacy формата
        const isImportant = 
            message.includes('Stage=GENERATED') ||
            message.includes('Stage=ACCEPTED') ||
            message.includes('Stage=REJECTED') ||
            message.includes('ORDER EXEC FAILED');
        
        if (!isImportant) {
            console.debug('[addLiveLog] Skipping non-important log:', message);
            return;
        }
        
        // Конвертируем в структурированное событие
        const symbolMatch = message.match(/Symbol=([A-Z]+)/);
        const directionMatch = message.match(/Direction=([A-Z]+)/);
        const strategyMatch = message.match(/Strategy=([^|]+)/);
        const reasonMatch = message.match(/Reasons=(\[[^\]]*\])/);
        const stageMatch = message.match(/Stage=([A-Z]+)/);
        
        event = {
            ts: timestamp,
            level: message.includes('FAILED') ? 'ERROR' : 'SIGNAL',
            category: message.includes('ORDER EXEC') ? 'execution' : 'signal',
            symbol: symbolMatch ? symbolMatch[1] : 'UNKNOWN',
            message: message,
            stage: stageMatch ? stageMatch[1] : null,
            strategy: strategyMatch ? strategyMatch[1].trim() : null,
            direction: directionMatch ? directionMatch[1] : null,
            reasons: null
        };
        
        if (reasonMatch) {
            try {
                event.reasons = JSON.parse(reasonMatch[1]);
            } catch {
                event.reasons = [reasonMatch[1]];
            }
        }
    }
    
    // Фильтрация по важности для структурированных событий
    const isImportantEvent = 
        event.category === 'signal' ||
        event.category === 'execution' ||
        event.category === 'risk' ||
        event.category === 'kill_switch' ||
        (event.stage && ['GENERATED', 'ACCEPTED', 'REJECTED'].includes(event.stage));
    
    if (!isImportantEvent) {
        console.debug('[addLiveLog] Skipping non-important event:', event);
        return;
    }
    
    // Используем createEventCard для рендеринга (индекс = текущее количество логов)
    const currentCards = container.querySelectorAll('.card');
    const cardHtml = createEventCard(event, currentCards.length);
    
    // Создаем элемент из HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = cardHtml;
    const logEntry = tempDiv.firstElementChild;
    
    // Добавляем новый лог в начало контейнера
    if (container.firstChild) {
        container.insertBefore(logEntry, container.firstChild);
    } else {
        container.appendChild(logEntry);
    }
    
    // Ограничиваем количество отображаемых логов до 50
    const allCards = container.querySelectorAll('.card');
    if (allCards.length > 50) {
        for (let i = allCards.length - 1; i >= 50; i--) {
            allCards[i].remove();
        }
    }
    
    // Обновляем счетчик логов
    const count = allCards.length;
    const countEl = document.getElementById('signalLogCount');
    if (countEl) {
        countEl.textContent = `${count} событий`;
    }
}

// Загружаем логи при открытии вкладки
document.addEventListener('DOMContentLoaded', () => {
    // Оригинальный код инициализации...
    // При нажатии на вкладку signals-log, загружаем логи
    document.querySelectorAll('[data-tab]').forEach(button => {
        button.addEventListener('click', (e) => {
            const tab = e.currentTarget.getAttribute('data-tab');
            if (tab === 'signals-log') {
                setTimeout(() => loadSignalLogs(), 100);
            }
        });
    });
});