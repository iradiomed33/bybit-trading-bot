"""
Тест синхронизации настроек из UI с ботом.

Проверяет что изменения конфигурации из UI корректно применяются к боту.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from config.settings import ConfigManager, get_config


class TestUIConfigSync:
    """Тесты синхронизации конфигурации из UI"""
    
    def test_config_set_and_save_updates_memory(self, tmp_path):
        """Тест что set() и save() обновляют конфиг в памяти"""
        config_file = tmp_path / "test_config.json"
        
        # Создаем конфиг
        cfg = ConfigManager(str(config_file))
        
        # Устанавливаем значение
        cfg.set("trading.mode", "paper")
        assert cfg.get("trading.mode") == "paper"
        
        # Сохраняем
        assert cfg.save() is True
        
        # Проверяем что значение все еще в памяти
        assert cfg.get("trading.mode") == "paper"
        
    def test_config_reload_after_save(self, tmp_path):
        """Тест что reload() после save() работает корректно"""
        config_file = tmp_path / "test_config.json"
        
        # Создаем конфиг и сохраняем
        cfg = ConfigManager(str(config_file))
        cfg.set("trading.mode", "live")
        cfg.save()
        
        # Меняем значение в памяти (не сохраняя)
        cfg.set("trading.mode", "paper")
        assert cfg.get("trading.mode") == "paper"
        
        # Reload должен вернуть сохраненное значение
        cfg.reload()
        assert cfg.get("trading.mode") == "live"
    
    def test_global_config_instance_persistence(self):
        """Тест что глобальный экземпляр конфига сохраняется"""
        # Импортируем get_config который возвращает глобальный экземпляр
        from config import get_config
        
        # Получаем экземпляр дважды
        cfg1 = get_config()
        cfg2 = get_config()
        
        # Должны быть одним объектом
        assert cfg1 is cfg2
        
        # Изменения в cfg1 должны быть видны в cfg2
        cfg1.set("test.value", 12345)
        assert cfg2.get("test.value") == 12345
    
    def test_bot_config_parameters_read_at_init(self):
        """Тест что параметры бота читаются при инициализации"""
        # Этот тест документирует текущее поведение:
        # Большинство параметров читаются в __init__ и не обновляются динамически
        
        from config import get_config
        
        cfg = get_config()
        
        # Устанавливаем значение
        cfg.set("risk_management.max_leverage", 5)
        
        # При создании бота он прочитает это значение
        # НО если бот уже запущен, он не увидит изменения
        # без перезапуска
        
        assert cfg.get("risk_management.max_leverage") == 5
    
    def test_config_changes_requiring_restart(self):
        """Тест определения параметров, требующих перезапуска"""
        
        # Параметры, которые требуют перезапуска бота
        restart_required_prefixes = [
            "risk_management.",
            "risk_monitor.",
            "stop_loss_tp.",
            "paper_trading.",
            "execution.",
            "meta_layer.",
            "no_trade_zone.",
            "kill_switch.",
        ]
        
        # Тестируем разные ключи
        test_cases = [
            ("risk_management.max_leverage", True),
            ("risk_monitor.max_daily_loss_percent", True),
            ("stop_loss_tp.sl_atr_multiplier", True),
            ("trading.symbol", False),  # Этот не требует
            ("logging.level", False),   # Этот тоже нет
            ("meta_layer.use_mtf", True),
        ]
        
        for key, should_require_restart in test_cases:
            requires_restart = any(
                key.startswith(prefix) for prefix in restart_required_prefixes
            )
            assert requires_restart == should_require_restart, \
                f"Key '{key}' restart requirement mismatch"
    
    @pytest.mark.asyncio
    async def test_update_config_with_reload(self):
        """Тест что update_config вызывает reload после save"""
        
        # Мокаем необходимые компоненты
        with patch('api.app.get_config') as mock_get_config, \
             patch('api.app.broadcast_message', new_callable=AsyncMock) as mock_broadcast, \
             patch('api.app.bot_status', {"is_running": False}):
            
            # Создаем мок конфига
            mock_config = Mock(spec=ConfigManager)
            mock_config.config = {}
            mock_get_config.return_value = mock_config
            
            # Импортируем функцию update_config
            from api.app import update_config, ConfigUpdate
            
            # Создаем тело запроса
            body = ConfigUpdate(value="paper")
            
            # Вызываем update_config
            result = await update_config("trading.mode", body)
            
            # Проверяем что вызваны правильные методы
            mock_config.set.assert_called_once_with("trading.mode", "paper")
            mock_config.save.assert_called_once()
            mock_config.reload.assert_called_once()
            
            # Проверяем результат
            assert result["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_config_update_triggers_bot_restart_if_needed(self):
        """Тест что изменение критичных параметров перезапускает бот"""
        
        with patch('api.app.get_config') as mock_get_config, \
             patch('api.app.broadcast_message', new_callable=AsyncMock), \
             patch('api.app.stop_bot', new_callable=AsyncMock) as mock_stop, \
             patch('api.app.start_bot', new_callable=AsyncMock) as mock_start, \
             patch('api.app.bot_status', {"is_running": True}), \
             patch('asyncio.sleep', new_callable=AsyncMock):
            
            # Создаем мок конфига
            mock_config = Mock(spec=ConfigManager)
            mock_config.config = {}
            mock_get_config.return_value = mock_config
            
            # Импортируем функцию
            from api.app import update_config, ConfigUpdate
            
            # Изменяем критичный параметр
            body = ConfigUpdate(value=10)
            result = await update_config("risk_management.max_leverage", body)
            
            # Проверяем что бот был перезапущен
            mock_stop.assert_called_once()
            mock_start.assert_called_once()
            
            # Проверяем результат
            assert result["status"] == "success"
            assert result["bot_restarted"] is True
            assert result["requires_restart"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
