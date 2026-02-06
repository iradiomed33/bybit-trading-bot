"""
Унифицированная структура результатов API для ордеров.

Обеспечивает единый интерфейс для всех операций с ордерами,
независимо от формата ответа Bybit API.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class OrderResult:
    """
    Унифицированная структура результата операции с ордером.
    
    Attributes:
        success: Успешна ли операция
        order_id: ID созданного/обновлённого ордера (если применимо)
        error: Сообщение об ошибке (если есть)
        raw: Сырой ответ API для дополнительного анализа
    """
    success: bool
    order_id: Optional[str] = None
    error: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_api_response(cls, response: Dict[str, Any]) -> "OrderResult":
        """
        Создать OrderResult из сырого ответа Bybit API.
        
        Args:
            response: Ответ API от Bybit (формат v5)
            
        Returns:
            OrderResult с разобранными полями
            
        Examples:
            >>> response = {"retCode": 0, "result": {"orderId": "123"}}
            >>> result = OrderResult.from_api_response(response)
            >>> result.success
            True
            >>> result.order_id
            "123"
        """
        ret_code = response.get("retCode", -1)
        success = (ret_code == 0)
        
        # Извлекаем order_id из result если есть
        result_data = response.get("result", {})
        order_id = result_data.get("orderId")
        
        # Извлекаем сообщение об ошибке
        error = None if success else response.get("retMsg", "Unknown error")
        
        return cls(
            success=success,
            order_id=order_id,
            error=error,
            raw=response
        )
    
    @classmethod
    def success_result(cls, order_id: Optional[str] = None, raw: Optional[Dict[str, Any]] = None) -> "OrderResult":
        """
        Создать успешный результат.
        
        Args:
            order_id: ID ордера
            raw: Сырой ответ API (опционально)
            
        Returns:
            OrderResult со success=True
        """
        return cls(
            success=True,
            order_id=order_id,
            raw=raw or {}
        )
    
    @classmethod
    def error_result(cls, error: str, raw: Optional[Dict[str, Any]] = None) -> "OrderResult":
        """
        Создать результат с ошибкой.
        
        Args:
            error: Сообщение об ошибке
            raw: Сырой ответ API (опционально)
            
        Returns:
            OrderResult со success=False
        """
        return cls(
            success=False,
            error=error,
            raw=raw or {}
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Конвертировать в словарь (для обратной совместимости).
        
        Returns:
            Словарь с полями success, order_id, error
        """
        result = {"success": self.success}
        if self.order_id is not None:
            result["order_id"] = self.order_id
        if self.error is not None:
            result["error"] = self.error
        return result
    
    def __bool__(self) -> bool:
        """Позволяет использовать в условиях: if result: ..."""
        return self.success
