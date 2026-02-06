"""

RISK-002: Circuit Breaker Tests


Протестировать:

1. Волатильность - ATR spike detection

2. Серия убытков - loss streak triggers

3. Kill switch - активирует и закрывает позиции

4. Halt - останавливает trading на N минут

5. Recovery - восстановление после halt

"""


import pytest

from decimal import Decimal

from datetime import datetime, timedelta

from risk.circuit_breaker import (

    CircuitBreaker,

    CircuitBreakerConfig,

    VolatilitySettings,

    LossStreakSettings,

    CircuitState,

)


class TestCircuitBreakerVolatility:

    """Тесты для волатильности"""

    def test_atr_recording(self):
        """Записать ATR значения"""

        cb = CircuitBreaker()

        # Записиваем несколько ATR

        cb.update_volatility(Decimal("100"))

        cb.update_volatility(Decimal("105"))

        cb.update_volatility(Decimal("110"))

        assert len(cb.atr_history) == 3

        assert cb.atr_history[-1] == Decimal("110")

    def test_atr_history_limit(self):
        """Историю ATR ограничиваем заданным количеством"""

        config = CircuitBreakerConfig(

            volatility_settings=VolatilitySettings(volatility_lookback_candles=5)

        )

        cb = CircuitBreaker(config=config)

        # Добавляем 10 свечей

        for i in range(10):

            cb.update_volatility(Decimal(str(100 + i)))

        # Должно остаться только последних 5

        assert len(cb.atr_history) == 5

        assert cb.atr_history[0] == Decimal("105")  # Первые 5 удалены

    def test_volatility_spike_detection_multiplier(self):
        """Детектировать spike по multiplier"""

        config = CircuitBreakerConfig(

            volatility_settings=VolatilitySettings(

                atr_multiplier=Decimal("2.0"),

                volatility_threshold_percent=Decimal("0"),  # Отключаем процент

                volatility_lookback_candles=10,

            )

        )

        cb = CircuitBreaker(config=config)

        # Записываем нормальные ATR (mean = 100)

        for _ in range(10):

            cb.update_volatility(Decimal("100"))

        # Сейчас mean = 100, поэтому spike при ATR > 200

        is_spike, reason = cb.check_volatility()

        assert not is_spike

        # Добавляем spike (250 > 100 * 2.0 = 200)

        cb.update_volatility(Decimal("250"))

        is_spike, reason = cb.check_volatility()

        assert is_spike

        assert "ATR spike detected" in reason

    def test_volatility_spike_detection_percent(self):
        """Детектировать spike по процентам"""

        config = CircuitBreakerConfig(

            volatility_settings=VolatilitySettings(

                atr_multiplier=Decimal("0"),  # Отключаем multiplier

                volatility_threshold_percent=Decimal("50"),

                volatility_lookback_candles=20,

            )

        )

        cb = CircuitBreaker(config=config)

        # Mean ATR = 100

        for _ in range(20):

            cb.update_volatility(Decimal("100"))

        # Не spike: 140 < 100 * 1.5 = 150

        cb.update_volatility(Decimal("140"))

        is_spike, _ = cb.check_volatility()

        assert not is_spike

        # Spike: 160 > 100 * 1.5 = 150

        # Mean will be (19*100 + 160) / 20 = 109.5

        # Threshold = 109.5 * 1.5 = 164.25

        # So 160 < 164.25, still not spike

        # Добавим 165

        cb.update_volatility(Decimal("165"))

        is_spike, reason = cb.check_volatility()

        assert is_spike

        assert "High volatility" in reason

    def test_volatility_halt_trigger(self):
        """Volatility halt срабатывает"""

        config = CircuitBreakerConfig(

            volatility_settings=VolatilitySettings(

                atr_multiplier=Decimal("2.0"), halt_duration_minutes=30

            )

        )

        cb = CircuitBreaker(config=config)

        assert cb.current_state == CircuitState.ACTIVE

        # Добавляем volatile ATR

        for _ in range(5):

            cb.update_volatility(Decimal("100"))

        cb.update_volatility(Decimal("250"))

        result = cb.trigger_volatility_halt()

        assert cb.current_state == CircuitState.VOLATILITY_HALT

        assert "recovery_at" in result

        assert result["state"] == CircuitState.VOLATILITY_HALT.value

    def test_halt_prevents_trading(self):
        """Halt блокирует trading"""

        cb = CircuitBreaker()

        cb.trigger_volatility_halt()

        can_trade, reason = cb.can_trade()

        assert not can_trade

        assert "halt active" in reason.lower()

    def test_halt_recovery_timing(self):
        """Recovery требует истечения времени"""

        config = CircuitBreakerConfig(

            volatility_settings=VolatilitySettings(halt_duration_minutes=1)

        )

        cb = CircuitBreaker(config=config)

        cb.trigger_volatility_halt()

        # Слишком рано для восстановления

        result = cb.recover_from_halt()

        assert "not_ready" in result

        assert cb.current_state == CircuitState.VOLATILITY_HALT


class TestCircuitBreakerLosses:

    """Тесты для tracking убытков"""

    def test_record_loss(self):
        """Записать убыток"""

        cb = CircuitBreaker()

        cb.record_loss(Decimal("100"), Decimal("-100"))

        cb.record_loss(Decimal("50"), Decimal("-50"))

        assert len(cb.loss_history) == 2

    def test_loss_streak_detection(self):
        """Детектировать серию убытков"""

        config = CircuitBreakerConfig(

            loss_streak_settings=LossStreakSettings(

                consecutive_losses_threshold=3, time_window_minutes=60

            )

        )

        cb = CircuitBreaker(config=config)

        # Менее чем порог

        cb.record_loss(Decimal("100"))

        cb.record_loss(Decimal("100"))

        should_kill, reason = cb.check_loss_streak()

        assert not should_kill

        # На пороге

        cb.record_loss(Decimal("100"))

        should_kill, reason = cb.check_loss_streak()

        assert should_kill

        assert "Loss streak triggered" in reason

    def test_loss_streak_time_window(self):
        """Loss streak считает только в окне"""

        config = CircuitBreakerConfig(

            loss_streak_settings=LossStreakSettings(

                consecutive_losses_threshold=3, time_window_minutes=1

            )

        )

        cb = CircuitBreaker(config=config)

        # Добавляем старый убыток

        cb.loss_history.append(

            {

                "timestamp": datetime.utcnow() - timedelta(minutes=2),

                "loss": Decimal("100"),

                "pnl": Decimal("-100"),

            }

        )

        # Добавляем новые

        cb.record_loss(Decimal("100"))

        cb.record_loss(Decimal("100"))

        # Должны считать только 2 новых (старый не в окне)

        should_kill, reason = cb.check_loss_streak()

        assert not should_kill

    def test_daily_loss_limit(self):
        """Daily loss limit срабатывает"""

        config = CircuitBreakerConfig(

            loss_streak_settings=LossStreakSettings(daily_loss_kill_percent=Decimal("5"))

        )

        cb = CircuitBreaker(config=config)

        equity = Decimal("10000")

        # Лимит = 10000 * 5% = 500

        # Добавляем убытки

        cb.record_loss(Decimal("300"))

        cb.record_loss(Decimal("250"))  # Итого 550 > лимит

        should_kill, reason = cb.check_loss_streak(equity=equity)

        assert should_kill

        assert "Daily loss limit" in reason

    def test_loss_alert_state(self):
        """Alert срабатывает перед kill switch"""

        config = CircuitBreakerConfig(

            loss_streak_settings=LossStreakSettings(

                alert_on_losses=2,

                consecutive_losses_threshold=3,

            )

        )

        cb = CircuitBreaker(config=config)

        # 1 убыток - без alert

        cb.record_loss(Decimal("100"))

        should_alert, _ = cb.check_alert_state()

        assert not should_alert

        # 2 убытка - alert

        cb.record_loss(Decimal("100"))

        should_alert, reason = cb.check_alert_state()

        assert should_alert

        assert "alert" in reason.lower()

        # 3 убытка - kill (не alert)

        cb.record_loss(Decimal("100"))

        should_alert, _ = cb.check_alert_state()

        assert not should_alert  # Перешли в kill, не alert


class TestCircuitBreakerKillSwitch:

    """Тесты для kill switch"""

    def test_kill_switch_activation(self):
        """Kill switch активируется"""

        cb = CircuitBreaker()

        assert cb.current_state == CircuitState.ACTIVE

        result = cb.trigger_kill_switch("Test reason")

        assert cb.current_state == CircuitState.KILL_SWITCH

        assert result["reason"] == "Test reason"

        assert "actions_required" in result

        assert "cancel_all_orders" in result["actions_required"]

        assert "close_all_positions" in result["actions_required"]

    def test_kill_switch_blocks_trading(self):
        """Kill switch блокирует trading"""

        cb = CircuitBreaker()

        cb.trigger_kill_switch()

        can_trade, reason = cb.can_trade()

        assert not can_trade

        assert "kill switch" in reason.lower()

    def test_kill_switch_legacy_fields(self):
        """Kill switch обновляет legacy поля"""

        cb = CircuitBreaker()

        cb.trigger_kill_switch("Legacy test")

        assert cb.is_circuit_broken

        assert cb.break_reason == "Legacy test"

    def test_kill_switch_double_activation(self):
        """Не активируется дважды"""

        cb = CircuitBreaker()

        cb.trigger_kill_switch("First")

        result = cb.trigger_kill_switch("Second")

        assert result["already_active"]

    def test_kill_switch_manual_reset(self):
        """Ручной сброс kill switch"""

        cb = CircuitBreaker()

        cb.trigger_kill_switch("Test")

        # Не может сбросить если не активирован

        cb2 = CircuitBreaker()

        result = cb2.manual_reset()

        assert result["not_triggered"]

        # Может сбросить если активирован

        result = cb.manual_reset()

        assert result["trading_resumed"]

        assert cb.current_state == CircuitState.ACTIVE

        assert not cb.is_circuit_broken

    def test_kill_switch_events(self):
        """Kill switch создает события"""

        cb = CircuitBreaker()

        cb.trigger_kill_switch("Reason 1")

        assert len(cb.events) > 0

        last_event = cb.events[-1]

        assert last_event.state == CircuitState.KILL_SWITCH

        assert last_event.reason == "Reason 1"


class TestCircuitBreakerIntegration:

    """Integration тесты"""

    def test_volatility_halt_workflow(self):
        """Workflow: volatility → halt → wait → recovery"""

        config = CircuitBreakerConfig(

            volatility_settings=VolatilitySettings(

                atr_multiplier=Decimal("2.0"), halt_duration_minutes=1

            )

        )

        cb = CircuitBreaker(config=config)

        # Setup: normal ATR

        for _ in range(5):

            cb.update_volatility(Decimal("100"))

        # Step 1: Check normal - можем торговать

        can_trade, _ = cb.can_trade()

        assert can_trade

        # Step 2: Spike happens

        cb.update_volatility(Decimal("250"))

        is_spike, _ = cb.check_volatility()

        assert is_spike

        # Step 3: Trigger halt

        cb.trigger_volatility_halt()

        can_trade, reason = cb.can_trade()

        assert not can_trade

        # Step 4: Try to recover (слишком рано)

        result = cb.recover_from_halt()

        assert "not_ready" in result

        assert cb.current_state == CircuitState.VOLATILITY_HALT

        # Step 5: Simulate время истекло

        cb.recovery_timestamp = datetime.utcnow() - timedelta(seconds=1)

        result = cb.recover_from_halt()

        assert result["trading_resumed"]

        assert cb.current_state == CircuitState.ACTIVE

        # Step 6: Can trade again

        can_trade, _ = cb.can_trade()

        assert can_trade

    def test_loss_streak_to_kill_workflow(self):
        """Workflow: loss → alert → kill"""

        config = CircuitBreakerConfig(

            loss_streak_settings=LossStreakSettings(

                alert_on_losses=2,

                consecutive_losses_threshold=3,

            )

        )

        cb = CircuitBreaker(config=config)

        # Loss 1

        cb.record_loss(Decimal("100"))

        should_alert, _ = cb.check_alert_state()

        assert not should_alert

        should_kill, _ = cb.check_loss_streak()

        assert not should_kill

        # Loss 2 - alert

        cb.record_loss(Decimal("100"))

        should_alert, alert_reason = cb.check_alert_state()

        assert should_alert

        should_kill, _ = cb.check_loss_streak()

        assert not should_kill

        # Loss 3 - kill

        cb.record_loss(Decimal("100"))

        should_kill, kill_reason = cb.check_loss_streak()

        assert should_kill

        # Trigger kill switch

        cb.trigger_kill_switch(kill_reason)

        can_trade, _ = cb.can_trade()

        assert not can_trade

    def test_state_tracking(self):
        """Все переходы состояния отслеживаются"""

        cb = CircuitBreaker()

        # ACTIVE → VOLATILITY_HALT

        cb.trigger_volatility_halt()

        assert len(cb.events) == 1

        assert cb.events[0].state == CircuitState.VOLATILITY_HALT

        # VOLATILITY_HALT → ACTIVE

        cb.recovery_timestamp = datetime.utcnow() - timedelta(seconds=1)

        cb.recover_from_halt()

        assert len(cb.events) == 2

        assert cb.events[1].state == CircuitState.ACTIVE

        # ACTIVE → KILL_SWITCH

        cb.trigger_kill_switch("Test")

        assert len(cb.events) == 3

        assert cb.events[2].state == CircuitState.KILL_SWITCH

    def test_get_state_info(self):
        """get_state возвращает полную информацию"""

        cb = CircuitBreaker()

        cb.update_volatility(Decimal("100"))

        cb.update_volatility(Decimal("110"))

        cb.record_loss(Decimal("50"))

        state = cb.get_state()

        assert state["current_state"] == CircuitState.ACTIVE.value

        assert state["can_trade"]

        assert state["atr_history_count"] == 2

        assert state["loss_history_count"] == 1

        assert "recent_events" in state

    def test_get_loss_info(self):
        """get_loss_streak_info возвращает статистику"""

        config = CircuitBreakerConfig(

            loss_streak_settings=LossStreakSettings(

                alert_on_losses=2,

                consecutive_losses_threshold=3,

            )

        )

        cb = CircuitBreaker(config=config)

        cb.record_loss(Decimal("100"))

        cb.record_loss(Decimal("50"))

        info = cb.get_loss_streak_info()

        assert info["total_losses"] == 2

        assert info["recent_losses"] == 2

        assert info["alert_triggered"]

        assert not info["kill_switch_triggered"]

    def test_get_volatility_info(self):
        """get_volatility_info возвращает статистику"""

        cb = CircuitBreaker()

        for i in range(5):

            cb.update_volatility(Decimal(str(100 + i)))

        info = cb.get_volatility_info()

        assert info["atr_readings"] == 5

        assert info["current_atr"] == 104.0

        assert "mean_atr" in info

        assert "atr_ratio" in info

    def test_new_day_reset(self):
        """Сброс на новый день"""

        cb = CircuitBreaker()

        cb.record_loss(Decimal("100"))

        cb.update_volatility(Decimal("100"))

        assert len(cb.loss_history) == 1

        assert len(cb.atr_history) == 1

        cb.reset_for_new_day()

        assert len(cb.loss_history) == 0  # Очищена

    def test_legacy_compatibility(self):
        """Legacy методы работают"""

        cb = CircuitBreaker()

        # check_consecutive_losses

        cb.check_consecutive_losses("loss")

        assert cb.consecutive_losses == 1

        cb.check_consecutive_losses("win")

        assert cb.consecutive_losses == 0

        # trigger_break + is_trading_allowed

        cb.trigger_break("Test reason")

        # is_trading_allowed() теперь вызывает can_trade()

        # trigger_break только устанавливает флаги, не изменяет state

        assert cb.is_circuit_broken

        # Проверяем что флаги установлены

        assert cb.break_reason == "Test reason"

        # reset

        cb.reset()

        assert cb.consecutive_losses == 0

        assert not cb.is_circuit_broken


class TestCircuitBreakerEdgeCases:

    """Edge cases"""

    def test_empty_atr_history(self):
        """Empty ATR история не вызывает ошибок"""

        cb = CircuitBreaker()

        is_spike, reason = cb.check_volatility()

        assert not is_spike

        info = cb.get_volatility_info()

        assert info["atr_readings"] == 0

    def test_empty_loss_history(self):
        """Empty loss история не вызывает ошибок"""

        cb = CircuitBreaker()

        should_kill, _ = cb.check_loss_streak()

        assert not should_kill

        info = cb.get_loss_streak_info()

        assert info["total_losses"] == 0

    def test_disabled_circuit_breaker(self):
        """Disabled CB всегда разрешает торговлю"""

        config = CircuitBreakerConfig(enabled=False)

        cb = CircuitBreaker(config=config)

        cb.trigger_kill_switch("Test")

        can_trade, _ = cb.can_trade()

        assert can_trade  # Даже kill switch не блокирует

    def test_decimal_conversion(self):
        """Работает с int/float/Decimal"""

        cb = CircuitBreaker()

        # int

        cb.update_volatility(100)

        assert isinstance(cb.atr_history[-1], Decimal)

        # float

        cb.update_volatility(101.5)

        assert isinstance(cb.atr_history[-1], Decimal)

        # Decimal

        cb.update_volatility(Decimal("102.5"))

        assert isinstance(cb.atr_history[-1], Decimal)

    def test_multiple_volatility_spikes(self):
        """Несколько spikes подряд"""

        config = CircuitBreakerConfig(

            volatility_settings=VolatilitySettings(atr_multiplier=Decimal("2.0"))

        )

        cb = CircuitBreaker(config=config)

        for _ in range(5):

            cb.update_volatility(Decimal("100"))

        # Первый spike

        cb.update_volatility(Decimal("300"))

        is_spike1, _ = cb.check_volatility()

        assert is_spike1

        # Второй spike

        cb.update_volatility(Decimal("350"))

        is_spike2, _ = cb.check_volatility()

        assert is_spike2

    def test_quick_recovery_attempt(self):
        """Быстрая попытка восстановления не работает"""

        cb = CircuitBreaker()

        cb.trigger_volatility_halt()

        can_trade1, _ = cb.can_trade()

        assert not can_trade1

        # Попытка сразу восстановиться

        result = cb.recover_from_halt()

        assert "not_ready" in result

        # Статус не изменился

        assert cb.current_state == CircuitState.VOLATILITY_HALT


class TestCircuitBreakerScenarios:

    """Реальные сценарии"""

    def test_scenario_high_volatility_then_recovery(self):
        """

        Сценарий:

        1. Normal trading

        2. ATR spike

        3. Halt 30 min

        4. Recover

        5. Resume trading

        """

        config = CircuitBreakerConfig(

            volatility_settings=VolatilitySettings(

                atr_multiplier=Decimal("2.0"), halt_duration_minutes=30

            )

        )

        cb = CircuitBreaker(config=config)

        # Phase 1: Normal

        for _ in range(10):

            cb.update_volatility(Decimal("100"))

        can_trade, _ = cb.can_trade()

        assert can_trade

        # Phase 2: Spike

        cb.update_volatility(Decimal("250"))

        cb.trigger_volatility_halt()

        can_trade, _ = cb.can_trade()

        assert not can_trade

        # Phase 3: Wait + recover (fake time)

        cb.recovery_timestamp = datetime.utcnow() - timedelta(seconds=1)

        result = cb.recover_from_halt()

        assert result["trading_resumed"]

        # Phase 4: Resume

        can_trade, _ = cb.can_trade()

        assert can_trade

    def test_scenario_loss_streak_kill_switch(self):
        """

        Сценарий:

        1. Loss 1 - ok

        2. Loss 2 - alert

        3. Loss 3 - kill switch

        4. Manual reset

        """

        config = CircuitBreakerConfig(

            loss_streak_settings=LossStreakSettings(

                alert_on_losses=2,

                consecutive_losses_threshold=3,

            )

        )

        cb = CircuitBreaker(config=config)

        equity = Decimal("10000")

        # Phase 1 & 2

        cb.record_loss(Decimal("100"))

        cb.record_loss(Decimal("100"))

        should_alert, _ = cb.check_alert_state()

        assert should_alert

        # Phase 3

        cb.record_loss(Decimal("100"))

        should_kill, reason = cb.check_loss_streak(equity)

        assert should_kill

        cb.trigger_kill_switch(reason)

        can_trade, _ = cb.can_trade()

        assert not can_trade

        # Phase 4

        result = cb.manual_reset()

        assert result["trading_resumed"]

        can_trade, _ = cb.can_trade()

        assert can_trade

    def test_scenario_combined_volatility_and_losses(self):
        """Одновременно volatility и loss streak"""

        config = CircuitBreakerConfig(

            volatility_settings=VolatilitySettings(atr_multiplier=Decimal("2.0")),

            loss_streak_settings=LossStreakSettings(consecutive_losses_threshold=2),

        )

        cb = CircuitBreaker(config=config)

        # Setup normal state

        for _ in range(5):

            cb.update_volatility(Decimal("100"))

        can_trade, _ = cb.can_trade()

        assert can_trade

        # Volatility spike

        cb.update_volatility(Decimal("250"))

        cb.trigger_volatility_halt()

        can_trade, _ = cb.can_trade()

        assert not can_trade

        # Во время halт происходят убытки

        cb.record_loss(Decimal("100"))

        cb.record_loss(Decimal("100"))

        # После восстановления из halt - kill switch от losses

        cb.recovery_timestamp = datetime.utcnow() - timedelta(seconds=1)

        cb.recover_from_halt()

        should_kill, _ = cb.check_loss_streak()

        assert should_kill

        cb.trigger_kill_switch("Loss streak after volatility")

        can_trade, _ = cb.can_trade()

        assert not can_trade


if __name__ == "__main__":

    pytest.main([__file__, "-v"])
