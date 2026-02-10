# Execution Gateway Pattern - Разделение режимов

## Проблема

В TradingBot было 20+ проверок `if mode == "live"` и `if mode == "paper"`, что:
- Затрудняло поддержку кода
- Усложняло добавление новых режимов
- Нарушало принцип "стратегия не знает где она исполняется"

## Решение: Gateway Pattern

Создан абстрактный интерфейс `IExecutionGateway` с реализациями для каждого режима.

---

## Архитектура

```
TradingBot
    ↓
gateway: IExecutionGateway
    ↓
    ├─ BybitLiveGateway → OrderManager → Bybit API
    ├─ PaperGateway → PaperTradingSimulator
    └─ BacktestGateway → Internal Simulator
```

---

## IExecutionGateway Interface

**Файл:** `execution/gateway.py`

### Методы:

```python
class IExecutionGateway(ABC):
    @abstractmethod
    def place_order(...) -> OrderResult:
        """Разместить ордер"""
        
    @abstractmethod
    def cancel_order(...) -> OrderResult:
        """Отменить ордер"""
        
    @abstractmethod
    def cancel_all_orders(...) -> OrderResult:
        """Отменить все ордера"""
        
    @abstractmethod
    def get_position(...) -> Optional[Dict]:
        """Получить позицию"""
        
    @abstractmethod
    def get_positions(...) -> List[Dict]:
        """Получить все позиции"""
        
    @abstractmethod
    def get_open_orders(...) -> List[Dict]:
        """Получить открытые ордера"""
        
    @abstractmethod
    def set_trading_stop(...) -> OrderResult:
        """Установить SL/TP"""
        
    @abstractmethod
    def cancel_trading_stop(...) -> OrderResult:
        """Отменить SL/TP"""
        
    @abstractmethod
    def get_account_balance(...) -> Dict:
        """Получить баланс"""
        
    @abstractmethod
    def get_executions(...) -> List[Dict]:
        """Получить исполнения"""
```

---

## Реализации

### 1. BybitLiveGateway

**Файл:** `execution/live_gateway.py`

**Для:** Реальная торговля на Bybit

**Использует:**
- OrderManager - для всех операций с ордерами
- PositionManager - для позиций
- Прямой доступ к API через OrderManager.client

**Пример:**
```python
from execution import BybitLiveGateway, OrderManager, PositionManager

order_manager = OrderManager(rest_client, db)
position_manager = PositionManager(order_manager)

gateway = BybitLiveGateway(order_manager, position_manager)

# Разместить ордер
result = gateway.place_order(
    category="linear",
    symbol="BTCUSDT",
    side="Buy",
    order_type="Market",
    qty=0.001
)

if result.success:
    print(f"Order placed: {result.order_id}")
else:
    print(f"Error: {result.error}")
```

---

### 2. PaperGateway

**Файл:** `execution/paper_gateway.py`

**Для:** Paper trading (симуляция с реальными ценами)

**Использует:**
- PaperTradingSimulator

**Особенности:**
- Адаптирует вызовы simulator к интерфейсу gateway
- Конвертирует dict результаты в OrderResult
- SL/TP управляются виртуально
- Баланс из simulator.balance

**Пример:**
```python
from execution import PaperGateway
from execution.paper_trading_simulator import PaperTradingSimulator

config = PaperTradingConfig(initial_balance=10000, fee_rate=0.0006)
simulator = PaperTradingSimulator(config)

gateway = PaperGateway(simulator)

result = gateway.place_order(
    category="linear",
    symbol="BTCUSDT",
    side="Buy",
    order_type="Market",
    qty=0.01
)
```

---

### 3. BacktestGateway

**Файл:** `execution/backtest_gateway.py`

**Для:** Backtesting (полная симуляция)

**Особенности:**
- Внутренний симулятор (без зависимостей)
- Хранение позиций и ордеров в памяти
- Market ордера исполняются мгновенно
- Limit ордера в pending состоянии
- Метод `update_position_pnl()` для обновления PnL

**Пример:**
```python
from execution import BacktestGateway

gateway = BacktestGateway(initial_balance=10000)

# Разместить market ордер (исполняется мгновенно)
result = gateway.place_order(
    category="linear",
    symbol="BTCUSDT",
    side="Buy",
    order_type="Market",
    qty=0.001,
    price=50000.0  # Текущая цена
)

# Обновить PnL при изменении цены
gateway.update_position_pnl("BTCUSDT", current_price=51000.0)

# Получить баланс
balance = gateway.get_account_balance()
print(f"Equity: {balance['equity']}")
```

---

## Использование в TradingBot

### Было (с if-ами):

```python
class TradingBot:
    def __init__(self, mode, ...):
        self.mode = mode
        
        if mode == "live":
            self.order_manager = OrderManager(...)
            self.position_manager = PositionManager(...)
        elif mode == "paper":
            self.paper_simulator = PaperTradingSimulator(...)
            
    def place_order(self, ...):
        if self.mode == "live":
            return self.order_manager.create_order(...)
        elif self.mode == "paper":
            return self.paper_simulator.place_order(...)
```

### Стало (с gateway):

```python
class TradingBot:
    def __init__(self, mode, ...):
        # Создание gateway в зависимости от режима
        if mode == "live":
            order_manager = OrderManager(...)
            position_manager = PositionManager(...)
            self.gateway = BybitLiveGateway(order_manager, position_manager)
        elif mode == "paper":
            simulator = PaperTradingSimulator(...)
            self.gateway = PaperGateway(simulator)
        elif mode == "backtest":
            self.gateway = BacktestGateway(initial_balance=10000)
            
    def place_order(self, ...):
        # Без if-ов!
        return self.gateway.place_order(...)
```

---

## Преимущества

### 1. Стратегия не знает где она исполняется ✅
```python
# Стратегия просто вызывает gateway
result = gateway.place_order(...)

# Не важно live это, paper или backtest
```

### 2. Легко добавить новый режим ✅
```python
# Например, Demo режим для другой биржи
class BinanceDemoGateway(IExecutionGateway):
    def place_order(self, ...):
        # Реализация для Binance demo
        pass
```

### 3. Упрощённое тестирование ✅
```python
# Mock gateway для unit тестов
class MockGateway(IExecutionGateway):
    def place_order(self, ...):
        return OrderResult.success_result(order_id="mock_123")
        
# Использование в тестах
bot = TradingBot(gateway=MockGateway())
```

### 4. Чистый код без if-ов ✅
- Бизнес-логика не зависит от режима
- Легче читать и поддерживать
- Меньше вероятность ошибок

---

## OrderResult

Все методы gateway возвращают `OrderResult`:

```python
@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str] = None
    error: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)
```

**Пример проверки:**
```python
result = gateway.place_order(...)

if result.success:
    print(f"Order placed: {result.order_id}")
    # Доступ к raw ответу
    print(f"Raw: {result.raw}")
else:
    print(f"Error: {result.error}")
```

---

## Миграция

### Шаг 1: Замена инициализации

**Было:**
```python
if mode == "live":
    self.order_manager = OrderManager(...)
```

**Стало:**
```python
if mode == "live":
    order_manager = OrderManager(...)
    self.gateway = BybitLiveGateway(order_manager, position_manager)
```

### Шаг 2: Замена вызовов

**Было:**
```python
if self.mode == "live":
    result = self.order_manager.create_order(...)
elif self.mode == "paper":
    result = self.paper_simulator.place_order(...)
```

**Стало:**
```python
result = self.gateway.place_order(...)
```

### Шаг 3: Убрать проверки mode

Удалить все `if self.mode == "live"` из бизнес-логики.

---

## Статус

✅ **РЕАЛИЗОВАНО:**
- IExecutionGateway interface
- BybitLiveGateway
- PaperGateway
- BacktestGateway
- Экспорт из execution модуля

🔄 **TODO:**
- Рефакторинг TradingBot для использования gateway
- Убрать if mode проверки из кода
- Обновить документацию TradingBot
- Создать тесты с mock gateway

---

## Файлы

**Новые:**
- `execution/gateway.py` - интерфейс (200 строк)
- `execution/live_gateway.py` - live реализация (200 строк)
- `execution/paper_gateway.py` - paper реализация (220 строк)
- `execution/backtest_gateway.py` - backtest реализация (280 строк)

**Изменённые:**
- `execution/__init__.py` - экспорт gateway классов

**Следующий шаг:**
Рефакторинг TradingBot.py для полного использования gateway вместо прямых вызовов OrderManager/PaperSimulator.
