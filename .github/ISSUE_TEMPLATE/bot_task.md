---
name: Bot task (A1..VAL-002) with regression mapping
about: Реализация задачи по боту с обязательной привязкой к REG-ID и тест-планом
title: "[BOT] <кратко: что делаем>"
labels: ["bot", "qa", "copilot"]
assignees: []
---

## Контекст
Ссылка на epic/док/обсуждение:  
- ...

## Цель (что меняем/добавляем)
Опиши ожидаемое поведение и почему это нужно.

## Область изменений (scope)
- Компоненты/модули:
  - [ ] data / features / strategies / meta / risk / execution / position manager / reports
- Поведение, которое **не** должно измениться:
  - ...

## Привязка к регрессу (обязательно)
Указать REG-ID из `docs/qa/regression_bot.md` (и/или `docs/qa/regression_matrix.md`).

### REG-ID, которые должны **пройти** после PR
- [ ] REG-...

### REG-ID, которые должен **покрыть/добавить автотестами** этот PR
- [ ] REG-...

> Если подходящего REG-ID нет — добавь новый в `regression_bot.md` и обнови матрицу.

## План тестирования
Заполни и добавь команды/скрипты.

| Тип | Что гоняем | Где (CI/nightly/manual) | Команда/Workflow |
|---|---|---|---|
| unit | ... | CI | `pytest -q ...` |
| integration | ... | CI/nightly | `python -m ...` / `pytest -q ...` |
| testnet | ... | manual | `gh workflow run testnet-e2e.yml` |

## Definition of Done (DoD)
- [ ] Реализация соответствует цели и контрактам
- [ ] Добавлены/обновлены автотесты под указанные REG-ID
- [ ] Логи/причины решений (`signal/confidence/reasons/values`) не деградировали
- [ ] Все проверки уровня `CI` зелёные
- [ ] Для `nightly/testnet` приложены артефакты (лог/отчёт/скрин openOrders/positions)
- [ ] Обновлена документация (`regression_bot.md` / `regression_matrix.md`) при необходимости

## Артефакты (приложить ссылками/вставками)
- Логи:
- Отчёт paper/backtest:
- Сравнение метрик (если применимо):
- Скрин/JSON Bybit TESTNET (если testnet):

## Риски / углы
- Возможные флейки:
- Граничные условия:
- Rollback план:
