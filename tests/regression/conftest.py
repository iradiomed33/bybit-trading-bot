"""
Shared fixtures для всех regression тестов.

Содержит:
- OHLCV данные (синтетические и реальные)
- Mock объекты (API, БД)
- Стратегии для тестов
- Конфигурации
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List
import json
from unittest.mock import Mock, MagicMock, patch


@pytest.fixture
def sample_ohlcv():
    """Синтетические OHLCV данные для 100 свечей (15m)"""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=100, freq='15min')
    
    close = pd.Series(50000 + np.cumsum(np.random.randn(100) * 100))
    high = pd.Series(close + np.abs(np.random.randn(100) * 50))
    low = pd.Series(close - np.abs(np.random.randn(100) * 50))
    open_ = close.shift(1)
    volume = pd.Series(np.random.uniform(10, 100, 100))
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })
    
    return df.reset_index(drop=True)


@pytest.fixture
def uptrend_data():
    """OHLCV данные с восходящим трендом (для тестирования индикаторов)"""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=200, freq='1h')
    
    # Линейный тренд вверх
    base_trend = np.linspace(50000, 55000, 200)
    noise = np.random.randn(200) * 200
    close = pd.Series(base_trend + noise)
    
    high = pd.Series(close + np.abs(np.random.randn(200) * 100))
    low = pd.Series(close - np.abs(np.random.randn(200) * 100))
    open_ = close.shift(1)
    volume = pd.Series(np.random.uniform(50, 150, 200))
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })
    
    return df.reset_index(drop=True)


@pytest.fixture
def downtrend_data():
    """OHLCV данные с нисходящим трендом"""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=200, freq='1h')
    
    # Линейный тренд вниз
    base_trend = np.linspace(55000, 50000, 200)
    noise = np.random.randn(200) * 200
    close = pd.Series(base_trend + noise)
    
    high = pd.Series(close + np.abs(np.random.randn(200) * 100))
    low = pd.Series(close - np.abs(np.random.randn(200) * 100))
    open_ = close.shift(1)
    volume = pd.Series(np.random.uniform(50, 150, 200))
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })
    
    return df.reset_index(drop=True)


@pytest.fixture
def sideways_data():
    """OHLCV данные с боковой торговлей (range)"""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=200, freq='1h')
    
    # Осциллирующие данные вокруг среднего
    close = pd.Series(50000 + 500 * np.sin(2 * np.pi * np.arange(200) / 50) + np.random.randn(200) * 100)
    
    high = pd.Series(close + np.abs(np.random.randn(200) * 100))
    low = pd.Series(close - np.abs(np.random.randn(200) * 100))
    open_ = close.shift(1)
    volume = pd.Series(np.random.uniform(50, 150, 200))
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })
    
    return df.reset_index(drop=True)


@pytest.fixture
def high_volatility_data():
    """OHLCV данные с высокой волатильностью"""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=200, freq='1h')
    
    close = pd.Series(50000 + np.cumsum(np.random.randn(200) * 500))  # Большие движения
    high = pd.Series(close + np.abs(np.random.randn(200) * 300))
    low = pd.Series(close - np.abs(np.random.randn(200) * 300))
    open_ = close.shift(1)
    volume = pd.Series(np.random.uniform(50, 150, 200))
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })
    
    return df.reset_index(drop=True)


@pytest.fixture
def low_volume_data(sample_ohlcv):
    """OHLCV данные с низким объёмом"""
    data = sample_ohlcv.copy()
    data['volume'] = data['volume'] * 0.1  # 10% от нормального
    return data


@pytest.fixture
def mock_bybit_client():
    """Mock Bybit API клиент"""
    client = MagicMock()
    client.get_positions = MagicMock(return_value={
        'retCode': 0,
        'result': {
            'list': [
                {
                    'symbol': 'BTCUSDT',
                    'side': 'Buy',
                    'size': '0.1',
                    'positionValue': '5000',
                    'avgPrice': '50000',
                    'markPrice': '50100',
                    'pnl': '10',
                }
            ]
        }
    })
    
    client.get_wallet_balance = MagicMock(return_value={
        'retCode': 0,
        'result': {
            'list': [
                {
                    'totalEquity': '10000',
                    'totalWalletBalance': '10000',
                    'totalMarginBalance': '10000',
                    'totalAvailableBalance': '9900',
                }
            ]
        }
    })
    
    client.place_order = MagicMock(return_value={
        'retCode': 0,
        'result': {
            'orderId': 'test_order_123',
            'symbol': 'BTCUSDT',
            'orderType': 'Limit',
            'side': 'Buy',
            'qty': '0.1',
            'price': '50000',
            'status': 'New',
        }
    })
    
    return client


@pytest.fixture
def mock_database():
    """Mock БД для сохранения сделок и позиций"""
    db = MagicMock()
    db.save_trade = MagicMock(return_value=True)
    db.save_position = MagicMock(return_value=True)
    db.get_last_position = MagicMock(return_value=None)
    db.get_last_trade = MagicMock(return_value=None)
    return db


@pytest.fixture
def test_config():
    """Конфигурация для тестов"""
    return {
        'symbol': 'BTCUSDT',
        'mode': 'paper',
        'use_mtf': True,
        'mtf_score_threshold': 0.6,
        'risk_pct': 1.0,
        'max_leverage': 10.0,
        'max_notional': 50000.0,
        'daily_loss_limit': 5000.0,
        'fee_maker': 0.0002,
        'fee_taker': 0.0005,
        'slippage_bps': 5,
        'breakout_entry': 'instant',
        'entry_mode': 'confirm_close',
    }


@pytest.fixture
def paper_simulator_config():
    """Конфигурация для paper trading симулятора"""
    return {
        'initial_balance': 10000.0,
        'leverage': 1.0,
        'fees_enabled': True,
        'slippage_enabled': True,
        'slippage_bps': 5,
    }


# Вспомогательные функции для тестов

def create_order(
    symbol: str = "BTCUSDT",
    side: str = "Buy",
    qty: float = 0.1,
    price: float = 50000.0,
    order_type: str = "Limit",
    reduce_only: bool = False,
) -> Dict[str, Any]:
    """Создать объект ордера для тестирования"""
    return {
        'symbol': symbol,
        'side': side,
        'qty': qty,
        'price': price,
        'orderType': order_type,
        'reduceOnly': reduce_only,
    }


def create_position(
    symbol: str = "BTCUSDT",
    side: str = "Buy",
    size: float = 0.1,
    entry_price: float = 50000.0,
    mark_price: float = 50100.0,
    pnl: float = 10.0,
) -> Dict[str, Any]:
    """Создать объект позиции для тестирования"""
    return {
        'symbol': symbol,
        'side': side,
        'size': size,
        'entryPrice': entry_price,
        'markPrice': mark_price,
        'unrealisedPnl': pnl,
        'positionValue': size * mark_price,
    }


def create_signal(
    symbol: str = "BTCUSDT",
    direction: str = "long",
    confidence: float = 0.8,
    entry_price: float = 50000.0,
    stop_loss: float = 49000.0,
    take_profit: float = 51000.0,
    reason: str = "test_signal",
) -> Dict[str, Any]:
    """Создать объект сигнала для тестирования"""
    return {
        'symbol': symbol,
        'direction': direction,
        'confidence': confidence,
        'entryPrice': entry_price,
        'stopLoss': stop_loss,
        'takeProfit': take_profit,
        'reasons': [reason],
        'timestamp': datetime.now().isoformat(),
    }
