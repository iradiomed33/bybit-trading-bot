"""
E2E TESTNET INTEGRATION: Полный цикл сделки

Этот тест проверяет на реальном Bybit testnet весь цикл торговли:
1. Открыть позицию (Market)
2. Выставить SL/TP через /v5/position/trading-stop
3. Закрыть позицию (reduceOnly Market)
4. Очистка (отмена ордеров и стопов)

Требования:
- BYBIT_API_KEY и BYBIT_API_SECRET в .env
- RUN_TESTNET_E2E=1 для запуска (чтобы не задеть биржу случайно)

Запуск:
    RUN_TESTNET_E2E=1 pytest tests/e2e/test_full_trade_cycle_testnet.py -v -s

Критерии приёмки:
- Тест стабильно проходит на testnet
- Падает с понятной диагностикой при ошибках
- Проверяет факт на стороне биржи, а не только retCode
"""

import os
import sys
import pytest
import time
from decimal import Decimal
from typing import Dict, Any, Optional, List

# Добавляем корневую директорию в path
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Загружаем .env файл
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv не обязателен, можно использовать системные переменные

from exchange.base_client import BybitRestClient
from exchange.account import AccountClient
from exchange.instruments import InstrumentsManager
from execution.order_manager import OrderManager
from storage.database import Database
from logger import setup_logger

logger = setup_logger(__name__)


# Флаг для запуска E2E тестов
TESTNET_E2E_ENABLED = os.getenv('RUN_TESTNET_E2E') == '1'

# Тестовый символ и параметры
TEST_SYMBOL = 'BTCUSDT'
TEST_CATEGORY = 'linear'
POSITION_INDEX = 0  # One-way mode


class E2ETestnetHelper:
    """Вспомогательный класс для E2E тестов на testnet"""
    
    def __init__(self):
        """Инициализация клиентов и менеджеров"""
        # Проверяем API ключи
        self.api_key = os.getenv('BYBIT_API_KEY')
        self.api_secret = os.getenv('BYBIT_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            raise ValueError(
                "\n\n❌ BYBIT_API_KEY и BYBIT_API_SECRET не установлены!\n\n"
                "Создайте .env файл в корне проекта:\n"
                "  BYBIT_API_KEY=your_testnet_api_key\n"
                "  BYBIT_API_SECRET=your_testnet_api_secret\n\n"
                "Получить ключи: https://testnet.bybit.com/app/user/api-management\n"
            )
        
        logger.info(f"Using API key: {self.api_key[:8]}...{self.api_key[-4:]}")
        
        # Инициализация клиентов
        self.rest_client = BybitRestClient(
            api_key=self.api_key, 
            api_secret=self.api_secret, 
            testnet=True
        )
        self.account_client = AccountClient(
            api_key=self.api_key,
            api_secret=self.api_secret,
            testnet=True
        )
        
        # База данных (используем временную для теста)
        self.db = Database(db_path="storage/e2e_test.db")
        
        # Менеджеры
        self.instruments = InstrumentsManager(
            rest_client=self.rest_client,
            category=TEST_CATEGORY
        )
        self.order_manager = OrderManager(
            client=self.rest_client,
            db=self.db
        )
        
        logger.info("E2ETestnetHelper initialized")
    
    def load_instruments(self) -> bool:
        """Загрузить информацию об инструментах"""
        try:
            success = self.instruments.load_instruments(force_refresh=True)
            if not success:
                logger.error("Failed to load instruments")
                return False
            
            info = self.instruments.get_instrument(TEST_SYMBOL)
            if not info:
                logger.error(f"Instrument {TEST_SYMBOL} not found")
                return False
            
            logger.info(
                f"✓ Instrument loaded: {TEST_SYMBOL} "
                f"tickSize={info['tickSize']}, "
                f"qtyStep={info['qtyStep']}, "
                f"minOrderQty={info['minOrderQty']}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error loading instruments: {e}", exc_info=True)
            return False
    
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Получить текущую позицию по символу.
        
        Returns:
            Dict с информацией о позиции или None если позиции нет
        """
        try:
            response = self.account_client.get_positions(
                category=TEST_CATEGORY,
                symbol=symbol
            )
            
            if response.get('retCode') != 0:
                logger.error(f"Failed to get position: {response.get('retMsg')}")
                return None
            
            positions = response.get('result', {}).get('list', [])
            if not positions:
                logger.debug(f"No position found for {symbol}")
                return None
            
            # Возвращаем первую позицию для символа
            position = positions[0]
            size = Decimal(position.get('size', '0'))
            
            logger.info(
                f"Position: {symbol} size={size} side={position.get('side')} "
                f"avgPrice={position.get('avgPrice')} "
                f"unrealizedPnl={position.get('unrealisedPnl')}"
            )
            
            return position
            
        except Exception as e:
            logger.error(f"Error getting position: {e}", exc_info=True)
            return None
    
    def close_position_if_exists(self, symbol: str) -> bool:
        """
        Закрыть позицию если она открыта.
        
        Returns:
            True если позиция закрыта или не было позиции
        """
        try:
            position = self.get_position(symbol)
            if not position:
                logger.info(f"✓ No position to close for {symbol}")
                return True
            
            size = Decimal(position.get('size', '0'))
            if size == 0:
                logger.info(f"✓ Position size is 0 for {symbol}")
                return True
            
            # Определяем противоположную сторону для закрытия
            side = position.get('side')
            close_side = 'Sell' if side == 'Buy' else 'Buy'
            
            logger.info(f"Closing position: {symbol} size={size} close_side={close_side}")
            
            # Закрываем позицию через Market order с reduceOnly
            params = {
                "category": TEST_CATEGORY,
                "symbol": symbol,
                "side": close_side,
                "orderType": "Market",
                "qty": str(size),
                "reduceOnly": True,
                "positionIdx": POSITION_INDEX,
            }
            
            response = self.rest_client.post("/v5/order/create", params=params)
            
            if response.get('retCode') != 0:
                logger.error(f"Failed to close position: {response.get('retMsg')}")
                return False
            
            # Ждем исполнения
            time.sleep(2)
            
            # Проверяем что позиция закрылась
            position = self.get_position(symbol)
            if position:
                size = Decimal(position.get('size', '0'))
                if size > 0:
                    logger.error(f"Position still open after close: size={size}")
                    return False
            
            logger.info(f"✓ Position closed for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error closing position: {e}", exc_info=True)
            return False
    
    def cancel_all_orders(self, symbol: str) -> bool:
        """
        Отменить все активные ордера по символу.
        
        Returns:
            True если все ордера отменены или не было ордеров
        """
        try:
            # Отменяем все ордера через API
            params = {
                "category": TEST_CATEGORY,
                "symbol": symbol,
            }
            
            response = self.rest_client.post("/v5/order/cancel-all", params=params)
            
            if response.get('retCode') != 0:
                logger.error(f"Failed to cancel orders: {response.get('retMsg')}")
                return False
            
            result = response.get('result', {})
            cancelled_list = result.get('list', [])
            
            logger.info(f"✓ Cancelled {len(cancelled_list)} orders for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling orders: {e}", exc_info=True)
            return False
    
    def clear_trading_stop(self, symbol: str) -> bool:
        """
        Очистить SL/TP на позиции (установить в "").
        
        Returns:
            True если стопы очищены
        """
        try:
            result = self.order_manager.set_trading_stop(
                category=TEST_CATEGORY,
                symbol=symbol,
                position_idx=POSITION_INDEX,
                stop_loss="0",
                take_profit="0",
            )
            
            if not result.success:
                # Ошибка 34040 "not modified" - это нормально (SL/TP уже пустые)
                if "34040" in str(result.error) or "not modified" in str(result.error).lower():
                    logger.info(f"✓ Trading stop already cleared for {symbol}")
                    return True
                    
                logger.error(f"Failed to clear trading stop: {result.error}")
                return False
            
            logger.info(f"✓ Trading stop cleared for {symbol}")
            return True
            
        except Exception as e:
            error_msg = str(e)
            # Ошибка 34040 "not modified" - это нормально
            if "34040" in error_msg or "not modified" in error_msg.lower():
                logger.info(f"✓ Trading stop already cleared for {symbol}")
                return True
                
            logger.error(f"Error clearing trading stop: {e}", exc_info=True)
            return False
    
    def get_minimum_qty(self, symbol: str, price: Decimal) -> Decimal:
        """
        Получить минимальное количество для ордера.
        
        Args:
            symbol: Символ
            price: Текущая цена
            
        Returns:
            Минимальное количество, удовлетворяющее всем требованиям
        """
        info = self.instruments.get_instrument(symbol)
        if not info:
            raise ValueError(f"Instrument {symbol} not found")
        
        min_order_qty = info['minOrderQty']
        qty_step = info['qtyStep']
        min_notional = info['minNotional']
        
        # Вычисляем минимальное qty для notional
        min_qty_for_notional = min_notional / price
        
        # Выбираем максимум из двух минимумов
        min_qty = max(min_order_qty, min_qty_for_notional)
        
        # Добавляем небольшой запас (5%) для надежности
        min_qty = min_qty * Decimal('1.05')
        
        # ВАЖНО: Bybit testnet имеет баг где qtyStep=1 для всех пар
        # Поэтому используем max(qtyStep, minOrderQty) для безопасности
        effective_qty_step = max(qty_step, min_order_qty)
        
        # Округляем до effective_qty_step вверх
        min_qty = (min_qty / effective_qty_step).quantize(Decimal('1'), rounding='ROUND_UP') * effective_qty_step
        
        # Если qty_step слишком большой, используем minOrderQty
        if min_qty > min_order_qty * Decimal('100'):  # Если получилось >100x от минимума
            logger.warning(f"qtyStep={qty_step} too large, using minOrderQty={min_order_qty}")
            min_qty = min_order_qty
        
        logger.info(f"Minimum qty for {symbol}: {min_qty} (price={price})")
        return min_qty


@pytest.fixture(scope='module')
def helper():
    """Fixture для E2E helper"""
    h = E2ETestnetHelper()
    
    # Загружаем инструменты
    assert h.load_instruments(), "Failed to load instruments"
    
    yield h
    
    # Cleanup после всех тестов
    logger.info("=== Final cleanup ===")
    h.clear_trading_stop(TEST_SYMBOL)
    h.cancel_all_orders(TEST_SYMBOL)
    h.close_position_if_exists(TEST_SYMBOL)


@pytest.mark.skipif(
    not TESTNET_E2E_ENABLED,
    reason="RUN_TESTNET_E2E=1 not set. Skipping testnet E2E tests."
)
class TestE2EFullTradeCycle:
    """E2E тест полного цикла торговли на testnet"""
    
    def test_00_preparation(self, helper: E2ETestnetHelper):
        """
        Шаг 0: Подготовка - убедиться что нет открытых позиций/ордеров.
        """
        logger.info("=== STEP 0: Preparation ===")
        
        # Отменяем все ордера
        assert helper.cancel_all_orders(TEST_SYMBOL), \
            "Failed to cancel existing orders"
        
        # Закрываем позицию если есть
        assert helper.close_position_if_exists(TEST_SYMBOL), \
            "Failed to close existing position"
        
        # Очищаем trading stop
        helper.clear_trading_stop(TEST_SYMBOL)
        
        # Проверяем что позиция закрыта
        position = helper.get_position(TEST_SYMBOL)
        if position:
            size = Decimal(position.get('size', '0'))
            assert size == 0, f"Position size should be 0, got {size}"
        
        logger.info("✓ Preparation complete")
    
    def test_01_open_position(self, helper: E2ETestnetHelper):
        """
        Шаг 1: Открыть позицию через Market ордер.
        
        Assertions:
        - Ордер создан успешно
        - Позиция появилась в /v5/position/list
        - size > 0
        """
        logger.info("=== STEP 1: Open Position ===")
        
        # ВАЖНО: закрываем существующую позицию если есть
        helper.close_position_if_exists(TEST_SYMBOL)
        
        # Получаем текущую цену (для расчета минимального qty)
        # Используем ticker для получения lastPrice
        ticker_response = helper.rest_client.get(
            "/v5/market/tickers",
            params={"category": TEST_CATEGORY, "symbol": TEST_SYMBOL}
        )
        
        assert ticker_response.get('retCode') == 0, \
            f"Failed to get ticker: {ticker_response.get('retMsg')}"
        
        ticker_list = ticker_response.get('result', {}).get('list', [])
        assert ticker_list, f"No ticker data for {TEST_SYMBOL}"
        
        last_price = Decimal(ticker_list[0].get('lastPrice', '0'))
        assert last_price > 0, "Invalid last price"
        
        logger.info(f"Current price for {TEST_SYMBOL}: {last_price}")
        
        # Вычисляем минимальное количество
        qty = helper.get_minimum_qty(TEST_SYMBOL, last_price)
        
        logger.info(f"Opening position: {TEST_SYMBOL} qty={qty}")
        
        # Открываем позицию через OrderManager
        result = helper.order_manager.create_order(
            category=TEST_CATEGORY,
            symbol=TEST_SYMBOL,
            side='Buy',
            order_type='Market',
            qty=float(qty),
        )
        
        assert result.success, f"Failed to create order: {result.error}"
        assert result.order_id, "Order ID should be returned"
        
        logger.info(f"✓ Order created: {result.order_id}")
        
        # Ждем исполнения ордера
        time.sleep(3)
        
        # Проверяем что позиция открылась
        position = helper.get_position(TEST_SYMBOL)
        assert position is not None, "Position should exist after order execution"
        
        size = Decimal(position.get('size', '0'))
        assert size > 0, f"Position size should be > 0, got {size}"
        
        side = position.get('side')
        assert side == 'Buy', f"Position side should be 'Buy', got {side}"
        
        logger.info(f"✓ Position opened: size={size} side={side}")
    
    def test_02_set_sl_tp(self, helper: E2ETestnetHelper):
        """
        Шаг 2: Выставить SL/TP через trading-stop API.
        
        Assertions:
        - set_trading_stop вернул success=True
        - В /v5/position/list появились stopLoss и takeProfit
        """
        logger.info("=== STEP 2: Set SL/TP ===")
        
        # Получаем текущую позицию
        position = helper.get_position(TEST_SYMBOL)
        assert position is not None, "Position should exist before setting SL/TP"
        
        size = Decimal(position.get('size', '0'))
        assert size > 0, "Position size should be > 0"
        
        avg_price = Decimal(position.get('avgPrice', '0'))
        assert avg_price > 0, "Invalid avgPrice"
        
        # Вычисляем SL и TP (для Buy позиции)
        # SL: -2% от avgPrice
        # TP: +3% от avgPrice
        sl_price_calc = avg_price * Decimal('0.98')
        tp_price_calc = avg_price * Decimal('1.03')
        
        # Нормализуем цены
        sl_price = helper.instruments.normalize_price(TEST_SYMBOL, float(sl_price_calc))
        tp_price = helper.instruments.normalize_price(TEST_SYMBOL, float(tp_price_calc))
        
        if sl_price is None or tp_price is None:
            raise ValueError("Failed to normalize SL/TP prices")
        
        logger.info(
            f"Setting SL/TP: avgPrice={avg_price} SL={sl_price} TP={tp_price}"
        )
        
        # Выставляем SL/TP через OrderManager
        result = helper.order_manager.set_trading_stop(
            category=TEST_CATEGORY,
            symbol=TEST_SYMBOL,
            position_idx=POSITION_INDEX,
            stop_loss=str(sl_price),
            take_profit=str(tp_price),
            sl_trigger_by='LastPrice',
            tp_trigger_by='LastPrice',
            tpsl_mode='Full',
        )
        
        assert result.success, f"Failed to set trading stop: {result.error}"
        
        logger.info("✓ Trading stop set successfully")
        
        # Ждем применения
        time.sleep(2)
        
        # Проверяем что SL/TP установились на бирже
        position = helper.get_position(TEST_SYMBOL)
        assert position is not None, "Position should still exist"
        
        position_sl = position.get('stopLoss', '')
        position_tp = position.get('takeProfit', '')
        
        # Проверяем что stopLoss и takeProfit не пустые
        assert position_sl and position_sl != '0' and position_sl != '', \
            f"Stop Loss should be set on position, got: {position_sl}"
        
        assert position_tp and position_tp != '0' and position_tp != '', \
            f"Take Profit should be set on position, got: {position_tp}"
        
        logger.info(
            f"✓ SL/TP verified on exchange: SL={position_sl} TP={position_tp}"
        )
        
        # Проверяем что значения соответствуют установленным (с учетом возможного округления)
        position_sl_decimal = Decimal(position_sl)
        position_tp_decimal = Decimal(position_tp)
        
        # Допускаем отклонение до 0.1% (из-за округления на бирже)
        sl_diff = abs(position_sl_decimal - sl_price) / sl_price
        tp_diff = abs(position_tp_decimal - tp_price) / tp_price
        
        assert sl_diff < Decimal('0.001'), \
            f"SL price mismatch: expected {sl_price}, got {position_sl_decimal}"
        
        assert tp_diff < Decimal('0.001'), \
            f"TP price mismatch: expected {tp_price}, got {position_tp_decimal}"
        
        logger.info("✓ SL/TP values match expected")
    
    def test_03_close_position(self, helper: E2ETestnetHelper):
        """
        Шаг 3: Закрыть позицию через Market reduceOnly ордер.
        
        Assertions:
        - Ордер создан успешно
        - После исполнения size == 0 в /v5/position/list
        """
        logger.info("=== STEP 3: Close Position ===")
        
        # Получаем текущую позицию
        position = helper.get_position(TEST_SYMBOL)
        assert position is not None, "Position should exist before closing"
        
        size = Decimal(position.get('size', '0'))
        assert size > 0, f"Position size should be > 0, got {size}"
        
        side = position.get('side')
        close_side = 'Sell' if side == 'Buy' else 'Buy'
        
        logger.info(f"Closing position: size={size} close_side={close_side}")
        
        # Закрываем позицию через Market order с reduceOnly
        params = {
            "category": TEST_CATEGORY,
            "symbol": TEST_SYMBOL,
            "side": close_side,
            "orderType": "Market",
            "qty": str(size),
            "reduceOnly": True,
            "positionIdx": POSITION_INDEX,
        }
        
        response = helper.rest_client.post("/v5/order/create", params=params)
        
        assert response.get('retCode') == 0, \
            f"Failed to close position: {response.get('retMsg')}"
        
        order_id = response.get('result', {}).get('orderId')
        logger.info(f"✓ Close order created: {order_id}")
        
        # Ждем исполнения
        time.sleep(3)
        
        # Проверяем что позиция закрылась
        position = helper.get_position(TEST_SYMBOL)
        
        if position:
            size = Decimal(position.get('size', '0'))
            assert size == 0, \
                f"Position should be closed (size=0), got size={size}"
        
        logger.info("✓ Position closed successfully")
    
    def test_04_cleanup(self, helper: E2ETestnetHelper):
        """
        Шаг 4: Cleanup - очистить trading stop и отменить ордера.
        
        Assertions:
        - Trading stop очищен
        - Нет активных ордеров
        """
        logger.info("=== STEP 4: Cleanup ===")
        
        # Очищаем trading stop
        assert helper.clear_trading_stop(TEST_SYMBOL), \
            "Failed to clear trading stop"
        
        # Отменяем все ордера (на всякий случай)
        assert helper.cancel_all_orders(TEST_SYMBOL), \
            "Failed to cancel orders"
        
        # Проверяем что нет активных ордеров
        orders_response = helper.account_client.get_open_orders(
            category=TEST_CATEGORY,
            symbol=TEST_SYMBOL
        )
        
        assert orders_response.get('retCode') == 0, \
            "Failed to get open orders"
        
        orders = orders_response.get('result', {}).get('list', [])
        assert len(orders) == 0, \
            f"Should have no active orders, found {len(orders)}"
        
        logger.info("✓ Cleanup complete")
    
    def test_05_verify_final_state(self, helper: E2ETestnetHelper):
        """
        Шаг 5: Финальная проверка - убедиться что всё чисто.
        
        Assertions:
        - Нет открытой позиции (size=0)
        - Нет активных ордеров
        - Нет SL/TP на позиции
        """
        logger.info("=== STEP 5: Verify Final State ===")
        
        # Проверяем позицию
        position = helper.get_position(TEST_SYMBOL)
        if position:
            size = Decimal(position.get('size', '0'))
            assert size == 0, f"Final position size should be 0, got {size}"
            
            # Проверяем что SL/TP очищены
            stop_loss = position.get('stopLoss', '')
            take_profit = position.get('takeProfit', '')
            
            # На Bybit пустой SL/TP может быть "" или "0"
            assert not stop_loss or stop_loss == '0' or stop_loss == '', \
                f"Stop Loss should be cleared, got: {stop_loss}"
            
            assert not take_profit or take_profit == '0' or take_profit == '', \
                f"Take Profit should be cleared, got: {take_profit}"
        
        # Проверяем ордера
        orders_response = helper.account_client.get_open_orders(
            category=TEST_CATEGORY,
            symbol=TEST_SYMBOL
        )
        
        assert orders_response.get('retCode') == 0, \
            "Failed to get open orders"
        
        orders = orders_response.get('result', {}).get('list', [])
        assert len(orders) == 0, \
            f"Should have no active orders, found {len(orders)}"
        
        logger.info("✓ Final state verified - all clean")


if __name__ == '__main__':
    # Запуск тестов с подробным выводом
    pytest.main([__file__, '-v', '-s'])
