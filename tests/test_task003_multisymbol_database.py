"""
TASK-003 (P0): MultiSymbol Безопасность SQLite

Тесты для проверки что несколько потоков могут безопасно писать в БД
без "database is locked" ошибок.

Реализация варианта C (минимум):
- WAL mode включен для concurrent writes
- busy_timeout = 5 сек для обработки lock'ов  
- Глобальный кэш соединений (одно подключение на файл БД в процессе)
"""

import pytest
import threading
import time
import tempfile
from pathlib import Path
from datetime import datetime

from storage.database import Database
from logger import setup_logger

logger = setup_logger(__name__)


class TestWALAndBusyTimeout:
    """Проверь что WAL mode и busy_timeout установлены"""
    
    def test_wal_mode_enabled(self):
        """Проверить что WAL mode включен"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            db = Database(db_path)
            
            cursor = db.conn.cursor()
            cursor.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            
            assert mode.upper() == "WAL", f"Expected WAL mode, got {mode}"
            logger.info(f"✓ WAL mode verified: {mode}")
            Database.close_all_cached()

    def test_busy_timeout_set(self):
        """Проверить что busy_timeout установлен на 5 сек"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            db = Database(db_path)
            
            cursor = db.conn.cursor()
            cursor.execute("PRAGMA busy_timeout")
            timeout_ms = cursor.fetchone()[0]
            
            assert timeout_ms == 5000, f"Expected 5000ms, got {timeout_ms}ms"
            logger.info(f"✓ busy_timeout verified: {timeout_ms}ms")
            Database.close_all_cached()

    def test_synchronous_normal(self):
        """Проверить что synchronous mode установлен на NORMAL"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            db = Database(db_path)
            
            cursor = db.conn.cursor()
            cursor.execute("PRAGMA synchronous")
            sync_mode = cursor.fetchone()[0]
            
            assert sync_mode == 1, f"Expected synchronous=NORMAL (1), got {sync_mode}"
            logger.info(f"✓ synchronous mode verified: {sync_mode} (NORMAL)")
            Database.close_all_cached()


class TestCachedConnections:
    """Тесты кэширования соединений"""
    
    def test_same_file_reuses_connection(self):
        """Проверить что два Database с одним файлом используют одно соединение"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "shared.db")
            
            db1 = Database(db_path)
            db2 = Database(db_path)
            
            assert db1.conn is db2.conn
            logger.info(f"✓ Same file reuses connection")
            Database.close_all_cached()

    def test_different_files_different_connections(self):
        """Проверить что разные файлы используют разные соединения"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db1_path = str(Path(tmpdir) / "db1.db")
            db2_path = str(Path(tmpdir) / "db2.db")
            
            db1 = Database(db1_path)
            db2 = Database(db2_path)
            
            assert db1.conn is not db2.conn
            logger.info(f"✓ Different files use different connections")
            Database.close_all_cached()

    def test_cached_connection_count(self):
        """Проверить счетчик кэшированных соединений"""
        Database.close_all_cached()
        assert Database.get_cached_connection_count() == 0
        
        with tempfile.TemporaryDirectory() as tmpdir:
            db1_path = str(Path(tmpdir) / "db1.db")
            db2_path = str(Path(tmpdir) / "db2.db")
            
            Database(db1_path)
            assert Database.get_cached_connection_count() == 1
            
            Database(db2_path)
            assert Database.get_cached_connection_count() == 2
            
            Database(db1_path)
            assert Database.get_cached_connection_count() == 2
            
            logger.info("✓ Cached connection counting works")
            Database.close_all_cached()


class TestMultiSymbolWrites:
    """
    Главные тесты: MultiSymbol сценарии без "database is locked"
    """
    
    def test_sequential_writes_multiple_threads(self):
        """
        Тест TASK-003: несколько потоков пишут в одну БД.
        
        Благодаря WAL + busy_timeout, отсутствуют "database is locked" ошибки.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            db = Database(db_path)
            
            # Инициализируем
            db.save_signal("init", "BTCUSDT", "long", 100.0, {})
            
            errors = []
            
            def writer(thread_id: int):
                try:
                    local_db = Database(db_path)
                    for i in range(20):
                        local_db.save_signal(
                            strategy=f"t{thread_id}",
                            symbol=f"S{thread_id}",
                            signal_type="long",
                            price=100.0 + i,
                            metadata={"t": thread_id}
                        )
                except Exception as e:
                    errors.append(f"T{thread_id}: {str(e)[:80]}")
            
            threads = [
                threading.Thread(target=writer, args=(i,), daemon=False)
                for i in range(3)
            ]
            
            for t in threads:
                t.start()
            
            for t in threads:
                t.join(timeout=30)
            
            assert len(errors) == 0, f"Got errors: {errors}"
            
            cursor = db.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM signals")
            count = cursor.fetchone()[0]
            assert count == 61  # 1 init + 3*20
            
            logger.info(f"✓ Multiple threads wrote {count} signals without errors")
            Database.close_all_cached()

    def test_multisymbol_scenario(self):
        """
        Главный TASK-003 сценарий: несколько TradingBot инстансов (разные символы)
        пишут в одну БД параллельно без "database is locked" ошибок.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "multi.db")
            
            symbols = ["BTCUSDT", "ETHUSDT", "XRPUSDT"]
            errors = []
            success = [0]
            
            def symbol_worker(symbol: str):
                try:
                    db = Database(db_path)
                    for i in range(15):
                        db.save_signal(
                            strategy="strgy",
                            symbol=symbol,
                            signal_type="long",
                            price=100.0 + i,
                            metadata={}
                        )
                        success[0] += 1
                except Exception as e:
                    errors.append(f"{symbol}: {str(e)[:80]}")
            
            threads = [
                threading.Thread(target=symbol_worker, args=(sym,), daemon=False)
                for sym in symbols
            ]
            
            for t in threads:
                t.start()
            
            for t in threads:
                t.join(timeout=30)
            
            assert len(errors) == 0, f"Errors: {errors}"
            assert success[0] == 45  # 3*15
            
            logger.info(f"✓ MultiSymbol ({len(symbols)} symbols) wrote {success[0]} signals successfully")
            Database.close_all_cached()

    def test_close_behavior(self):
        """Проверить поведение close()"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            
            db1 = Database(db_path)
            db1.close()
            
            # db2 должна продолжить работать (соединение кэшировано)
            db2 = Database(db_path)
            db2.save_signal("test", "BTCUSDT", "long", 100.0, {})
            
            cursor = db2.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM signals")
            count = cursor.fetchone()[0]
            assert count == 1
            
            logger.info("✓ Cached connection persists after close()")
            Database.close_all_cached()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
