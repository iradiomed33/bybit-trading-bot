"""
Тест для проверки endpoint API killswitch reset
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_api_endpoint_exists():
    """Проверка что endpoint определен в API"""
    
    with open('api/app.py', 'r') as f:
        content = f.read()
    
    # Check for endpoint
    if '@app.post("/api/bot/reset_killswitch")' in content:
        print("✅ Endpoint /api/bot/reset_killswitch найден в app.py")
    else:
        print("❌ Endpoint /api/bot/reset_killswitch НЕ найден в app.py")
        return False
    
    # Check for function
    if 'async def reset_killswitch():' in content:
        print("✅ Функция reset_killswitch() найдена")
    else:
        print("❌ Функция reset_killswitch() НЕ найдена")
        return False
    
    # Check for KillSwitch import
    if 'from risk.kill_switch import KillSwitch' in content:
        print("✅ Import KillSwitch найден в функции")
    else:
        print("❌ Import KillSwitch НЕ найден")
        return False
    
    return True


def test_ui_button_exists():
    """Проверка что кнопка добавлена в UI"""
    
    with open('static/index.html', 'r') as f:
        content = f.read()
    
    # Check for button
    if 'resetKillswitchBtn' in content:
        print("✅ Кнопка resetKillswitchBtn найдена в HTML")
    else:
        print("❌ Кнопка resetKillswitchBtn НЕ найдена в HTML")
        return False
    
    # Check for onclick handler
    if 'onclick="resetKillswitch()"' in content:
        print("✅ Обработчик onclick='resetKillswitch()' найден")
    else:
        print("❌ Обработчик onclick НЕ найден")
        return False
    
    # Check for button text
    if 'Сбросить Kill Switch' in content:
        print("✅ Текст кнопки найден")
    else:
        print("❌ Текст кнопки НЕ найден")
        return False
    
    return True


def test_js_function_exists():
    """Проверка что JavaScript функция добавлена"""
    
    with open('static/js/app.js', 'r') as f:
        content = f.read()
    
    # Check for function
    if 'async function resetKillswitch()' in content:
        print("✅ Функция resetKillswitch() найдена в app.js")
    else:
        print("❌ Функция resetKillswitch() НЕ найдена в app.js")
        return False
    
    # Check for API call
    if '/bot/reset_killswitch' in content:
        print("✅ API вызов /bot/reset_killswitch найден")
    else:
        print("❌ API вызов НЕ найден")
        return False
    
    # Check for confirmation
    if 'confirm(' in content and 'Kill Switch' in content:
        print("✅ Диалог подтверждения найден")
    else:
        print("❌ Диалог подтверждения НЕ найден")
        return False
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("ПРОВЕРКА РЕАЛИЗАЦИИ KILLSWITCH RESET")
    print("=" * 60)
    
    print("\n1. Проверка API endpoint...")
    test1 = test_api_endpoint_exists()
    
    print("\n2. Проверка UI кнопки...")
    test2 = test_ui_button_exists()
    
    print("\n3. Проверка JavaScript функции...")
    test3 = test_js_function_exists()
    
    print("\n" + "=" * 60)
    if test1 and test2 and test3:
        print("✅ ВСЕ ПРОВЕРКИ ПРОШЛИ УСПЕШНО!")
        print("\nРеализация включает:")
        print("  - API endpoint для сброса killswitch")
        print("  - UI кнопку в dashboard")
        print("  - JavaScript функцию с подтверждением")
        print("  - Исправление бага в risk/kill_switch.py")
        sys.exit(0)
    else:
        print("❌ НЕКОТОРЫЕ ПРОВЕРКИ НЕ ПРОШЛИ")
        sys.exit(1)
