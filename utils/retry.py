"""
Retry logic with exponential backoff.

Используется для обработки rate limits и временных ошибок API.
"""

import time
from typing import Callable, TypeVar, Any, Optional, Dict
from logger import setup_logger

logger = setup_logger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    func: Callable[..., T],
    func_args: tuple = (),
    func_kwargs: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
    max_delay: float = 10.0,
) -> Optional[T]:
    """
    Выполнить функцию с retry logic и exponential backoff.

    Args:
        func: Функция для вызова
        func_args: Позиционные аргументы для func
        func_kwargs: Именованные аргументы для func
        max_retries: Максимальное количество попыток
        initial_delay: Начальная задержка в секундах
        backoff_factor: Множитель для увеличения задержки
        max_delay: Максимальная задержка между попытками

    Returns:
        Результат функции или None если все попытки исчерпаны
    """
    if func_kwargs is None:
        func_kwargs = {}
        
    delay = initial_delay
    last_error = None

    for attempt in range(max_retries):
        try:
            result = func(*func_args, **func_kwargs)

            # Проверяем retCode для Bybit API
            if isinstance(result, dict) and "retCode" in result:
                if result["retCode"] == 0:
                    # Успешный ответ
                    if attempt > 0:
                        logger.info(f"✅ Успешно после {attempt} повторной попытки")
                    return result
                elif result["retCode"] == 2:
                    # Rate limit error - нужно retry
                    last_error = f"Rate limit (retCode=2)"
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"⏳ Rate limit. Retry {attempt + 1}/{max_retries} через {delay:.1f}s"
                        )
                        time.sleep(delay)
                        delay = min(delay * backoff_factor, max_delay)
                        continue
                    else:
                        logger.error(f"❌ Rate limit persist after {max_retries} retries")
                        return None
                else:
                    # Другая ошибка API - не нужно retry
                    logger.error(f"API error: retCode={result['retCode']}")
                    return result
            else:
                # Успешный результат (не API ответ)
                if attempt > 0:
                    logger.info(f"✅ Успешно после {attempt} повторной попытки")
                return result

        except Exception as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                logger.warning(
                    f"⏳ Error: {e}. Retry {attempt + 1}/{max_retries} через {delay:.1f}s"
                )
                time.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
            else:
                logger.error(f"❌ Failed after {max_retries} retries: {e}")

    logger.error(f"All retries exhausted. Last error: {last_error}")
    return None


def retry_api_call(
    func: Callable[..., Dict[str, Any]],
    *func_args: Any,
    max_retries: int = 3,
    **func_kwargs: Any,
) -> Optional[Dict[str, Any]]:
    """
    Специализированная функция для retry API вызовов.

    Args:
        func: API функция (должна вернуть dict с retCode)
        *func_args: Позиционные аргументы для func
        max_retries: Максимум попыток
        **func_kwargs: Именованные аргументы для func

    Returns:
        API ответ или None
    """
    return retry_with_backoff(
        func,
        func_args=func_args,
        func_kwargs=func_kwargs,
        max_retries=max_retries,
        initial_delay=0.5,
        backoff_factor=2.0,
        max_delay=10.0,
    )
