"""
Тест для проверки исправления killswitch reset
"""

import sys
import os
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage.database import Database
from risk.kill_switch import KillSwitch


def test_killswitch_reset():
    """Тест сброса killswitch"""
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Create database instance
        db = Database(db_path=db_path)
        
        # Create kill switch
        kill_switch = KillSwitch(db)
        
        # 1. Activate kill switch
        print("1. Активация kill switch...")
        kill_switch.activate("Test activation")
        
        # 2. Check status - should be activated
        print("2. Проверка статуса после активации...")
        is_active = kill_switch.check_status()
        assert is_active, "Kill switch должен быть активирован"
        print("   ✅ Kill switch активирован")
        
        # 3. Reset kill switch
        print("3. Сброс kill switch...")
        result = kill_switch.reset("RESET")
        assert result is True, "Сброс должен быть успешным"
        print("   ✅ Kill switch сброшен")
        
        # 4. Create new instance to test persistence
        print("4. Создание нового экземпляра для проверки персистентности...")
        kill_switch2 = KillSwitch(db)
        
        # 5. Check status - should NOT be activated
        print("5. Проверка статуса после сброса...")
        is_active_after_reset = kill_switch2.check_status()
        
        if is_active_after_reset:
            print("   ❌ ОШИБКА: Kill switch все еще активирован после сброса!")
            print("   Это означает, что записи не были удалены из БД")
            
            # Debug: check database
            cursor = db.conn.cursor()
            cursor.execute("SELECT * FROM errors WHERE error_type = 'kill_switch_activated'")
            records = cursor.fetchall()
            print(f"   Найдено записей активации в БД: {len(records)}")
            for record in records:
                print(f"     {record}")
            
            return False
        else:
            print("   ✅ Kill switch НЕ активирован (сброс работает корректно)")
        
        # 6. Test invalid confirmation
        print("6. Тест неверного кода подтверждения...")
        kill_switch.activate("Test activation 2")
        result = kill_switch.reset("WRONG")
        assert result is False, "Сброс с неверным кодом должен провалиться"
        is_still_active = kill_switch.check_status()
        assert is_still_active, "Kill switch должен остаться активным при неверном коде"
        print("   ✅ Неверный код отклонен")
        
        # 7. Reset with correct code again
        print("7. Сброс с правильным кодом...")
        result = kill_switch.reset("RESET")
        assert result is True
        is_active_final = kill_switch.check_status()
        assert not is_active_final, "Kill switch должен быть сброшен"
        print("   ✅ Kill switch снова сброшен")
        
        print("\n✅ ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        print("\nИсправление работает корректно:")
        print("  - Метод reset() удаляет записи из таблицы errors")
        print("  - После сброса killswitch больше не активируется автоматически")
        print("  - Неверные коды подтверждения отклоняются")
        
        return True
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    success = test_killswitch_reset()
    sys.exit(0 if success else 1)
