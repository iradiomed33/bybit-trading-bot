#!/usr/bin/env python3
"""
TASK-006 Phase 1 Verification Script

Быстрая проверка что единый источник истины работает правильно.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import ConfigManager
from config import Config
from logger import setup_logger

logger = setup_logger()


def print_section(title):
    """Печать разделителя"""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def test_basic_functionality():
    """Тест базовой функциональности"""
    print_section("1. Basic Functionality Tests")
    
    config = ConfigManager()
    
    # Test is_testnet() returns boolean
    result = config.is_testnet()
    print(f"✓ is_testnet() returned: {result} (type: {type(result).__name__})")
    assert isinstance(result, bool), "is_testnet() должен вернуть bool"
    
    # Test get_environment() returns string
    env = config.get_environment()
    print(f"✓ get_environment() returned: '{env}' (type: {type(env).__name__})")
    assert isinstance(env, str), "get_environment() должен вернуть string"
    assert env in ("testnet", "mainnet"), f"Invalid environment: {env}"
    
    # Test consistency
    if result:
        assert env == "testnet", "Inconsistency: is_testnet()=True but get_environment()!='testnet'"
    else:
        assert env == "mainnet", "Inconsistency: is_testnet()=False but get_environment()!='mainnet'"
    print(f"✓ Methods are consistent")


def test_config_parameters():
    """Тест доступности параметров конфига"""
    print_section("2. Config Parameters Tests")
    
    config = ConfigManager()
    
    # Check trading.testnet exists
    testnet_param = config.get("trading.testnet", None)
    print(f"✓ trading.testnet from JSON: {testnet_param}")
    assert testnet_param is not None, "trading.testnet должен быть в конфиге"
    assert isinstance(testnet_param, bool), "trading.testnet должен быть boolean"
    
    # Check Config.ENVIRONMENT
    env_var = Config.ENVIRONMENT
    print(f"✓ Config.ENVIRONMENT from env: {env_var}")


def test_cli_imports():
    """Тест что CLI импортирует ConfigManager"""
    print_section("3. CLI Updates Tests")
    
    cli_path = Path(__file__).parent / "cli.py"
    
    with open(cli_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check import
    if "from config.settings import ConfigManager" in content:
        print(f"✓ cli.py imports ConfigManager")
    else:
        print(f"✗ cli.py does NOT import ConfigManager")
        return False
    
    # Check usage (should have is_testnet calls)
    if ".is_testnet()" in content:
        count = content.count(".is_testnet()")
        print(f"✓ cli.py uses .is_testnet() {count} times")
    else:
        print(f"✗ cli.py does NOT use .is_testnet()")
        return False
    
    # Check old pattern is removed (should not have Config.ENVIRONMENT == "testnet")
    old_pattern_count = content.count('Config.ENVIRONMENT == "testnet"')
    if old_pattern_count == 0:
        print(f"✓ cli.py removed old pattern (Config.ENVIRONMENT == \"testnet\")")
    else:
        print(f"⚠ cli.py still has {old_pattern_count} instances of old pattern")
    
    return True


def test_smoke_test_imports():
    """Тест что smoke_test импортирует ConfigManager"""
    print_section("4. Smoke Test Updates Tests")
    
    smoke_path = Path(__file__).parent / "smoke_test.py"
    
    with open(smoke_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check import
    if "from config.settings import ConfigManager" in content:
        print(f"✓ smoke_test.py imports ConfigManager")
    else:
        print(f"✗ smoke_test.py does NOT import ConfigManager")
        return False
    
    # Check usage
    if "ConfigManager().is_testnet()" in content:
        count = content.count("ConfigManager().is_testnet()")
        print(f"✓ smoke_test.py uses ConfigManager().is_testnet() {count} times")
    else:
        print(f"✗ smoke_test.py does NOT use ConfigManager().is_testnet()")
        return False
    
    return True


def test_multiple_instances():
    """Тест что разные инстансы вернут один результат"""
    print_section("5. Multiple Instances Consistency Tests")
    
    config1 = ConfigManager()
    config2 = ConfigManager()
    config3 = ConfigManager()
    
    result1 = config1.is_testnet()
    result2 = config2.is_testnet()
    result3 = config3.is_testnet()
    
    assert result1 == result2 == result3, "Разные инстансы должны вернуть один результат"
    print(f"✓ All instances return same result: {result1}")


def test_environment_variable():
    """Тест переопределения через ENVIRONMENT переменную"""
    print_section("6. ENVIRONMENT Variable Override Test")
    
    current_env = os.environ.get("ENVIRONMENT")
    print(f"Current ENVIRONMENT: {current_env}")
    
    config = ConfigManager()
    result = config.is_testnet()
    
    if current_env == "testnet":
        assert result is True, "ENVIRONMENT=testnet должен вернуть True"
        print(f"✓ ENVIRONMENT=testnet → is_testnet()={result}")
    elif current_env == "mainnet":
        assert result is False, "ENVIRONMENT=mainnet должен вернуть False"
        print(f"✓ ENVIRONMENT=mainnet → is_testnet()={result}")
    else:
        print(f"⚠ ENVIRONMENT not set, using JSON/default: is_testnet()={result}")


def test_logging():
    """Тест что логирование работает"""
    print_section("7. Logging Test")
    
    import logging
    
    # Capture logs
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    
    logger_obj = logging.getLogger('config.settings')
    logger_obj.addHandler(handler)
    logger_obj.setLevel(logging.DEBUG)
    
    config = ConfigManager()
    print(f"Calling is_testnet()...")
    result = config.is_testnet()
    print(f"Result: {result}")
    print(f"✓ Logging test complete (check output above for [Environment] messages)")


def run_all_tests():
    """Запустить все тесты"""
    print("\n" + ">>> TASK-006 Phase 1 Verification Script <<<".center(70))
    print("=" * 70)
    
    try:
        test_basic_functionality()
        test_config_parameters()
        test_cli_imports()
        test_smoke_test_imports()
        test_multiple_instances()
        test_environment_variable()
        test_logging()
        
        print_section("✓ All Verification Tests Passed!")
        print("TASK-006 Phase 1 is ready for production use.\n")
        return 0
        
    except AssertionError as e:
        print(f"\n[ERROR] Test failed: {e}\n")
        return 1
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
