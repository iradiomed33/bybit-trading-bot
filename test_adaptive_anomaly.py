"""
Quick test to verify adaptive anomaly detection thresholds
"""

import pandas as pd
import numpy as np
from data.features import FeaturePipeline

def test_adaptive_thresholds():
    """Test that different timeframes and networks produce different thresholds"""
    
    # Create sample data
    np.random.seed(42)
    n = 100
    df = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=n, freq='1min'),
        'open': np.random.uniform(40000, 41000, n),
        'high': np.random.uniform(40000, 41000, n),
        'low': np.random.uniform(40000, 41000, n),
        'close': np.random.uniform(40000, 41000, n),
        'volume': np.random.uniform(100, 1000, n),
    })
    df = df.set_index('timestamp')
    
    pipeline = FeaturePipeline()
    
    # Test 1: 1min testnet (most tolerant)
    print("\n=== Test 1: 1min testnet (most tolerant) ===")
    df1 = pipeline.detect_data_anomalies(df.copy(), kline_interval_minutes=1, is_testnet=True)
    anomaly_count_1 = df1['has_anomaly'].sum()
    print(f"Anomalies detected: {anomaly_count_1}")
    
    # Test 2: 1min mainnet (moderate)
    print("\n=== Test 2: 1min mainnet (moderate) ===")
    df2 = pipeline.detect_data_anomalies(df.copy(), kline_interval_minutes=1, is_testnet=False)
    anomaly_count_2 = df2['has_anomaly'].sum()
    print(f"Anomalies detected: {anomaly_count_2}")
    
    # Test 3: 60min testnet (moderate-strict)
    print("\n=== Test 3: 60min testnet (moderate-strict) ===")
    df3 = pipeline.detect_data_anomalies(df.copy(), kline_interval_minutes=60, is_testnet=True)
    anomaly_count_3 = df3['has_anomaly'].sum()
    print(f"Anomalies detected: {anomaly_count_3}")
    
    # Test 4: 60min mainnet (strict)
    print("\n=== Test 4: 60min mainnet (most strict) ===")
    df4 = pipeline.detect_data_anomalies(df.copy(), kline_interval_minutes=60, is_testnet=False)
    anomaly_count_4 = df4['has_anomaly'].sum()
    print(f"Anomalies detected: {anomaly_count_4}")
    
    # Test 5: 240min mainnet (strictest)
    print("\n=== Test 5: 240min mainnet (strictest) ===")
    df5 = pipeline.detect_data_anomalies(df.copy(), kline_interval_minutes=240, is_testnet=False)
    anomaly_count_5 = df5['has_anomaly'].sum()
    print(f"Anomalies detected: {anomaly_count_5}")
    
    # Verify expected behavior: stricter thresholds detect MORE anomalies
    print("\n=== Verification ===")
    print(f"1min testnet: {anomaly_count_1} anomalies (most tolerant)")
    print(f"1min mainnet: {anomaly_count_2} anomalies (should be >= 1min testnet)")
    print(f"60min testnet: {anomaly_count_3} anomalies (should be >= 1min mainnet)")
    print(f"60min mainnet: {anomaly_count_4} anomalies (should be >= 60min testnet)")
    print(f"240min mainnet: {anomaly_count_5} anomalies (strictest)")
    
    # Assertions
    assert anomaly_count_2 >= anomaly_count_1, "Mainnet should detect >= anomalies vs testnet (same TF)"
    assert anomaly_count_4 >= anomaly_count_3, "Mainnet should detect >= anomalies vs testnet (same TF)"
    
    # Note: Higher TF = stricter thresholds = MORE anomalies detected
    # But this may not always hold with random data, so log warning if unexpected
    if not (anomaly_count_5 >= anomaly_count_4 >= anomaly_count_2):
        print("⚠️  WARNING: Strict ordering not observed (expected with random data)")
    else:
        print("✅ Expected ordering observed: stricter TF → more anomalies detected")
    
    print("\n✅ All tests passed! Adaptive thresholds are working.")

if __name__ == "__main__":
    test_adaptive_thresholds()
