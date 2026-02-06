#!/usr/bin/env python3
"""
Smoke test для проверки правильности порядка инициализации в live режиме.
Проверяет, что OrderManager создаётся перед StopLossTakeProfitManager.
"""

import sys


def test_initialization_order():
    """
    Читает код trading_bot.py и проверяет, что order_manager 
    инициализируется перед sl_tp_manager
    """
    print("="*70)
    print("SMOKE TEST: Live Initialization Order")
    print("="*70)
    
    try:
        import ast
        import re
        
        with open('bot/trading_bot.py', 'r') as f:
            content = f.read()
        
        # Разбиваем на строки для более надёжной проверки
        lines = content.split('\n')
        
        order_manager_line = None
        sl_tp_manager_line = None
        
        for i, line in enumerate(lines):
            # Проверяем присваивание order_manager (игнорируем пробелы)
            if re.search(r'self\.order_manager\s*=\s*OrderManager', line):
                if order_manager_line is None:  # Берём первое вхождение
                    order_manager_line = i
                    
            # Проверяем присваивание sl_tp_manager (игнорируем пробелы)
            if re.search(r'self\.sl_tp_manager\s*=\s*StopLossTakeProfitManager', line):
                if sl_tp_manager_line is None:  # Берём первое вхождение
                    sl_tp_manager_line = i
        
        print(f"\n✓ Строка создания order_manager: {order_manager_line + 1 if order_manager_line is not None else 'не найдено'}")
        print(f"✓ Строка создания sl_tp_manager: {sl_tp_manager_line + 1 if sl_tp_manager_line is not None else 'не найдено'}")
        
        if order_manager_line is None:
            print("\n❌ ОШИБКА: Не найдено создание order_manager")
            return False
            
        if sl_tp_manager_line is None:
            print("\n❌ ОШИБКА: Не найдено создание sl_tp_manager")
            return False
        
        if order_manager_line < sl_tp_manager_line:
            print("\n✓✓✓ УСПЕХ: order_manager создаётся ПЕРЕД sl_tp_manager")
            print(f"✓ Разница: {sl_tp_manager_line - order_manager_line} строк")
            
            # Проверим также, что rest_client создаётся один раз
            # Примечание: проверяет только паттерн 'rest_client = BybitRestClient(...)'
            rest_client_count = len(re.findall(r'rest_client\s*=\s*BybitRestClient\s*\(', content))
            print(f"\n✓ Количество создания rest_client (паттерн 'rest_client = BybitRestClient(...)'): {rest_client_count}")
            
            if rest_client_count == 1:
                print("✓ ОТЛИЧНО: rest_client создаётся один раз (оптимизация)")
            elif rest_client_count == 0:
                print("⚠ Предупреждение: паттерн создания rest_client не найден (возможно изменился)")
            else:
                print(f"⚠ Предупреждение: найдено {rest_client_count} создания(й) rest_client")
            
            print("\n" + "="*70)
            print("РЕЗУЛЬТАТ: ✓ ТЕСТ ПРОЙДЕН")
            print("="*70)
            return True
        else:
            print("\n❌❌❌ ОШИБКА: sl_tp_manager создаётся ПЕРЕД order_manager")
            print("❌ Это вызовет AttributeError при запуске в live режиме!")
            print("\n" + "="*70)
            print("РЕЗУЛЬТАТ: ❌ ТЕСТ НЕ ПРОЙДЕН")
            print("="*70)
            return False
            
    except FileNotFoundError:
        print("❌ ОШИБКА: Файл bot/trading_bot.py не найден")
        return False
    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Запуск smoke-теста"""
    success = test_initialization_order()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
