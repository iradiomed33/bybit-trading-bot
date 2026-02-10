"""
Тестовый скрипт для проверки значения mode из конфигурации
"""

from config.settings import get_config
import json

# Получаем конфиг
cfg = get_config()

print("="*60)
print("ТЕСТ КОНФИГУРАЦИИ")
print("="*60)

print(f"\nПуть к конфигу: {cfg.config_path}")
print(f"Файл существует: {cfg.config_path}")

print(f"\ntрading.mode из get(): {cfg.get('trading.mode')}")
print(f"trading.testnet из get(): {cfg.get('trading.testnet')}")
print(f"trading.symbol из get(): {cfg.get('trading.symbol')}")
print(f"trading.symbols из get(): {cfg.get('trading.symbols')}")

print("\nВесь раздел trading:")
print(json.dumps(cfg.get_section('trading'), indent=2, ensure_ascii=False))

print("\n" + "="*60)
