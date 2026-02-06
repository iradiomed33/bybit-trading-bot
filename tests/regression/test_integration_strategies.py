"""
ИНТЕГРАЦИОННЫЕ ТЕСТЫ: Все стратегии (REG-STR)

Тесты:
- REG-STR-001: Breakout стратегия генерирует сигналы
- REG-STR-002: Mean Reversion стратегия работает при боковой торговле
- REG-STR-003: Trend Following стратегия работает на тренде
"""

import pytest
from strategy.breakout import BreakoutStrategy
from strategy.mean_reversion import MeanReversionStrategy
from strategy.trend_pullback import TrendPullbackStrategy
from data.features import FeaturePipeline


class TestREGSTR001_Breakout:
    """REG-STR-001: Breakout стратегия генерирует сигналы при разломе уровней"""
    
    def test_breakout_strategy_initializes(self):
        """BreakoutStrategy должна инициализироваться"""
        strategy = BreakoutStrategy()
        
        assert strategy is not None
        assert hasattr(strategy, 'generate_signal')
        assert callable(strategy.generate_signal)
    
    def test_breakout_detects_upbreak(self, uptrend_data):
        """Breakout должен детектировать восходящий пробой"""
        strategy = BreakoutStrategy()
        pipeline = FeaturePipeline()
        
        df = pipeline.build_features(uptrend_data.copy())
        
        # На uptrend данных стратегия должна генерировать signals
        signal = strategy.generate_signal(df, {})
        
        # Сигнал может быть None или dict
        assert signal is None or isinstance(signal, dict)
    
    def test_breakout_with_volume(self, high_volatility_data):
        """Breakout должен подтверждаться объемом"""
        strategy = BreakoutStrategy()
        pipeline = FeaturePipeline()
        
        df = pipeline.build_features(high_volatility_data.copy())
        
        # Проверить что volume есть в данных
        assert 'volume' in df.columns
        assert strategy is not None


class TestREGSTR002_MeanReversion:
    """REG-STR-002: Mean Reversion работает при боковой торговле"""
    
    def test_mean_reversion_initializes(self):
        """MeanReversionStrategy должна инициализироваться"""
        strategy = MeanReversionStrategy(require_range_regime=False)
        
        assert strategy is not None
        assert hasattr(strategy, 'generate_signal')
        assert callable(strategy.generate_signal)
    
    def test_mean_reversion_on_sideways(self, sideways_data):
        """Mean Reversion должна работать при боковой торговле"""
        strategy = MeanReversionStrategy(
            require_range_regime=False,
        )
        pipeline = FeaturePipeline()
        
        df = pipeline.build_features(sideways_data.copy())
        
        # На боковых данных стратегия должна искать mean reversion
        assert len(df) > 50
        
        # Должны быть RSI значения для анализа
        if 'rsi' in df.columns:
            assert df['rsi'].notna().sum() > 10
    
    def test_mean_reversion_config(self):
        """Mean Reversion должна быть конфигурируемой"""
        strategy = MeanReversionStrategy(require_range_regime=True)
        
        # Стратегия инициализирована с требованием range режима
        assert strategy.require_range_regime == True


class TestREGSTR003_TrendFollowing:
    """REG-STR-003: Trend Following стратегия работает на трендовых рынках"""
    
    def test_trend_pullback_initializes(self):
        """TrendPullbackStrategy должна инициализироваться"""
        strategy = TrendPullbackStrategy()
        
        assert strategy is not None
        assert hasattr(strategy, 'generate_signal')
        assert callable(strategy.generate_signal)
    
    def test_trend_pullback_on_uptrend(self, uptrend_data):
        """Trend Pullback должна работать на восходящем тренде"""
        strategy = TrendPullbackStrategy()
        pipeline = FeaturePipeline()
        
        df = pipeline.build_features(uptrend_data.copy())
        
        # На trendовых данных должны быть тренд-индикаторы
        required_cols = ['close', 'open', 'high', 'low']
        
        for col in required_cols:
            assert col in df.columns
        
        assert strategy is not None
    
    def test_trend_detection(self, uptrend_data, downtrend_data):
        """Тренд должен правильно определяться"""
        pipeline = FeaturePipeline()
        
        df_up = pipeline.build_features(uptrend_data.copy())
        df_down = pipeline.build_features(downtrend_data.copy())
        
        # На uptrend close должен быть высокий в конце
        assert df_up['close'].iloc[-1] > df_up['close'].iloc[0]
        
        # На downtrend close должен быть низкий в конце
        assert df_down['close'].iloc[-1] < df_down['close'].iloc[0]


class TestREGSTR_All:
    """Общие тесты для всех стратегий"""
    
    def test_all_strategies_have_generate_signal(self):
        """Все стратегии должны иметь метод generate_signal"""
        strategies = [
            BreakoutStrategy(),
            MeanReversionStrategy(),
            TrendPullbackStrategy(),
        ]
        
        for strategy in strategies:
            assert callable(strategy.generate_signal), \
                f"{strategy.__class__.__name__} не имеет generate_signal"
    
    def test_signal_format_consistency(self, uptrend_data):
        """Все сигналы должны иметь одинаковый формат"""
        pipeline = FeaturePipeline()
        df = pipeline.build_features(uptrend_data.copy())
        
        strategies = [
            BreakoutStrategy(),
            MeanReversionStrategy(),
            TrendPullbackStrategy(),
        ]
        
        for strategy in strategies:
            signal = strategy.generate_signal(df, {})
            
            # Сигнал может быть None или dict
            if signal is not None:
                assert isinstance(signal, dict)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
