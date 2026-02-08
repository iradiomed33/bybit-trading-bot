#!/usr/bin/env python
"""
Скрипт для сброса Kill Switch.

Использование:
    python reset_killswitch.py

Этот скрипт сбрасывает оба механизма kill switch:
1. KillSwitch (risk/kill_switch.py) - удаляет записи из таблицы errors
2. KillSwitchManager (execution/kill_switch.py) - очищает флаг trading_disabled

После запуска этого скрипта бот можно запустить снова.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage.database import Database
from risk.kill_switch import KillSwitch
from logger import setup_logger

logger = setup_logger(__name__)


def reset_killswitch():
    """Сброс kill switch через командную строку"""
    
    print("=" * 70)
    print("СБРОС KILL SWITCH")
    print("=" * 70)
    print()
    
    # Найти базу данных
    db_path = "storage/bot_state.db"
    if not os.path.exists(db_path):
        print(f"❌ База данных не найдена: {db_path}")
        print("   Убедитесь, что вы запускаете скрипт из корневой директории проекта")
        return False
    
    print(f"✓ База данных найдена: {db_path}")
    print()
    
    try:
        # Создать подключение к БД
        db = Database(db_path=db_path)
        print("✓ Подключение к базе данных установлено")
        print()
        
        # 1. Проверить текущий статус kill switch
        print("1️⃣  Проверка текущего статуса...")
        kill_switch = KillSwitch(db)
        is_active = kill_switch.check_status()
        
        if is_active:
            print("   ⚠️  Kill switch АКТИВИРОВАН (найдены записи в БД)")
        else:
            print("   ✓ Kill switch не активирован")
        
        # Проверить флаг trading_disabled
        trading_disabled = db.get_config("trading_disabled", False)
        if trading_disabled:
            print("   ⚠️  Флаг trading_disabled установлен в TRUE")
        else:
            print("   ✓ Флаг trading_disabled не установлен")
        
        print()
        
        # Если оба флага в порядке
        if not is_active and not trading_disabled:
            print("✅ Kill switch уже сброшен. Бот можно запускать.")
            return True
        
        # 2. Запросить подтверждение
        print("2️⃣  Требуется подтверждение для сброса kill switch")
        print()
        print("   ВНИМАНИЕ: Это удалит все записи активации kill switch из БД")
        print("   и очистит флаг trading_disabled.")
        print()
        
        confirmation = input("   Введите 'RESET' для подтверждения сброса: ").strip()
        print()
        
        if confirmation != "RESET":
            print("❌ Неверный код подтверждения. Сброс отменен.")
            return False
        
        # 3. Сброс старого KillSwitch (таблица errors)
        print("3️⃣  Сброс KillSwitch (таблица errors)...")
        success_old = kill_switch.reset("RESET")
        
        if success_old:
            print("   ✅ KillSwitch успешно сброшен")
        else:
            print("   ❌ Не удалось сбросить KillSwitch")
        
        print()
        
        # 4. Сброс флага trading_disabled
        print("4️⃣  Сброс флага trading_disabled...")
        try:
            db.save_config("trading_disabled", False)
            print("   ✅ Флаг trading_disabled очищен")
            success_manager = True
        except Exception as e:
            print(f"   ❌ Ошибка при очистке флага: {e}")
            success_manager = False
        
        print()
        
        # 5. Проверка результата
        print("5️⃣  Проверка результата...")
        kill_switch_verify = KillSwitch(db)
        is_active_after = kill_switch_verify.check_status()
        trading_disabled_after = db.get_config("trading_disabled", False)
        
        if not is_active_after:
            print("   ✅ KillSwitch не активирован")
        else:
            print("   ❌ KillSwitch все еще активирован!")
        
        if not trading_disabled_after:
            print("   ✅ Флаг trading_disabled очищен")
        else:
            print("   ❌ Флаг trading_disabled все еще установлен!")
        
        print()
        
        # Итоговый результат
        if success_old and success_manager and not is_active_after and not trading_disabled_after:
            print("=" * 70)
            print("✅ СБРОС УСПЕШНО ЗАВЕРШЕН!")
            print("=" * 70)
            print()
            print("Бот теперь можно запустить.")
            print()
            return True
        else:
            print("=" * 70)
            print("⚠️  СБРОС ЗАВЕРШЕН С ОШИБКАМИ")
            print("=" * 70)
            print()
            print("Проверьте логи выше для деталей.")
            print()
            return False
        
    except Exception as e:
        print()
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            db.close()
        except:
            pass


if __name__ == "__main__":
    print()
    success = reset_killswitch()
    print()
    sys.exit(0 if success else 1)
