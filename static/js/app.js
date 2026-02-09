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
    
    // Update bot status badge
    const botStatusEl = document.getElementById('botStatus');
    if (botStatusEl) {
        if (connected) {
            botStatusEl.textContent = 'Active';
            botStatusEl.className = 'badge bg-success';
        } else {
            botStatusEl.textContent = 'Stopped';
            botStatusEl.className = 'badge bg-warning';
        }
    }
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
    
    // Show bot as Active if API is connected
    const statusBadge = document.getElementById('botStatus');
    if (isConnected) {
        statusBadge.textContent = 'Active';
        statusBadge.className = 'badge bg-success';
    } else {
        statusBadge.textContent = 'Stopped';
        statusBadge.className = 'badge bg-warning';
    }
    
    console.log('[updateDashboardFromConfig] Updated with symbols:', symbols);
}

// Load settings form
async function loadSettings() {
    const configData = await apiCall('/config');
    if (!configData) return;

    // Load primary symbol
    document.getElementById('settingSymbol').value = configData.trading?.symbol || '';
    
    // Load multiple symbols if available
    const symbols = configData.trading?.symbols || [];
    if (symbols.length > 0) {
        document.getElementById('settingSymbols').value = symbols.join(', ');
    } else if (configData.trading?.symbol) {
        // Fallback: if no symbols array, use single symbol
        document.getElementById('settingSymbols').value = configData.trading.symbol;
    }
    
    document.getElementById('settingMode').value = configData.trading?.mode || 'paper';
    document.getElementById('settingRiskPercent').value = configData.risk_management?.position_risk_percent || 1.0;
    document.getElementById('settingMaxLeverage').value = configData.risk_management?.max_leverage || 10;
    document.getElementById('settingStopLoss').value = configData.risk_management?.stop_loss_percent || 2.0;
    document.getElementById('settingTakeProfit').value = configData.risk_management?.take_profit_percent || 5.0;
    
    console.log('[loadSettings] Loaded symbols:', symbols);
}


// Save settings
async function saveSettings() {
    // Parse multiple symbols from comma/space separated input
    const symbolsInput = document.getElementById('settingSymbols').value;
    const symbols = symbolsInput
        .split(/[,\s]+/)  // Split by comma or space
        .map(s => s.trim().toUpperCase())  // Trim and uppercase
        .filter(s => s.length > 0);  // Remove empty strings
    
    const primarySymbol = document.getElementById('settingSymbol').value.toUpperCase();
    
    const updates = {
        'trading.symbols': symbols,  // Array of symbols
        'trading.symbol': primarySymbol || (symbols.length > 0 ? symbols[0] : ''),  // Primary symbol
        'trading.mode': document.getElementById('settingMode').value,
        'risk_management.position_risk_percent': parseFloat(document.getElementById('settingRiskPercent').value),
        'risk_management.max_leverage': parseInt(document.getElementById('settingMaxLeverage').value),
        'risk_management.stop_loss_percent': parseFloat(document.getElementById('settingStopLoss').value),
        'risk_management.take_profit_percent': parseFloat(document.getElementById('settingTakeProfit').value),
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
    }
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
        const limit = parseInt(document.getElementById('signalLogLimit').value) || 50;
        const level = document.getElementById('signalLogLevel').value || 'all';
        
        const response = await fetch(`${API_BASE}/signals/logs?limit=${limit}&level=${level}`, {
            headers: {
                'Authorization': `Bearer ${getToken()}`
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        displaySignalLogs(data);
    } catch (error) {
        console.error('[SIGNALS] Error loading logs:', error);
        document.getElementById('signalLogsContainer').innerHTML = 
            `<div class="alert alert-danger">Ошибка загрузки логов: ${error.message}</div>`;
    }
}

/**
 * Отобразить логи сигналов с цветовой подсветкой
 */
function displaySignalLogs(data) {
    const container = document.getElementById('signalLogsContainer');
    
    if (!data.data || data.data.length === 0) {
        container.innerHTML = '<p class="text-muted">Нет логов</p>';
        return;
    }
    
    let html = '';
    
    data.data.forEach(log => {
        let rowClass = 'text-light';
        let icon = '📝';
        
        // Определяем цвет в зависимости от типа сообщения
        if (log.message.includes('✅')) {
            rowClass = 'text-success';
            icon = '✅';
        } else if (log.message.includes('❌')) {
            rowClass = 'text-danger';
            icon = '❌';
        } else if (log.message.includes('⏳')) {
            rowClass = 'text-warning';
            icon = '⏳';
        } else if (log.message.includes('🔍')) {
            rowClass = 'text-info';
            icon = '🔍';
        } else if (log.message.includes('📊')) {
            rowClass = 'text-secondary';
            icon = '📊';
        }
        
        // Парсим сообщение для лучшего отображения
        const message = log.message || log.raw || 'Unknown log';
        const timestamp = log.timestamp || 'N/A';
        
        // Разбиваем на части по |
        const parts = message.split('|').map(p => p.trim()).filter(p => p);
        
        html += `
            <div class="log-entry ${rowClass} border-start border-3 ps-3 mb-2 py-2 font-monospace small">
                <div style="color: #888;">${timestamp}</div>
                <div><strong>${parts[0]}</strong></div>
                ${parts.slice(1).map(p => `<div style="color: #ccc; margin-left: 10px;">• ${p}</div>`).join('')}
            </div>
        `;
    });
    
    container.innerHTML = html;
    document.getElementById('signalLogCount').textContent = `${data.data.length} логов`;
}

/**
 * Очистить логи (на самом деле - перезагрузить пустыми)
 */
function clearSignalLogs() {
    if (confirm('Вы уверены? Это не удалит файл, только очистит представление.')) {
        document.getElementById('signalLogsContainer').innerHTML = '';
        document.getElementById('signalLogCount').textContent = '0 логов';
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