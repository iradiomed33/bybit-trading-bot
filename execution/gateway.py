"""
Execution Gateway - абстракция для разделения режимов backtest/paper/live.

Позволяет стратегии не знать где она исполняется.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from execution.order_result import OrderResult


class IExecutionGateway(ABC):
    """
    Абстрактный интерфейс для исполнения торговых операций.
    
    Реализации:
    - BacktestGateway - симуляция для бэктеста
    - PaperGateway - симуляция с реальными ценами
    - BybitLiveGateway - реальная торговля на Bybit
    """
    
    @abstractmethod
    def place_order(
        self,
        category: str,
        symbol: str,
        side: str,
        order_type: str,
        qty: float,
        price: Optional[float] = None,
        time_in_force: str = "GTC",
        order_link_id: Optional[str] = None,
        **kwargs
    ) -> OrderResult:
        """
        Разместить ордер.
        
        Args:
            category: Категория (linear, inverse, spot)
            symbol: Торговый символ
            side: Buy или Sell
            order_type: Market, Limit
            qty: Количество
            price: Цена (для Limit)
            time_in_force: GTC, IOC, FOK
            order_link_id: Клиентский ID для идемпотентности
            
        Returns:
            OrderResult с результатом операции
        """
        pass
    
    @abstractmethod
    def cancel_order(
        self,
        category: str,
        symbol: str,
        order_id: Optional[str] = None,
        order_link_id: Optional[str] = None,
    ) -> OrderResult:
        """
        Отменить ордер.
        
        Args:
            category: Категория
            symbol: Символ
            order_id: ID ордера (или order_link_id)
            order_link_id: Клиентский ID
            
        Returns:
            OrderResult
        """
        pass
    
    @abstractmethod
    def cancel_all_orders(
        self,
        category: str,
        symbol: Optional[str] = None,
    ) -> OrderResult:
        """
        Отменить все ордера.
        
        Args:
            category: Категория
            symbol: Символ (если None, все символы)
            
        Returns:
            OrderResult
        """
        pass
    
    @abstractmethod
    def get_position(self, category: str, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Получить позицию по символу.
        
        Args:
            category: Категория
            symbol: Символ
            
        Returns:
            Dict с данными позиции или None
        """
        pass
    
    @abstractmethod
    def get_positions(self, category: str) -> List[Dict[str, Any]]:
        """
        Получить все позиции.
        
        Args:
            category: Категория
            
        Returns:
            List позиций
        """
        pass
    
    @abstractmethod
    def get_open_orders(
        self,
        category: str,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Получить открытые ордера.
        
        Args:
            category: Категория
            symbol: Символ (если None, все)
            
        Returns:
            List ордеров
        """
        pass
    
    @abstractmethod
    def set_trading_stop(
        self,
        category: str,
        symbol: str,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        sl_trigger_by: str = "LastPrice",
        tp_trigger_by: str = "LastPrice",
        **kwargs
    ) -> OrderResult:
        """
        Установить SL/TP на позицию.
        
        Args:
            category: Категория
            symbol: Символ
            stop_loss: Цена Stop Loss
            take_profit: Цена Take Profit
            sl_trigger_by: Триггер SL
            tp_trigger_by: Триггер TP
            
        Returns:
            OrderResult
        """
        pass
    
    @abstractmethod
    def cancel_trading_stop(
        self,
        category: str,
        symbol: str,
    ) -> OrderResult:
        """
        Отменить SL/TP на позиции.
        
        Args:
            category: Категория
            symbol: Символ
            
        Returns:
            OrderResult
        """
        pass
    
    @abstractmethod
    def get_account_balance(self, account_type: str = "UNIFIED") -> Dict[str, Any]:
        """
        Получить баланс аккаунта.
        
        Args:
            account_type: Тип аккаунта
            
        Returns:
            Dict с балансом
        """
        pass
    
    @abstractmethod
    def get_executions(
        self,
        category: str,
        symbol: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Получить исполнения (fills).
        
        Args:
            category: Категория
            symbol: Символ
            limit: Лимит результатов
            
        Returns:
            List исполнений
        """
        pass
