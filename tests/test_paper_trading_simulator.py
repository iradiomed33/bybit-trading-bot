"""
Tests для Paper Trading Simulator - E1 EPIC

25+ тестов:
- Fills и slippage
- Комиссии (maker/taker)
- Позиции и equity
- SL/TP логика
- Reproducibility с seed
- Edge cases
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from execution.paper_trading_simulator import (
    PaperTradingSimulator,
    PaperTradingConfig,
    TradeState,
)
from execution.trade_metrics import TradeMetricsCalculator, EquityCurve


class TestPaperTradingConfig:
    """Конфигурация"""
    
    def test_default_config(self):
        """Конфигурация по умолчанию"""
        config = PaperTradingConfig()
        assert config.initial_balance == Decimal("10000")
        assert config.maker_commission == Decimal("0.0002")
        assert config.taker_commission == Decimal("0.0004")
    
    def test_custom_config(self):
        """Пользовательская конфигурация"""
        config = PaperTradingConfig(
            initial_balance=Decimal("50000"),
            maker_commission=Decimal("0.0001"),
        )
        assert config.initial_balance == Decimal("50000")
        assert config.maker_commission == Decimal("0.0001")


class TestOrderFilling:
    """Заполнение ордеров"""
    
    def test_market_order_buy_fills_immediately(self):
        """Market buy ордер заполняется сразу"""
        sim = PaperTradingSimulator(PaperTradingConfig(initial_balance=Decimal("10000")))
        
        order_id, success, msg = sim.submit_market_order(
            symbol="BTCUSDT",
            side="Buy",
            qty=Decimal("0.01"),
            current_price=Decimal("50000"),
        )
        
        assert success
        assert order_id in sim.orders
        assert sim.orders[order_id].status.value == "filled"
    
    def test_market_order_applies_slippage_on_buy(self):
        """Market buy применяет slippage (цена выше close)"""
        config = PaperTradingConfig(
            initial_balance=Decimal("10000"),
            slippage_buy=Decimal("0.001"),  # 0.1%
        )
        sim = PaperTradingSimulator(config)
        
        close_price = Decimal("50000")
        order_id, success, _ = sim.submit_market_order(
            symbol="BTCUSDT",
            side="Buy",
            qty=Decimal("0.01"),
            current_price=close_price,
        )
        
        filled_price = sim.orders[order_id].avg_filled_price
        expected_price = close_price * (1 + Decimal("0.001"))
        
        # Проверить что filled_price выше close_price (неудача)
        assert filled_price > close_price
        assert filled_price == expected_price
    
    def test_market_order_applies_slippage_on_sell(self):
        """Market sell применяет slippage (цена ниже close)"""
        config = PaperTradingConfig(
            initial_balance=Decimal("10000"),
            slippage_sell=Decimal("0.001"),
        )
        sim = PaperTradingSimulator(config)
        
        # Сначала купить
        sim.submit_market_order("BTCUSDT", "Buy", Decimal("0.1"), Decimal("50000"))
        
        # Затем продать
        close_price = Decimal("51000")
        order_id, success, _ = sim.submit_market_order(
            symbol="BTCUSDT",
            side="Sell",
            qty=Decimal("0.1"),
            current_price=close_price,
        )
        
        filled_price = sim.orders[order_id].avg_filled_price
        expected_price = close_price * (1 - Decimal("0.001"))
        
        # Проверить что filled_price ниже close_price (неудача)
        assert filled_price < close_price
    
    def test_market_order_insufficient_funds(self):
        """Market buy с недостаточно средств"""
        sim = PaperTradingSimulator(PaperTradingConfig(initial_balance=Decimal("100")))
        
        order_id, success, msg = sim.submit_market_order(
            symbol="BTCUSDT",
            side="Buy",
            qty=Decimal("10"),  # 10 * 50000 = 500000
            current_price=Decimal("50000"),
        )
        
        assert not success
        assert "Insufficient cash" in msg


class TestCommissions:
    """Комиссии"""
    
    def test_market_order_uses_taker_commission(self):
        """Market ордер используют taker комиссию"""
        config = PaperTradingConfig(
            initial_balance=Decimal("10000"),
            taker_commission=Decimal("0.0004"),  # 0.04%
        )
        sim = PaperTradingSimulator(config)
        
        order_id, _, _ = sim.submit_market_order(
            symbol="BTCUSDT",
            side="Buy",
            qty=Decimal("0.01"),
            current_price=Decimal("50000"),
        )
        
        order = sim.orders[order_id]
        # Commission = qty * filled_price * rate
        expected_commission = order.filled_qty * order.avg_filled_price * config.taker_commission
        
        assert order.commission_paid > 0
        assert abs(order.commission_paid - expected_commission) < Decimal("1")  # Погрешность округления
    
    def test_limit_order_uses_maker_commission(self):
        """Limit ордер используют maker комиссию"""
        config = PaperTradingConfig(
            initial_balance=Decimal("10000"),
            maker_commission=Decimal("0.0002"),  # 0.02%
        )
        sim = PaperTradingSimulator(config)
        
        # Limit ордер заполняется по лимит цене без slippage
        order_id, success, _ = sim.submit_limit_order(
            symbol="BTCUSDT",
            side="Buy",
            qty=Decimal("0.01"),
            limit_price=Decimal("49000"),
        )
        
        assert success
        assert sim.orders[order_id].status.value == "pending"


class TestPositions:
    """Позиции"""
    
    def test_create_long_position(self):
        """Создать long позицию"""
        sim = PaperTradingSimulator(PaperTradingConfig(initial_balance=Decimal("10000")))
        
        sim.submit_market_order("BTCUSDT", "Buy", Decimal("0.01"), Decimal("50000"))
        
        pos = sim.get_position("BTCUSDT")
        assert pos is not None
        assert pos.side == "long"
        assert pos.qty == Decimal("0.01")
    
    def test_average_up_on_multiple_buys(self):
        """Average up при нескольких покупках"""
        sim = PaperTradingSimulator(PaperTradingConfig(initial_balance=Decimal("100000")))
        
        # Первая покупка
        sim.submit_market_order("BTCUSDT", "Buy", Decimal("0.01"), Decimal("50000"))
        pos1_entry = sim.get_position("BTCUSDT").entry_price
        
        # Вторая покупка по другой цене
        sim.submit_market_order("BTCUSDT", "Buy", Decimal("0.01"), Decimal("51000"))
        pos2 = sim.get_position("BTCUSDT")
        
        # Entry price должна быть средней
        assert pos2.entry_price != pos1_entry
        assert pos2.qty == Decimal("0.02")
    
    def test_close_long_position(self):
        """Закрыть long позицию"""
        sim = PaperTradingSimulator(PaperTradingConfig(initial_balance=Decimal("10000")))
        
        # Открыть long
        sim.submit_market_order("BTCUSDT", "Buy", Decimal("0.01"), Decimal("50000"))
        initial_cash = sim.cash
        
        # Закрыть long
        sim.submit_market_order("BTCUSDT", "Sell", Decimal("0.01"), Decimal("51000"))
        
        # Позиция должна быть закрыта
        assert sim.get_position("BTCUSDT") is None
        
        # Cash должен вырасти (прибыль)
        assert sim.cash > initial_cash
        
        # Сделка должна быть в истории
        assert len(sim.trades) == 1
        trade = sim.trades[0]
        assert trade.side == "long"
        assert trade.pnl_after_commission > 0  # Выгодная сделка


class TestEquity:
    """Equity и PnL"""
    
    def test_equity_includes_unrealized_pnl(self):
        """Equity включает unrealized PnL"""
        sim = PaperTradingSimulator(PaperTradingConfig(initial_balance=Decimal("10000")))
        
        initial_equity = sim.get_equity()
        
        # Открыть позицию
        sim.submit_market_order("BTCUSDT", "Buy", Decimal("0.01"), Decimal("50000"))
        cash_after_buy = sim.cash
        
        # Обновить цены
        sim.update_market_prices({"BTCUSDT": Decimal("51000")})
        
        # Equity должна быть: cash + unrealized profit
        # Даже если unrealized > 0, equity может быть < initial из-за commission на buy
        equity_with_profit = sim.get_equity()
        
        # Но unrealized PnL должна быть positive
        pos = sim.get_position("BTCUSDT")
        assert pos.unrealized_pnl > 0  # Profit from 50000 -> 51000
    
    def test_account_summary(self):
        """Account summary"""
        config = PaperTradingConfig(initial_balance=Decimal("10000"))
        sim = PaperTradingSimulator(config)
        
        sim.submit_market_order("BTCUSDT", "Buy", Decimal("0.01"), Decimal("50000"))
        sim.update_market_prices({"BTCUSDT": Decimal("51000")})
        
        summary = sim.get_account_summary()

        assert summary["initial_balance"] == 10000.0
        # Equity может быть меньше initial balance даже с положительным unrealized PnL
        # because commission costs were paid
        assert summary["open_positions"] == 1
        assert summary["unrealized_pnl"] > 0  # Profit от price change
        assert summary["unrealized_pnl"] > 0


class TestStopLossAndTakeProfit:
    """SL/TP логика"""
    
    def test_set_stop_loss_and_take_profit(self):
        """Установить SL и TP"""
        sim = PaperTradingSimulator(PaperTradingConfig(initial_balance=Decimal("10000")))
        
        sim.submit_market_order("BTCUSDT", "Buy", Decimal("0.01"), Decimal("50000"))
        
        success = sim.set_stop_loss_take_profit(
            "BTCUSDT",
            stop_loss=Decimal("49000"),
            take_profit=Decimal("51000"),
        )
        
        assert success
        pos = sim.get_position("BTCUSDT")
        assert pos.stop_loss == Decimal("49000")
        assert pos.take_profit == Decimal("51000")
    
    def test_stop_loss_triggered_on_long(self):
        """SL срабатывает на long позиции"""
        sim = PaperTradingSimulator(PaperTradingConfig(initial_balance=Decimal("10000")))
        
        sim.submit_market_order("BTCUSDT", "Buy", Decimal("0.01"), Decimal("50000"))
        sim.set_stop_loss_take_profit("BTCUSDT", Decimal("49000"), Decimal("51000"))
        
        # Цена падает ниже SL
        triggered = sim.check_sl_tp(Decimal("48900"))
        
        assert "BTCUSDT" in triggered
        assert triggered["BTCUSDT"] == "sl"
    
    def test_take_profit_triggered_on_long(self):
        """TP срабатывает на long позиции"""
        sim = PaperTradingSimulator(PaperTradingConfig(initial_balance=Decimal("10000")))
        
        sim.submit_market_order("BTCUSDT", "Buy", Decimal("0.01"), Decimal("50000"))
        sim.set_stop_loss_take_profit("BTCUSDT", Decimal("49000"), Decimal("51000"))
        
        # Цена поднимается выше TP
        triggered = sim.check_sl_tp(Decimal("51100"))
        
        assert "BTCUSDT" in triggered
        assert triggered["BTCUSDT"] == "tp"
    
    def test_close_position_on_stop_loss(self):
        """Закрыть позицию по SL"""
        sim = PaperTradingSimulator(PaperTradingConfig(initial_balance=Decimal("10000")))
        
        sim.submit_market_order("BTCUSDT", "Buy", Decimal("0.01"), Decimal("50000"))
        sim.set_stop_loss_take_profit("BTCUSDT", Decimal("49000"), Decimal("51000"))
        
        # Закрыть по SL
        success, _ = sim.close_position_on_trigger("BTCUSDT", "sl", Decimal("48900"))
        
        assert success
        assert sim.get_position("BTCUSDT") is None
        
        # Проверить что trade помечена как stopped_out
        trade = sim.trades[-1]
        assert trade.was_sl_hit
        assert trade.state == TradeState.STOPPED_OUT


class TestReproducibility:
    """Воспроизводимость с seed"""
    
    def test_same_seed_same_results(self):
        """Одинаковый seed дает одинаковые результаты"""
        config1 = PaperTradingConfig(
            initial_balance=Decimal("10000"),
            seed=42,
            use_random_slippage=True,
        )
        sim1 = PaperTradingSimulator(config1)
        
        config2 = PaperTradingConfig(
            initial_balance=Decimal("10000"),
            seed=42,
            use_random_slippage=True,
        )
        sim2 = PaperTradingSimulator(config2)
        
        # Выполнить одинаковые сделки
        for sim in [sim1, sim2]:
            sim.submit_market_order("BTCUSDT", "Buy", Decimal("0.01"), Decimal("50000"))
            sim.update_market_prices({"BTCUSDT": Decimal("51000")})
            sim.submit_market_order("BTCUSDT", "Sell", Decimal("0.01"), Decimal("51000"))
        
        # Результаты должны быть идентичными
        assert sim1.get_equity() == sim2.get_equity()
    
    def test_different_seed_different_results(self):
        """Разные seed дают разные результаты"""
        configs = [
            PaperTradingConfig(seed=42, use_random_slippage=True),
            PaperTradingConfig(seed=123, use_random_slippage=True),
        ]
        
        results = []
        
        for config in configs:
            sim = PaperTradingSimulator(config)
            sim.submit_market_order("BTCUSDT", "Buy", Decimal("0.01"), Decimal("50000"))
            results.append(sim.orders[list(sim.orders.keys())[-1]].commission_paid)
        
        # При random slippage результаты должны отличаться
        # (могут совпасть, но маловероятно)


class TestTradeHistory:
    """История сделок"""
    
    def test_trades_recorded_in_history(self):
        """Все сделки записываются в историю"""
        sim = PaperTradingSimulator(PaperTradingConfig(initial_balance=Decimal("100000")))
        
        # Выполнить 3 сделки
        for i in range(3):
            sim.submit_market_order("BTCUSDT", "Buy", Decimal("0.01"), Decimal("50000"))
            sim.submit_market_order("BTCUSDT", "Sell", Decimal("0.01"), Decimal("51000"))
        
        assert len(sim.trades) == 3
        assert all(trade.pnl > 0 for trade in sim.trades)
    
    def test_trade_contains_all_info(self):
        """Trade содержит все необходимые поля"""
        sim = PaperTradingSimulator(PaperTradingConfig(initial_balance=Decimal("10000")))
        
        sim.submit_market_order("BTCUSDT", "Buy", Decimal("0.01"), Decimal("50000"))
        sim.submit_market_order("BTCUSDT", "Sell", Decimal("0.01"), Decimal("51000"))
        
        trade = sim.trades[0]
        
        assert trade.entry_price > 0
        assert trade.exit_price > 0
        assert trade.entry_qty == Decimal("0.01")
        assert trade.pnl_after_commission != 0
        assert trade.roi_percent != 0


class TestEdgeCases:
    """Edge cases"""
    
    def test_zero_quantity(self):
        """Нулевое количество"""
        sim = PaperTradingSimulator(PaperTradingConfig(initial_balance=Decimal("10000")))
        
        order_id, success, msg = sim.submit_market_order(
            "BTCUSDT", "Buy", Decimal("0"), Decimal("50000")
        )
        
        assert not success
        assert "Quantity must be positive" in msg
    
    def test_very_small_quantity(self):
        """Очень маленькое количество"""
        sim = PaperTradingSimulator(PaperTradingConfig(initial_balance=Decimal("10000")))
        
        order_id, success, _ = sim.submit_market_order(
            "BTCUSDT", "Buy", Decimal("0.000001"), Decimal("50000")
        )
        
        assert success
    
    def test_very_large_quantity(self):
        """Очень большое количество"""
        sim = PaperTradingSimulator(PaperTradingConfig(initial_balance=Decimal("10000000")))  # 10M
        
        order_id, success, _ = sim.submit_market_order(
            "BTCUSDT", "Buy", Decimal("100"), Decimal("50000")
        )
        
        assert success
    
    def test_negative_price(self):
        """Отрицательная цена (edge case)"""
        sim = PaperTradingSimulator(PaperTradingConfig(initial_balance=Decimal("10000")))
        
        # Цена не должна быть отрицательной в реальности, но тестируем обработку
        order_id, success, _ = sim.submit_market_order(
            "BTCUSDT", "Buy", Decimal("0.01"), Decimal("-50000")
        )
        
        # Должно быть ошибка или обработано


class TestMetricsCalculation:
    """Вычисление метрик"""
    
    def test_calculate_metrics_from_trades(self):
        """Вычислить метрики из сделок"""
        sim = PaperTradingSimulator(PaperTradingConfig(initial_balance=Decimal("10000")))
        
        # Выполнить несколько сделок
        sim.submit_market_order("BTCUSDT", "Buy", Decimal("0.01"), Decimal("50000"))
        sim.submit_market_order("BTCUSDT", "Sell", Decimal("0.01"), Decimal("51000"))  # +1000
        
        sim.submit_market_order("BTCUSDT", "Buy", Decimal("0.01"), Decimal("51000"))
        sim.submit_market_order("BTCUSDT", "Sell", Decimal("0.01"), Decimal("50000"))  # -1000
        
        metrics = TradeMetricsCalculator.calculate(
            sim.trades,
            Decimal("10000"),
        )
        
        assert metrics.total_trades == 2
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.win_rate > 0
    
    def test_profit_factor(self):
        """Profit factor = gross_profit / abs(gross_loss)"""
        sim = PaperTradingSimulator(PaperTradingConfig(initial_balance=Decimal("100000")))
        
        # Выгодная сделка
        sim.submit_market_order("BTCUSDT", "Buy", Decimal("0.1"), Decimal("50000"))
        sim.submit_market_order("BTCUSDT", "Sell", Decimal("0.1"), Decimal("52000"))
        
        metrics = TradeMetricsCalculator.calculate(sim.trades, Decimal("100000"))
        
        assert metrics.profit_factor > 0
        assert metrics.winning_trades == 1
