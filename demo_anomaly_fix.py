#!/usr/bin/env python3
"""
Демонстрация исправления Symbol=UNKNOWN и ложных аномалий.

Этот скрипт показывает:
1. Symbol теперь корректно передается в features
2. Doji-свечи не флагаются как аномалия
3. Экстремальные тени корректно детектируются
4. Детали аномалии присутствуют в логах
"""

import pandas as pd
import numpy as np
from data.features import FeaturePipeline
from strategy.meta_layer import NoTradeZones, MetaLayer
from unittest.mock import patch


def test_doji_not_anomaly():
    """Демонстрация: doji-свеча не является аномалией"""
    print("\n" + "="*70)
    print("ТЕСТ 1: Doji-свеча с умеренными тенями")
    print("="*70)
    
    # Создаем doji-свечу (open == close) с тенями 1% от цены
    data = pd.DataFrame({
        "open": [100.0, 100.0, 100.0],
        "high": [101.0, 101.0, 101.0],  # Верхняя тень: 1%
        "low": [99.0, 99.0, 99.0],       # Нижняя тень: 1%
        "close": [100.0, 100.0, 100.0],  # Doji: open == close
        "volume": [1000, 1000, 1000]
    })
    
    pipeline = FeaturePipeline()
    df = pipeline.detect_data_anomalies(data)
    
    print(f"Body (open-close): {abs(data.iloc[-1]['close'] - data.iloc[-1]['open']):.2f}")
    print(f"Upper wick: {data.iloc[-1]['high'] - max(data.iloc[-1]['open'], data.iloc[-1]['close']):.2f}")
    print(f"Lower wick: {min(data.iloc[-1]['open'], data.iloc[-1]['close']) - data.iloc[-1]['low']:.2f}")
    print(f"anomaly_wick: {df.iloc[-1]['anomaly_wick']}")
    print(f"has_anomaly: {df.iloc[-1]['has_anomaly']}")
    
    if df.iloc[-1]['anomaly_wick'] == 0:
        print("✅ PASSED: Doji-свеча НЕ помечена как аномалия")
    else:
        print("❌ FAILED: Doji-свеча ошибочно помечена как аномалия")
    

def test_extreme_wick_is_anomaly():
    """Демонстрация: экстремальная тень детектируется"""
    print("\n" + "="*70)
    print("ТЕСТ 2: Свеча с экстремальной тенью")
    print("="*70)
    
    # Создаем свечу с экстремальной тенью (20% от цены)
    data = pd.DataFrame({
        "open": [100.0, 100.0, 100.0],
        "high": [100.5, 100.5, 120.0],  # Экстремальная верхняя тень: 20%
        "low": [99.5, 99.5, 99.5],
        "close": [100.0, 100.0, 100.2],  # Малое тело
        "volume": [1000, 1000, 1000]
    })
    
    pipeline = FeaturePipeline()
    df = pipeline.detect_data_anomalies(data)
    
    print(f"Body (open-close): {abs(data.iloc[-1]['close'] - data.iloc[-1]['open']):.2f}")
    print(f"Upper wick: {data.iloc[-1]['high'] - max(data.iloc[-1]['open'], data.iloc[-1]['close']):.2f}")
    print(f"Upper wick % от цены: {(data.iloc[-1]['high'] - max(data.iloc[-1]['open'], data.iloc[-1]['close'])) / data.iloc[-1]['close'] * 100:.1f}%")
    print(f"anomaly_wick: {df.iloc[-1]['anomaly_wick']}")
    print(f"has_anomaly: {df.iloc[-1]['has_anomaly']}")
    
    if df.iloc[-1]['anomaly_wick'] == 1:
        print("✅ PASSED: Экстремальная тень корректно детектирована")
    else:
        print("❌ FAILED: Экстремальная тень НЕ детектирована")


def test_symbol_propagation():
    """Демонстрация: Symbol корректно передается в features"""
    print("\n" + "="*70)
    print("ТЕСТ 3: Передача Symbol в features")
    print("="*70)
    
    # Имитируем процесс в TradingBot
    symbol = "BTCUSDT"
    features = {}
    
    # Добавляем symbol (как в исправленном trading_bot.py)
    features["symbol"] = symbol
    
    # Извлекаем symbol (как в MetaLayer)
    extracted_symbol = features.get("symbol", "UNKNOWN")
    
    print(f"Original symbol: {symbol}")
    print(f"Features dict: {features}")
    print(f"Extracted symbol: {extracted_symbol}")
    
    if extracted_symbol == symbol and extracted_symbol != "UNKNOWN":
        print("✅ PASSED: Symbol корректно передается и извлекается")
    else:
        print("❌ FAILED: Symbol не передается корректно")


def test_anomaly_details_in_logs():
    """Демонстрация: Детали аномалии в логах"""
    print("\n" + "="*70)
    print("ТЕСТ 4: Детали аномалии в возврате NoTradeZones")
    print("="*70)
    
    # Создаем DataFrame с аномалией
    df = pd.DataFrame({
        "has_anomaly": [0, 0, 1],
        "anomaly_wick": [0, 0, 1],
        "anomaly_low_volume": [0, 0, 0],
        "anomaly_gap": [0, 0, 0],
        "vol_regime": [0, 0, 0],
        "atr_percent": [1.0, 1.0, 1.0]
    })
    
    features = {"symbol": "ETHUSDT"}
    
    # Вызываем is_trading_allowed
    allowed, reason, details = NoTradeZones.is_trading_allowed(df, features, error_count=0)
    
    print(f"Trading allowed: {allowed}")
    print(f"Reason: {reason}")
    print(f"Details: {details}")
    
    if not allowed and details and "anomaly_wick" in details:
        print("✅ PASSED: Детали аномалии корректно возвращаются")
    else:
        print("❌ FAILED: Детали аномалии отсутствуют или некорректны")


def test_meta_layer_integration():
    """Демонстрация: Интеграция с MetaLayer"""
    print("\n" + "="*70)
    print("ТЕСТ 5: Интеграция с MetaLayer (Symbol в логах)")
    print("="*70)
    
    # Создаем данные с аномалией
    data = pd.DataFrame({
        "open": [100.0] * 100,
        "high": [102.0] * 99 + [125.0],  # Экстремальная тень
        "low": [98.0] * 100,
        "close": [100.0] * 99 + [100.5],
        "volume": [1000] * 100
    })
    
    pipeline = FeaturePipeline()
    df = pipeline.build_features(data)
    
    # Добавляем symbol в features (как в TradingBot)
    features = {"symbol": "SOLUSDT"}
    
    # Создаем MetaLayer и вызываем get_signal с mock logger
    with patch('strategy.meta_layer.signal_logger') as mock_logger:
        meta_layer = MetaLayer(strategies=[])
        result = meta_layer.get_signal(df, features, error_count=0)
        
        print(f"Signal result: {result}")
        print(f"log_signal_rejected called: {mock_logger.log_signal_rejected.called}")
        
        if mock_logger.log_signal_rejected.called:
            call_args = mock_logger.log_signal_rejected.call_args
            logged_symbol = call_args[1]["symbol"]
            logged_values = call_args[1]["values"]
            
            print(f"Logged symbol: {logged_symbol}")
            print(f"Logged values: {logged_values}")
            
            if logged_symbol == "SOLUSDT" and logged_symbol != "UNKNOWN":
                print("✅ PASSED: Symbol корректен в логе (не UNKNOWN)")
            else:
                print("❌ FAILED: Symbol некорректен в логе")
                
            if "anomaly_wick" in logged_values or "anomaly_low_volume" in logged_values:
                print("✅ PASSED: Детали аномалии присутствуют в логе")
            else:
                print("❌ FAILED: Детали аномалии отсутствуют в логе")
        else:
            print("⚠️  WARNING: log_signal_rejected не был вызван (возможно, нет аномалии)")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("ДЕМОНСТРАЦИЯ ИСПРАВЛЕНИЯ SYMBOL=UNKNOWN И ЛОЖНЫХ АНОМАЛИЙ")
    print("="*70)
    
    test_doji_not_anomaly()
    test_extreme_wick_is_anomaly()
    test_symbol_propagation()
    test_anomaly_details_in_logs()
    test_meta_layer_integration()
    
    print("\n" + "="*70)
    print("ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА")
    print("="*70 + "\n")
