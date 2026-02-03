"""
Command Line Interface для управления ботом.
Пока только health check команда.
"""
import sys
from logger import setup_logger
from config import Config

logger = setup_logger()

def health_check():
    """Проверка конфигурации и работоспособности"""
    logger.info("=== Health Check Started ===")
    
    try:
        # Валидация конфига
        Config.validate()
        logger.info(f"✓ Configuration valid")
        logger.info(f"  - Environment: {Config.ENVIRONMENT}")
        logger.info(f"  - Mode: {Config.MODE}")
        logger.info(f"  - REST URL: {Config.get_rest_url()}")
        logger.info(f"  - WS URL: {Config.get_ws_url()}")
        logger.info(f"  - Log level: {Config.LOG_LEVEL}")
        
        # Проверка модулей
        modules = ['exchange', 'data', 'strategy', 'risk', 'execution', 'portfolio', 'storage']
        for module in modules:
            try:
                __import__(module)
                logger.info(f"✓ Module '{module}' loaded")
            except ImportError as e:
                logger.warning(f"✗ Module '{module}' not fully implemented: {e}")
        
        logger.info("=== Health Check Passed ===")
        return 0
        
    except Exception as e:
        logger.error(f"✗ Health check failed: {e}")
        logger.info("=== Health Check Failed ===")
        return 1

def main():
    """Точка входа CLI"""
    if len(sys.argv) < 2:
        print("Usage: python cli.py <command>")
        print("Commands:")
        print("  health   - Check configuration and system health")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "health":
        sys.exit(health_check())
    else:
        logger.error(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
