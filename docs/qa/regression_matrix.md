# Матрица регресса: REG-ID → тип теста → где запускается

Источник: `docs/qa/regression_bot.md`  
Цель: быстро понять, **какие проверки** должны быть покрыты автотестами и **где** их гонять.

## Легенда
- **Тип теста**
  - `unit` — чистая логика/математика/контракты, без сети и времени
  - `integration` — пайплайны/симуляции/бэктесты, работа с файлами/БД, но без реальной биржи
  - `testnet` — реальная интеграция с Bybit TESTNET (секреты, сеть, нестабильность)
- **Запуск**
  - `CI` — на каждый PR (быстро и детерминированно)
  - `nightly` — по расписанию (дольше/тяжелее)
  - `manual` — вручную (или отдельный `workflow_dispatch`), обычно требует ключей/рынка

> Примечание: тесты `testnet` **можно** перевести в `nightly`, если настроены секреты и есть бюджет на флейки.

## Таблица

| REG-ID | Тип теста | Запуск | Описание |
|---|---|---|---|
| SMK-01 | integration | manual | Бот стартует без исключений, конфиг читается, видны версии/параметры запуска. |
| SMK-02 | integration | manual | Market data грузится (OHLCV не пустой), последняя свеча свежая. |
| SMK-03 | integration | manual | FeaturePipeline считает ключевые фичи без NaN на хвосте (`atr`, `rsi`, `adx`, BB width и т.п.). |
| SMK-04 | integration | manual | В режиме `paper` генерируются и применяются сделки (не “просто лог”). |
| SMK-05 | testnet | manual | В TESTNET приватный вызов работает (balance/positions/создание ордера). |
| SMK-06 | testnet | manual | Kill switch можно активировать вручную и он реально закрывает риск. |
| REG-A1-01 | integration | CI | Загрузка свечей для всех MTF-TF |
| REG-A1-02 | integration | CI | MTF принимает сигналы по скорингу (если внедрён META-001) |
| REG-A1-03 | integration | CI | Поведение при `use_mtf=false` |
| REG-A2-01 | unit | CI | Каноничные колонки присутствуют |
| REG-A2-02 | unit | CI | RegimeSwitcher читает те же имена |
| REG-A2-03 | unit | CI | Стратегии читают те же имена |
| REG-A3-01 | unit | CI | RSI диапазон 0..100 и без NaN на хвосте |
| REG-A3-02 | unit | CI | Mean Reversion перестаёт быть “всегда neutral” |
| REG-A4-01 | unit | CI | Volume filter блокирует вход при низком объёме |
| REG-A4-02 | unit | CI | Volatility filter блокирует вход без expansion |
| REG-B1-01 | unit | CI | Live-ветка проходит до place_order без исключений (mock) |
| REG-B1-02 | testnet | manual | Live-ветка на TESTNET с “микро-ордером” |
| REG-B2-01 | testnet | manual | Приватный GET работает стабильно |
| REG-B2-02 | testnet | manual | Приватный POST place_order проходит (TESTNET) |
| REG-B2-03 | testnet | manual | Отмена ордера (POST) работает |
| REG-B3-01 | unit | CI | Округление price по tickSize |
| REG-B3-02 | unit | CI | Округление qty по qtyStep + minQty/minNotional |
| REG-B3-03 | testnet | manual | Ордер не отклоняется биржей по “invalid qty/price” |
| REG-C1-01 | integration | CI | Открытие позиции → запись state |
| REG-C1-02 | testnet | manual | Reconcile: ручное закрытие на бирже |
| REG-C1-03 | testnet | manual | Partial fills корректно отражаются в state |
| REG-C2-01 | testnet | manual | При входе выставляются SL/TP (если биржевые) |
| REG-C2-02 | integration | CI | Виртуальные SL/TP (если выбран виртуальный подход) |
| REG-C2-03 | integration | CI | Stop distance привязан к ATR (vol-based) |
| REG-C3-01 | integration | CI | Ignore при наличии позиции |
| REG-C3-02 | integration | CI | Add (пирамидинг) по правилам (если включено) |
| REG-C3-03 | integration | CI | Flip (если разрешено) |
| REG-D1-01 | testnet | manual | Kill switch отменяет все ордера |
| REG-D1-02 | testnet | manual | Kill switch закрывает позицию |
| REG-D1-03 | integration | CI | Halted режим — бот не торгует |
| REG-D2-01 | unit | CI | Max leverage enforced |
| REG-D2-02 | unit | CI | Max notional/exposure enforced |
| REG-D2-03 | integration | CI | Daily loss limit → kill switch |
| REG-D3-01 | integration | CI | При одинаковом equity риск в USD стабилен |
| REG-E1-01 | integration | nightly | Paper открывает/закрывает позиции и считает PnL |
| REG-E1-02 | integration | nightly | Stop/Take работают в paper |
| REG-E2-01 | integration | nightly | Backtest запускается и генерирует отчёт |
| REG-E2-02 | integration | nightly | Out-of-sample разделение реально работает |
| REG-F1-01 | unit | CI | Любое решение содержит signal/confidence/reasons/values |
| REG-STR-001 | unit | CI | Каждая стратегия возвращает stop/take и они валидны |
| REG-STR-002 | unit | CI | “Ликвидационная свеча” → cooldown |
| REG-STR-003-A | unit | CI | confirm_close требует подтверждения |
| REG-STR-003-B | integration | CI | limit_retest ставит лимитку и TTL работает |
| REG-STR-004 | unit | CI | MR в тренде не торгует |
| REG-STR-005 | integration | CI | Time stop закрывает позицию |
| REG-STR-006 | unit | CI | Без squeeze/expansion/volume входа нет |
| REG-STR-007 | integration | CI | Ретест обязателен и TTL ожидания работает |
| REG-META-001 | unit | CI | Сигнал не “умирает”, а получает скоринг |
| REG-META-002-01 | unit | CI | Режим high_vol_event |
| REG-META-002-02 | unit | CI | Trend vs Range различаются устойчиво |
| REG-EXE-001 | integration | CI | Стратегии выбирают корректный order type |
| REG-EXE-002-01 | testnet | manual | Partial fill обновляет state, нет рассинхрона |
| REG-EXE-002-02 | unit | CI | Любое закрытие позиции — reduceOnly |
| REG-EXE-003 | integration | nightly | Slippage влияет на PnL |
| REG-RISK-001-01 | unit | CI | Risk_usd соответствует конфигу |
| REG-RISK-001-02 | unit | CI | Caps блокируют превышение |
| REG-RISK-002-01 | integration | CI | Volatility breaker |
| REG-RISK-002-02 | integration | CI | Loss streak breaker |
| REG-VAL-001-01 | integration | nightly | Один и тот же сигнал на одинаковых данных |
| REG-VAL-001-02 | integration | nightly | Метрики отчёта присутствуют и корректны |
| REG-VAL-002-01 | integration | nightly | Sweep запускается и сохраняет результаты |
| REG-VAL-002-02 | integration | nightly | Отбор по устойчивости между периодами |
