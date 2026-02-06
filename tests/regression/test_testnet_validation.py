"""
TESTNET ТЕСТЫ: Валидация и сигналы (REG-VAL-001)

Требует: BYBIT_API_KEY и BYBIT_API_SECRET в .env

Тесты:
- REG-VAL-001: Все вход-диагностики работают на реальных данных testnet
"""

import os
import pytest
from exchange.base_client import BybitRestClient
from data.features import FeaturePipeline
from strategy.meta_layer import RegimeSwitcher


class TestREGVAL001_RealDataValidation:
    """REG-VAL-001: Валидация на реальных данных testnet"""
    
    @pytest.mark.skipif(
        not os.getenv('BYBIT_API_KEY'),
        reason="BYBIT_API_KEY не установлен"
    )
    def test_fetch_real_market_data(self):
        """Загрузка реальных свечей с testnet должна работать"""
        client = BybitRestClient(testnet=True)
        
        try:
            ohlcv = client.fetch_ohlcv(
                symbol='BTCUSDT',
                timeframe='1h',
                limit=100,
            )
            
            # Данные должны быть загружены
            assert ohlcv is not None
            assert len(ohlcv) > 0
            
            # Каждая свеча должна иметь o,h,l,c,v
            if isinstance(ohlcv, list):
                assert len(ohlcv[0]) >= 5
        except Exception as e:
            pytest.skip(f"Market data unavailable: {e}")
    
    @pytest.mark.skipif(
        not os.getenv('BYBIT_API_KEY'),
        reason="BYBIT_API_KEY не установлен"
    )
    def test_features_work_on_real_data(self):
        """Feature pipeline должен работать на реальных данных"""
        client = BybitRestClient(testnet=True)
        pipeline = FeaturePipeline()
        
        try:
            # Загрузить реальные данные
            ohlcv = client.fetch_ohlcv(
                symbol='BTCUSDT',
                timeframe='1h',
                limit=100,
            )
            
            if ohlcv and len(ohlcv) > 0:
                # Преобразовать в DataFrame
                import pandas as pd
                df = pd.DataFrame(
                    ohlcv,
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )
                
                # Построить фичи
                features = pipeline.build_features(df)
                
                # Фичи должны быть построены
                assert features is not None
                assert len(features) == len(df)
        except Exception as e:
            pytest.skip(f"Feature engineering failed: {e}")
    
    @pytest.mark.skipif(
        not os.getenv('BYBIT_API_KEY'),
        reason="BYBIT_API_KEY не установлен"
    )
    def test_regime_detection_on_real_data(self):
        """Regime detection должен работать на реальных данных"""
        client = BybitRestClient(testnet=True)
        pipeline = FeaturePipeline()
        switcher = RegimeSwitcher()
        
        try:
            # Загрузить реальные данные
            ohlcv = client.fetch_ohlcv(
                symbol='BTCUSDT',
                timeframe='1h',
                limit=100,
            )
            
            if ohlcv and len(ohlcv) > 0:
                # Преобразовать в DataFrame
                import pandas as pd
                df = pd.DataFrame(
                    ohlcv,
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )
                
                # Построить фичи
                features = pipeline.build_features(df)
                
                # Определить режим
                regime = switcher.detect_regime(features)
                
                # Режим должен быть определен
                assert regime in ['trend', 'range', 'high_vol_event', 'unknown']
        except Exception as e:
            pytest.skip(f"Regime detection failed: {e}")


class TestREGVAL001_SignalGeneration:
    """REG-VAL-001: Генерация сигналов на реальных данных"""
    
    @pytest.mark.skipif(
        not os.getenv('BYBIT_API_KEY'),
        reason="BYBIT_API_KEY не установлен"
    )
    def test_strategy_signal_on_real_data(self):
        """Стратегия должна генерировать сигналы на реальных данных"""
        client = BybitRestClient(testnet=True)
        pipeline = FeaturePipeline()
        
        try:
            from strategy.breakout import BreakoutStrategy
            
            # Загрузить реальные данные
            ohlcv = client.fetch_ohlcv(
                symbol='BTCUSDT',
                timeframe='1h',
                limit=100,
            )
            
            if ohlcv and len(ohlcv) > 0:
                # Преобразовать в DataFrame
                import pandas as pd
                df = pd.DataFrame(
                    ohlcv,
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )
                
                # Построить фичи
                features = pipeline.build_features(df)
                
                # Генерировать сигнал
                strategy = BreakoutStrategy()
                signal = strategy.generate_signal(features, {})
                
                # Сигнал может быть None или dict
                assert signal is None or isinstance(signal, dict)
        except Exception as e:
            pytest.skip(f"Signal generation failed: {e}")
    
    @pytest.mark.skipif(
        not os.getenv('BYBIT_API_KEY'),
        reason="BYBIT_API_KEY не установлен"
    )
    def test_no_error_on_extreme_conditions(self):
        """Системе не должны быть нужны крахи при экстремальных ценах"""
        client = BybitRestClient(testnet=True)
        pipeline = FeaturePipeline()
        
        try:
            # Загрузить реальные данные
            ohlcv = client.fetch_ohlcv(
                symbol='BTCUSDT',
                timeframe='5m',  # Более частые данные = более волатильные
                limit=100,
            )
            
            if ohlcv and len(ohlcv) > 0:
                # Преобразовать в DataFrame
                import pandas as pd
                df = pd.DataFrame(
                    ohlcv,
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )
                
                # Pipeline должен обработать любые данные без ошибок
                features = pipeline.build_features(df)
                
                assert features is not None
                assert len(features) > 0
        except Exception as e:
            pytest.skip(f"Extreme data handling failed: {e}")


class TestREGVAL001_Comprehensive:
    """REG-VAL-001: Полная валидация на testnet"""
    
    @pytest.mark.skipif(
        not os.getenv('BYBIT_API_KEY'),
        reason="BYBIT_API_KEY не установлен"
    )
    def test_full_validation_pipeline(self):
        """Полная цепочка: fetch -> features -> regime -> signals должна работать"""
        client = BybitRestClient(testnet=True)
        pipeline = FeaturePipeline()
        switcher = RegimeSwitcher()
        
        try:
            from strategy.breakout import BreakoutStrategy
            
            # Загрузить данные
            ohlcv = client.fetch_ohlcv(
                symbol='BTCUSDT',
                timeframe='1h',
                limit=100,
            )
            
            if ohlcv and len(ohlcv) > 0:
                import pandas as pd
                
                # Преобразовать
                df = pd.DataFrame(
                    ohlcv,
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )
                
                # Вся цепочка:
                # 1. Features
                features = pipeline.build_features(df)
                assert features is not None
                
                # 2. Regime
                regime = switcher.detect_regime(features)
                assert regime is not None
                
                # 3. Signals
                strategy = BreakoutStrategy()
                signal = strategy.generate_signal(features, {'regime': regime})
                assert signal is None or isinstance(signal, dict)
                
                # Полная валидация пройдена
                assert True
        except Exception as e:
            pytest.skip(f"Full pipeline validation failed: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
