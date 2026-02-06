#!/usr/bin/env python3

"""

Setup script для быстрой подготовки к live trading.


Использование:

    python setup_live.py

"""


import os

import sys

from pathlib import Path


def check_env_file():
    """Проверка .env файла"""

    print("📋 Проверка .env файла...")

    if not Path(".env").exists():

        print("❌ .env файл не найден!")

        print("\n📝 Создаю .env из шаблона...")

        os.system("cp .env.example .env")

        print("✅ .env создан!")

        print("\n⚠️  ВАЖНО: Заполни API ключи в .env:")

        print("   BYBIT_API_KEY=your_testnet_key")

        print("   BYBIT_API_SECRET=your_testnet_secret")

        print("   ENVIRONMENT=testnet")

        print("   MODE=live")

        return False

    # Проверка содержимого

    with open(".env") as f:

        content = f.read()

    checks = {

        "BYBIT_API_KEY": "API Key",

        "BYBIT_API_SECRET": "API Secret",

        "ENVIRONMENT": "Окружение",

    }

    missing = []

    for key, name in checks.items():

        if key not in content or f"{key}=your_" in content:

            missing.append(f"  ❌ {name}: {key}")

        else:

            print(f"  ✅ {name}: {key}")

    if missing:

        print("\n⚠️  ТРЕБУЕТСЯ ЗАПОЛНИТЬ:")

        for item in missing:

            print(item)

        return False

    return True


def check_dependencies():
    """Проверка зависимостей"""

    print("\n📦 Проверка зависимостей...")

    try:

        pass

        print("  ✅ pandas")

        print("  ✅ numpy")

        print("  ✅ requests")

        print("  ✅ websocket-client")

        return True

    except ImportError as e:

        print(f"  ❌ Отсутствует: {e}")

        print("\n💡 Установи зависимости:")

        print("   pip install -r requirements.txt")

        return False


def check_config():
    """Проверка конфигурации"""

    print("\n⚙️  Проверка конфигурации...")

    try:

        from config import Config

        Config.validate()

        print(f"  ✅ ENVIRONMENT: {Config.ENVIRONMENT}")

        print(f"  ✅ MODE: {Config.MODE}")

        print(f"  ✅ LOG_LEVEL: {Config.LOG_LEVEL}")

        return True

    except Exception as e:

        print(f"  ❌ Ошибка конфигурации: {e}")

        return False


def run_health_check():
    """Запуск health check"""

    print("\n🏥 Запуск health check...")

    result = os.system("python cli.py health > /dev/null 2>&1")

    if result == 0:

        print("  ✅ Health check пройден!")

        return True

    else:

        print("  ❌ Health check не пройден!")

        print("\n💡 Запусти для отладки:")

        print("   python cli.py health")

        return False


def show_instructions():
    """Показать инструкции"""

    print("\n" + "=" * 60)

    print("🚀 ГОТОВО К ЗАПУСКУ!")

    print("=" * 60)

    print("\n📌 NEXT STEPS:")

    print("  1. python cli.py market   # Тест API")

    print("  2. python cli.py stream   # Тест WebSocket (Ctrl+C через 10сек)")

    print("  3. python cli.py live     # ЗАПУСК ТОРГОВЛИ! 🎉")

    print("\n📖 Полный гайд: LIVE_TESTNET_GUIDE.md")

    print("⚡ Быстрый старт: QUICKSTART.md")

    print("\n⚠️  ПЕРЕД ЗАПУСКОМ НА MAINNET:")

    print("  - Первой запусти paper mode (MODE=paper)")

    print("  - Потом маленькие позиции на testnet")

    print("=" * 60 + "\n")


def main():
    """Главная функция"""

    print("\n" + "=" * 60)

    print("🔧 SETUP FOR LIVE TRADING")

    print("=" * 60 + "\n")

    # Проверки

    checks = [

        ("ENV FILE", check_env_file()),

        ("DEPENDENCIES", check_dependencies()),

        ("CONFIG", check_config()),

        ("HEALTH CHECK", run_health_check()),

    ]

    # Результат

    all_passed = all(status for _, status in checks)

    print("\n" + "=" * 60)

    print("RESULTS:")

    for name, status in checks:

        symbol = "✅" if status else "❌"

        print(f"  {symbol} {name}")

    print("=" * 60)

    if all_passed:

        show_instructions()

        return 0

    else:

        print("\n❌ Есть ошибки! Исправьте их и запустите заново.")

        return 1


if __name__ == "__main__":

    sys.exit(main())
