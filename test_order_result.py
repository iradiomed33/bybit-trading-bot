"""
Тесты для OrderResult - унифицированной структуры результатов API.
"""

import sys
import os

# Добавляем путь к модулю
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Импортируем напрямую, минуя __init__.py
from execution.order_result import OrderResult


class TestOrderResult:
    """Тесты для класса OrderResult"""
    
    def test_from_api_response_success(self):
        """Тест парсинга успешного ответа API"""
        response = {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "orderId": "12345",
                "orderLinkId": "link_123"
            }
        }
        
        result = OrderResult.from_api_response(response)
        
        assert result.success is True
        assert result.order_id == "12345"
        assert result.error is None
        assert result.raw == response
    
    def test_from_api_response_error(self):
        """Тест парсинга ответа с ошибкой"""
        response = {
            "retCode": 10001,
            "retMsg": "Invalid parameter",
            "result": {}
        }
        
        result = OrderResult.from_api_response(response)
        
        assert result.success is False
        assert result.order_id is None
        assert result.error == "Invalid parameter"
        assert result.raw == response
    
    def test_from_api_response_no_order_id(self):
        """Тест парсинга успешного ответа без orderId (например, cancel)"""
        response = {
            "retCode": 0,
            "retMsg": "OK",
            "result": {}
        }
        
        result = OrderResult.from_api_response(response)
        
        assert result.success is True
        assert result.order_id is None
        assert result.error is None
    
    def test_success_result(self):
        """Тест создания успешного результата"""
        result = OrderResult.success_result(order_id="12345")
        
        assert result.success is True
        assert result.order_id == "12345"
        assert result.error is None
        assert result.raw == {}
    
    def test_success_result_with_raw(self):
        """Тест создания успешного результата с raw данными"""
        raw_data = {"some": "data"}
        result = OrderResult.success_result(order_id="12345", raw=raw_data)
        
        assert result.success is True
        assert result.order_id == "12345"
        assert result.raw == raw_data
    
    def test_error_result(self):
        """Тест создания результата с ошибкой"""
        result = OrderResult.error_result("Connection timeout")
        
        assert result.success is False
        assert result.order_id is None
        assert result.error == "Connection timeout"
        assert result.raw == {}
    
    def test_error_result_with_raw(self):
        """Тест создания результата с ошибкой и raw данными"""
        raw_data = {"retCode": 500}
        result = OrderResult.error_result("Server error", raw=raw_data)
        
        assert result.success is False
        assert result.error == "Server error"
        assert result.raw == raw_data
    
    def test_to_dict_success(self):
        """Тест конвертации в словарь (успешный результат)"""
        result = OrderResult.success_result(order_id="12345")
        d = result.to_dict()
        
        assert d == {
            "success": True,
            "order_id": "12345"
        }
    
    def test_to_dict_error(self):
        """Тест конвертации в словарь (с ошибкой)"""
        result = OrderResult.error_result("Some error")
        d = result.to_dict()
        
        assert d == {
            "success": False,
            "error": "Some error"
        }
    
    def test_to_dict_with_all_fields(self):
        """Тест конвертации в словарь со всеми полями"""
        result = OrderResult(
            success=True,
            order_id="12345",
            error="ignored",  # error игнорируется при success=True
            raw={}
        )
        d = result.to_dict()
        
        # error должен присутствовать в dict даже если success=True
        assert d["success"] is True
        assert d["order_id"] == "12345"
        assert d["error"] == "ignored"
    
    def test_bool_conversion_success(self):
        """Тест использования в условиях (успешный результат)"""
        result = OrderResult.success_result()
        
        assert bool(result) is True
        assert result  # Можно использовать напрямую в if
    
    def test_bool_conversion_error(self):
        """Тест использования в условиях (ошибка)"""
        result = OrderResult.error_result("Error")
        
        assert bool(result) is False
        assert not result  # Можно использовать напрямую в if
    
    def test_backward_compatibility(self):
        """Тест обратной совместимости с dict форматом"""
        # Старый код может ожидать dict, to_dict() обеспечивает совместимость
        result = OrderResult.success_result(order_id="12345")
        d = result.to_dict()
        
        # Эмуляция старого кода
        assert d.get("success") is True
        assert d.get("order_id") == "12345"
        assert d.get("error") is None
    
    def test_from_api_response_missing_retcode(self):
        """Тест обработки ответа без retCode (некорректный ответ)"""
        response = {
            "result": {"orderId": "12345"}
        }
        
        result = OrderResult.from_api_response(response)
        
        # Без retCode считаем ошибкой
        assert result.success is False
        assert result.error == "Unknown error"


if __name__ == "__main__":
    # Запуск тестов напрямую
    import sys
    
    print("Running OrderResult tests...")
    print("=" * 70)
    
    test = TestOrderResult()
    tests = [
        ("from_api_response_success", test.test_from_api_response_success),
        ("from_api_response_error", test.test_from_api_response_error),
        ("from_api_response_no_order_id", test.test_from_api_response_no_order_id),
        ("success_result", test.test_success_result),
        ("success_result_with_raw", test.test_success_result_with_raw),
        ("error_result", test.test_error_result),
        ("error_result_with_raw", test.test_error_result_with_raw),
        ("to_dict_success", test.test_to_dict_success),
        ("to_dict_error", test.test_to_dict_error),
        ("to_dict_with_all_fields", test.test_to_dict_with_all_fields),
        ("bool_conversion_success", test.test_bool_conversion_success),
        ("bool_conversion_error", test.test_bool_conversion_error),
        ("backward_compatibility", test.test_backward_compatibility),
        ("from_api_response_missing_retcode", test.test_from_api_response_missing_retcode),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            print(f"✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {name}: Unexpected error: {e}")
            failed += 1
    
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    
    sys.exit(0 if failed == 0 else 1)
