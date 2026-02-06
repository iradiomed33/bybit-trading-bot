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
        with open('bot/trading_bot.py', 'r') as f:
            content = f.read()
        
        # Находим позиции создания компонентов
        order_manager_pos = content.find('self.order_manager = OrderManager')
        sl_tp_manager_pos = content.find('self.sl_tp_manager = StopLossTakeProfitManager')
        
        print(f"\n✓ Позиция создания order_manager: {order_manager_pos}")
        print(f"✓ Позиция создания sl_tp_manager: {sl_tp_manager_pos}")
        
        if order_manager_pos < 0:
            print("\n❌ ОШИБКА: Не найдено создание order_manager")
            return False
            
        if sl_tp_manager_pos < 0:
            print("\n❌ ОШИБКА: Не найдено создание sl_tp_manager")
            return False
        
        if order_manager_pos < sl_tp_manager_pos:
            print("\n✓✓✓ УСПЕХ: order_manager создаётся ПЕРЕД sl_tp_manager")
            print(f"✓ Разница позиций: {sl_tp_manager_pos - order_manager_pos} символов")
            
            # Проверим также, что rest_client создаётся один раз
            rest_client_count = content.count('rest_client = BybitRestClient(testnet=testnet)')
            print(f"\n✓ Количество создания rest_client: {rest_client_count}")
            
            if rest_client_count == 1:
                print("✓ ОТЛИЧНО: rest_client создаётся один раз (оптимизация)")
            else:
                print(f"⚠ Предупреждение: rest_client создаётся {rest_client_count} раз(а)")
            
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
