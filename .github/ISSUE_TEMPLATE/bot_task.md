---
name: Bot Task (с привязкой к регрессу)
about: Задача для Copilot/разработчика с обязательной привязкой к REG-ID
title: "[BOT] <кратко: что делаем>"
labels: ["bot", "enhancement"]
assignees: []
---

## Контекст
Коротко: **что ломает / что улучшаем / почему сейчас не ок**.

## Цель
Ожидаемое поведение после изменения (1–3 пункта).

## Scope
**Входит:**
- ...
**Не входит:**
- ...

## Связанные REG-ID (обязательное)
Укажите, какие пункты из `docs/qa/regression_bot.md` должны пройти после выполнения задачи:

- [ ] REG-...  
- [ ] REG-...

> Совет: берите REG-ID из `docs/qa/regression_matrix.md`, чтобы сразу понимать тип теста и где его гонять.

## Требование к тестам (обязательное)
Какие проверки должны быть **автоматизированы** и добавлены в репозиторий:

- [ ] Unit tests (быстро, детерминированно): `tests/...`
- [ ] Integration tests (fixtures/paper/backtest короткие): `tests/...`
- [ ] Testnet checks (manual/workflow_dispatch): приложить артефакты (лог/JSON/скрин openOrders/positions)

## План реализации (шаги)
1. ...
2. ...
3. ...

## Acceptance Criteria (DoD)
- [ ] Реализация завершена
- [ ] Добавлены/обновлены тесты, покрывающие REG-ID из списка
- [ ] Все REG-ID из списка **проходят**
- [ ] CI зелёный (unit + integration)
- [ ] Для testnet-пунктов приложены артефакты (логи/ответы API)

## Как проверить (локально)
Пример (подстройте под проект):
- `pytest -q`
- `pytest -q tests/regression -k <ID|section>`
- `python -m app.scripts.paper_run --config ...` (если есть)
- `python -m app.scripts.backtest --config ...` (если есть)
- Testnet: `python -m app.scripts.smoke_place_order --testnet ...`

## Артефакты
- Логи:
- Отчёты (paper/backtest):
- Ссылка на PR:
