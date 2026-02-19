#!/usr/bin/env python3
"""
Показывает текущие условия рынка для проверки почему Grid Trading не генерирует сигналы.
"""
import sys
import pandas as pd
import numpy as np
from bot.bybit_client import BybitClient
from utils.indicators import compute_indicators

def check_market_conditions():
    """Проверяет текущие рыночные условия для Grid Trading"""
    
    print("🔍 Проверка рыночных условий для Grid Trading\n")
    
    try:
        # Инициализация клиента
        client = BybitClient(mode="live", use_testnet=True)
        
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
        
        for symbol in symbols:
            print(f"\n{'='*60}")
            print(f"📊 {symbol}")
            print(f"{'='*60}")
            
            # Получаем свечи
            candles = client.market_data.fetch_klines(
                symbol=symbol,
                interval="60",
                limit=150
            )
            
            if not candles:
                print(f"  ⚠️  Не удалось получить данные")
                continue
            
            df = pd.DataFrame(candles)
            df = compute_indicators(df)
            
            # Последние значения
            last = df.iloc[-1]
            price = last['close']
            
            # ADX
            adx = last.get('adx', np.nan)
            adx_status = "✅ RANGING" if adx < 25 else "❌ TRENDING (блокирует Grid)"
            
            # Bollinger Bands width
            bb_upper = last.get('bb_upper', np.nan)
            bb_lower = last.get('bb_lower', np.nan)
            bb_width = (bb_upper - bb_lower) / price if not np.isnan(bb_upper) else np.nan
            
            bb_status = "✅ OK" if 0.015 <= bb_width <= 0.05 else "❌ OUT OF RANGE"
            
            # Volume Z-score (для breakout protection)
            volume_mean = df['volume'].tail(20).mean()
            volume_std = df['volume'].tail(20).std()
            last_volume_z = (last['volume'] - volume_mean) / volume_std if volume_std > 0 else 0
            
            breakout_risk = "⚠️  HIGH (блокирует)" if last_volume_z > 2.0 else "✅ LOW"
            
            # Диапазон для Grid (последние 100 свечей)
            range_high = df['high'].tail(100).max()
            range_low = df['low'].tail(100).min()
            range_mid = (range_high + range_low) / 2
            range_percent = ((range_high - range_low) / range_mid) * 100
            
            position_in_range = ((price - range_low) / (range_high - range_low)) * 100
            
            print(f"\n💰 Текущая цена: ${price:,.2f}")
            print(f"\n📈 ИНДИКАТОРЫ:")
            print(f"  ADX: {adx:.1f} {adx_status}")
            print(f"  BB Width: {bb_width:.4f} (0.015-0.05) {bb_status}")
            print(f"  Volume Z-score: {last_volume_z:.2f} - Breakout risk: {breakout_risk}")
            
            print(f"\n📏 RANGE (последние 100 свечей):")
            print(f"  High: ${range_high:,.2f}")
            print(f"  Low:  ${range_low:,.2f}")
            print(f"  Ширина: {range_percent:.1f}%")
            print(f"  Цена в диапазоне: {position_in_range:.1f}% от низа")
            
            # Финальный вердикт
            print(f"\n{'─'*60}")
            print("🎯 ВЕРДИКТ:")
            
            conditions = []
            if adx >= 25:
                conditions.append("❌ ADX слишком высокий (тренд, не range)")
            if bb_width < 0.015:
                conditions.append("❌ BB слишком узкий (риск пробоя)")
            elif bb_width > 0.05:
                conditions.append("❌ BB слишком широкий (высокая волатильность)")
            if last_volume_z > 2.0:
                conditions.append("❌ Высокий объём (риск пробоя)")
            
            if not conditions:
                print("  ✅ ВСЕ УСЛОВИЯ ДЛЯ GRID TRADING ВЫПОЛНЕНЫ!")
                print("  → Стратегия должна генерировать сигналы")
            else:
                print("  ⚠️  GRID TRADING ЗАБЛОКИРОВАНА:")
                for cond in conditions:
                    print(f"     {cond}")
                
                print("\n  💡 РЕШЕНИЕ:")
                if any("ADX" in c for c in conditions):
                    print("     • Отключите require_ranging_market или увеличьте max_adx_for_range")
                if any("BB" in c for c in conditions):
                    print("     • Расширьте диапазон min_bb_width/max_bb_width")
                if any("объём" in c for c in conditions):
                    print("     • Отключите enable_breakout_protection")
        
        print(f"\n\n{'='*60}")
        print("💡 БЫСТРОЕ РЕШЕНИЕ:")
        print("   Запустите: python enable_grid_test_mode.py")
        print("   Это отключит все фильтры для тестирования")
        print("='*60}\n")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(check_market_conditions())
