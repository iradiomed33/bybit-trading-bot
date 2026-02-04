/**
 * Login Page Script
 * Обработка входа, сохранение токена и редирект на дашборд
 */

// Константы
const API_URL = window.location.origin;
const TOKEN_KEY = 'auth_token';
const USERNAME_KEY = 'auth_username';
const REMEMBER_KEY = 'auth_remember';
const REMEMBER_DURATION = 7 * 24 * 60 * 60 * 1000; // 7 дней в миллисекундах

/**
 * Обработать отправку формы входа
 */
async function handleLogin(event) {
    event.preventDefault();

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const rememberMe = document.getElementById('rememberMe').checked;
    const loginBtn = document.getElementById('loginBtn');

    // Валидация
    if (!username || !password) {
        showError('Username and password are required');
        return;
    }

    console.log('[LOGIN FORM] Attempting login for user:', username);

    // Показать статус загрузки
    loginBtn.disabled = true;
    const originalHTML = loginBtn.innerHTML;
    loginBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Signing in...';

    try {
        // Отправить запрос на логин
        console.log('[LOGIN FORM] Sending login request to server');
        const response = await fetch(`${API_URL}/api/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                username: username,
                password: password,
            }),
        });

        const data = await response.json();
        console.log('[LOGIN FORM] Login response:', { ok: response.ok, status: response.status, data });

        if (!response.ok) {
            showError(data.detail || 'Login failed. Please check your credentials.');
            return;
        }

        // Сохранить токен
        saveToken(data.access_token, username, rememberMe);

        // Показать успешное сообщение
        showSuccess(`Welcome, ${data.username}! Redirecting...`);

        // Редирект на дашборд через 1 секунду
        setTimeout(() => {
            console.log('[LOGIN FORM] Redirecting to dashboard');
            window.location.href = '/';
        }, 1000);

    } catch (error) {
        console.error('[LOGIN FORM] Login error:', error);
        showError(`Connection error: ${error.message}`);
    } finally {
        // Вернуть кнопку в исходное состояние
        loginBtn.disabled = false;
        loginBtn.innerHTML = originalHTML;
    }
}

/**
 * Сохранить токен в localStorage
 */
function saveToken(token, username, rememberMe) {
    console.log('[LOGIN] Saving token for user:', username);
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USERNAME_KEY, username);
    
    if (rememberMe) {
        const expiryTime = new Date().getTime() + REMEMBER_DURATION;
        localStorage.setItem(REMEMBER_KEY, expiryTime.toString());
        console.log('[LOGIN] Remember me enabled for 7 days');
    } else {
        localStorage.removeItem(REMEMBER_KEY);
    }
}

/**
 * Получить сохраненный токен
 */
function getToken() {
    // Проверить, не истекло ли время "Remember Me"
    const rememberExpiry = localStorage.getItem(REMEMBER_KEY);
    if (rememberExpiry && new Date().getTime() > parseInt(rememberExpiry)) {
        clearToken();
        return null;
    }

    return localStorage.getItem(TOKEN_KEY);
}

/**
 * Очистить токен
 */
function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USERNAME_KEY);
    localStorage.removeItem(REMEMBER_KEY);
}

/**
 * Показать ошибку
 */
function showError(message) {
    const alert = document.getElementById('errorAlert');
    const messageEl = document.getElementById('errorMessage');
    messageEl.textContent = message;
    alert.style.display = 'block';
}

/**
 * Показать успех
 */
function showSuccess(message) {
    const alert = document.getElementById('successAlert');
    const messageEl = document.getElementById('successMessage');
    messageEl.textContent = message;
    alert.style.display = 'block';
}

/**
 * При загрузке страницы проверить, не уже ли вошли
 */
document.addEventListener('DOMContentLoaded', async () => {
    console.log('[LOGIN PAGE] Checking if already logged in...');
    const token = getToken();

    if (token) {
        console.log('[LOGIN PAGE] Token found in localStorage');
        // Попытаться проверить токен
        try {
            const response = await fetch(`${API_URL}/api/auth/verify`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            });

            const data = await response.json();
            console.log('[LOGIN PAGE] Verify response:', data);

            if (data.valid) {
                // Токен еще действителен, редирект на дашборд
                console.log('[LOGIN PAGE] Token is valid, redirecting to dashboard');
                // Небольшая задержка перед редиректом для гарантии
                setTimeout(() => {
                    window.location.href = '/';
                }, 500);
                return; // Выход чтобы не продолжать выполнение
            } else {
                // Токен невалиден, очистить и показать форму
                console.log('[LOGIN PAGE] Token is invalid, clearing and showing form');
                clearToken();
            }
        } catch (error) {
            console.error('[LOGIN PAGE] Token verification error:', error);
            // Оставить форму видимой
        }
    } else {
        console.log('[LOGIN PAGE] No token found, showing login form');
    }

    // Фокус на поле username
    document.getElementById('username').focus();

    // Обработчик Enter для отправки формы
    document.getElementById('loginForm').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleLogin(e);
        }
    });
});
