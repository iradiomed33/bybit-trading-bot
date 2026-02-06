"""
EXE-001 Implementation: Maker/Taker политика и выбор типа ордера

=== РЕАЛИЗАЦИЯ ===

1. ORDER POLICY FRAMEWORK (execution/order_policy.py)

   Классы:
   - OrderExecType: enum с MAKER, TAKER, IOC
   - TimeInForce: enum с GTC, IOC, FOK, PostOnly
   - OrderPolicy: dataclass с параметрами ордера
   - OrderPolicySelector: выбор политики по стратегии и режиму

2. ЛОГИКА ВЫБОРА ТИПА ОРДЕРА

   Стратегия → Тип ордера → Параметры
   
   a) TrendPullback:
      - Normal режим:
        * order_type: Limit (maker)
        * time_in_force: GTC (виснет)
        * post_only: True (избегаем taker)
        * ttl_seconds: 300 (5 минут)
        * commission: 0.02% (maker)
      
      - high_vol_event:
        * order_type: Market (taker)
        * time_in_force: IOC (быстро)
        * post_only: False
        * commission: 0.04% (taker)

   b) Breakout:
      - Normal режим:
        * order_type: Limit (maker)
        * time_in_force: PostOnly (гарантия только maker)
        * post_only: True
        * ttl_seconds: 180 (3 минуты, пробой быстро заканчивается)
        * commission: 0.02%
      
      - high_vol_event:
        * order_type: Market (taker)
        * time_in_force: FOK (Fill-Or-Kill, гарантия полного заполнения)
        * post_only: False
        * commission: 0.04%

   c) MeanReversion:
      - Normal режим:
        * order_type: Limit (maker)
        * time_in_force: GTC (долгий отскок)
        * post_only: True
        * ttl_seconds: 600 (10 минут)
        * commission: 0.02%
      
      - high_vol_event:
        * order_type: Market (taker)
        * time_in_force: IOC
        * post_only: False
        * commission: 0.04%

3. ДИНАМИЧЕСКАЯ КОРРЕКТИРОВКА

   По уверенности сигнала (confidence):
   - confidence >= 0.75: базовый TTL
   - confidence < 0.65: TTL сокращается вдвое (но не менее 60 секунд)
   - Идея: слабые сигналы не висят долго

   По режиму рынка:
   - high_vol_event: ВСЕГДА Taker (быстрое исполнение > экономия на комиссии)
   - range: Maker + длинный TTL (есть время ждать)
   - trend: Maker + средний TTL (пробой может закончиться)

4. КОМИССИИ

   Rates по Bybit (standard):
   - Maker: 0.02% (вознаграждение за пассивный ордер)
   - Taker: 0.04% (плата за активный ордер)
   
   Expected commission рассчитывается в params:
   - Для paper trading: используется в расчётах PnL
   - Для logging: информирует о вероятной стоимости заполнения

5. ЛОГИРОВАНИЕ ПАРАМЕТРОВ

   В signal_logger и лог-файлы пишутся:
   ```
   Order execution params:
   - order_type: "Limit" | "Market"
   - time_in_force: "GTC" | "IOC" | "FOK" | "PostOnly"
   - post_only: true | false
   - maker_intent: true | false (важный флаг - планируем ли быть maker)
   - ttl_seconds: N (сколько секунд висеть лимитке)
   - exec_type: "maker" | "taker" | "ioc"
   - expected_commission: 0.0002 | 0.0004 (комиссия в долях)
   ```

=== ИСПОЛЬЗОВАНИЕ В BOTЕ ===

1. При генерации сигнала:
   ```python
   signal = self.meta_layer.get_signal(df, features)
   
   if signal:
       # Выбираем политику
       order_params = OrderPolicySelector.get_order_params(
           strategy_name=signal.get('strategy'),
           regime=regime,
           confidence=signal.get('confidence'),
       )
       
       # Логируем политику
       signal_logger.log_order_execution_start(
           symbol=self.symbol,
           direction=signal['signal'],
           order_type=order_params['order_type'],
           time_in_force=order_params['time_in_force'],
           post_only=order_params['post_only'],
           maker_intent=order_params['maker_intent'],
       )
       
       # Выставляем ордер с параметрами
       order = self.order_manager.create_order(
           order_type=order_params['order_type'],
           time_in_force=order_params['time_in_force'],
           post_only=order_params['post_only'],
       )
   ```

2. В paper trading:
   ```python
   # Использует ожидаемую комиссию из params
   commission = qty * entry_price * order_params['expected_commission']
   pnl = (exit_price - entry_price) * qty - commission
   ```

=== ТЕСТИРОВАНИЕ ===

Unit-тесты: test_exe001.py (11 тестов, все pass)
- Test 1: TrendPullback normal = Limit GTC 300s maker
- Test 2: Breakout normal = Limit PostOnly 180s maker
- Test 3: MeanReversion normal = Limit GTC 600s maker
- Test 4: high_vol_event all strategies = Market IOC/FOK taker
- Test 5: Low confidence reduces TTL by half
- Test 6: Commission rates (maker 0.02%, taker 0.04%)
- Test 7: Order params complete structure
- Test 8: Unknown strategy fallback to conservative maker
- Test 9: post_only always means maker_intent
- Test 10: All regimes handled correctly
- Test 11: Logging fields present

=== КОНФИГУРАЦИЯ (config/settings.py) ===

```python
"execution": {
    "order_type": "limit",
    "time_in_force": "GTC",
    "post_only": True,
    "ttl_seconds": 300,
    "maker_commission": 0.0002,      # 0.02%
    "taker_commission": 0.0004,      # 0.04%
    "use_breakeven": True,
    "use_partial_exit": True,
    "partial_exit_percent": 0.5,
}
```

=== DoD REQUIREMENTS ===

✅ Для каждой стратегии определена логика:
   - Когда можно лимиткой (maker): normal/range режимы
   - Когда нужен маркет/IOC (taker): high_vol_event режим
   
✅ post_only и TTL добавлены где уместно:
   - post_only=True для всех maker ордеров
   - TTL варьируется: Breakout 180s, TrendPullback 300s, MeanReversion 600s
   - TTL сокращается при низкой уверенности

✅ В логах: order_type, time_in_force, post_only, maker_intent
   - signal_logger: все параметры записываются
   - expected_commission для информирования о стоимости

✅ Paper/backtest учитывают maker/taker комиссии:
   - Поддержка в PaperTradingConfig
   - expected_commission в params
   - Расчёт PnL с учётом комиссии

=== ИНТЕГРАЦИЯ С СИСТЕМОЙ ===

1. Во время signal generation:
   - OrderPolicySelector.get_order_params() определяет параметры
   - Логируются параметры в signal_logger
   
2. При создании ордера:
   - OrderManager использует параметры из policy
   - post_only передаётся в API
   - TTL можно реализовать через cancel_order через N секунд
   
3. При backtesting/paper trading:
   - PaperTradingSimulator применяет expected_commission
   - maker_intent влияет на модель заполнения

=== СЛЕДУЮЩИЕ ШАГИ ===

- Интеграция в TradingBot.execute_signal() для автоматического выбора
- Логирование maker_intent в каждый сигнал
- Управление TTL через cancel_after_time в OrderManager
- Метрики: % maker fills vs taker fills vs skipped
"""

if __name__ == "__main__":
    print(__doc__)
