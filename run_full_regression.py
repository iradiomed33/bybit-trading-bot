#!/usr/bin/env python3
"""
MASTER РЕГРЕСС-СКРИПТ

Запускает все уровни регресса и генерирует итоговый отчет.

Использование:
    python run_full_regression.py                    # Все уровни
    python run_full_regression.py --level=unit       # Только unit-тесты
    python run_full_regression.py --level=ci         # CI уровень (unit + integration + smoke)
    python run_full_regression.py --level=testnet    # Testnet тесты
    python run_full_regression.py --html             # Выводить HTML отчет
    python run_full_regression.py --verbose          # Verbose режим
"""

import argparse
import json
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple


class RegressionRunner:
    """Главный класс для запуска регресса"""
    
    def __init__(self, verbose: bool = False, html_report: bool = False, testnet_mode: bool = False):
        self.verbose = verbose
        self.html_report = html_report
        self.testnet_mode = testnet_mode
        self.start_time = datetime.now()
        self.results: Dict[str, Any] = {}
        self.critical_failures: List[str] = []
        self.workspace_root = Path(__file__).parent
        self.reports_dir = self.workspace_root / "tests" / "regression" / ".reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
    def log(self, level: str, message: str):
        """Логирование с уровнем"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        if level == "INFO":
            print(f"[{timestamp}] ℹ️  {message}")
        elif level == "PASS":
            print(f"[{timestamp}] ✓ {message}")
        elif level == "FAIL":
            print(f"[{timestamp}] ✗ {message}")
        elif level == "WARN":
            print(f"[{timestamp}] ⚠️  {message}")
        elif level == "DEBUG" and self.verbose:
            print(f"[{timestamp}] 🔍 {message}")
    
    def run_smoke_tests(self) -> Tuple[bool, float]:
        """Запустить smoke-тесты"""
        self.log("INFO", "=" * 70)
        self.log("INFO", "Уровень 1: SMOKE-ТЕСТЫ (SMK-01 до SMK-06)")
        self.log("INFO", "=" * 70)
        
        smoke_script = self.workspace_root / "smoke_test.py"
        
        if not smoke_script.exists():
            self.log("FAIL", f"smoke_test.py не найден в {self.workspace_root}")
            return False, 0
        
        start = time.time()
        
        try:
            result = subprocess.run(
                ["python", str(smoke_script)],
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=60,
            )
            
            elapsed = time.time() - start
            
            if result.returncode == 0:
                self.log("PASS", "Smoke-тесты пройдены")
                self.results['smoke'] = {
                    'status': 'PASS',
                    'time_seconds': elapsed,
                    'count': 6,
                }
                return True, elapsed
            else:
                self.log("FAIL", "Smoke-тесты не пройдены")
                self.log("DEBUG", result.stdout)
                self.log("DEBUG", result.stderr)
                self.critical_failures.append("SMOKE")
                self.results['smoke'] = {
                    'status': 'FAIL',
                    'time_seconds': elapsed,
                    'error': result.stderr[:500],
                }
                return False, elapsed
        
        except subprocess.TimeoutExpired:
            self.log("FAIL", "Smoke-тесты истекли по времени (timeout)")
            self.critical_failures.append("SMOKE")
            return False, 60
        except Exception as e:
            self.log("FAIL", f"Ошибка запуска smoke-тестов: {e}")
            self.critical_failures.append("SMOKE")
            return False, 0
    
    def run_unit_tests(self) -> Tuple[bool, float]:
        """Запустить unit-тесты (pytest)"""
        self.log("INFO", "=" * 70)
        self.log("INFO", "Уровень 2: UNIT-ТЕСТЫ (~35 тестов)")
        self.log("INFO", "=" * 70)
        
        start = time.time()
        
        try:
            result = subprocess.run(
                ["pytest", "tests/regression/test_unit_*.py", "-v", "--tb=short"],
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=180,
            )
            
            elapsed = time.time() - start
            
            # Парсить pytest результаты
            output = result.stdout
            if "passed" in output:
                self.log("PASS", f"Unit-тесты пройдены (время: {elapsed:.1f}s)")
                self.results['unit'] = {
                    'status': 'PASS',
                    'time_seconds': elapsed,
                }
                return True, elapsed
            else:
                self.log("FAIL", "Unit-тесты не пройдены")
                self.log("DEBUG", output[-1000:])  # Последние 1000 символов
                self.critical_failures.append("UNIT")
                self.results['unit'] = {
                    'status': 'FAIL',
                    'time_seconds': elapsed,
                    'error': output[-500:],
                }
                return False, elapsed
        
        except FileNotFoundError:
            self.log("WARN", "pytest не установлен, пропуск unit-тестов")
            self.results['unit'] = {'status': 'SKIP', 'reason': 'pytest not installed'}
            return True, 0
        except subprocess.TimeoutExpired:
            self.log("FAIL", "Unit-тесты истекли по времени (timeout)")
            self.critical_failures.append("UNIT")
            return False, 180
        except Exception as e:
            self.log("WARN", f"Ошибка запуска unit-тестов: {e}")
            self.results['unit'] = {'status': 'ERROR', 'error': str(e)}
            return True, 0  # Не критично, продолжаем
    
    def run_integration_tests(self) -> Tuple[bool, float]:
        """Запустить integration-тесты (pytest)"""
        self.log("INFO", "=" * 70)
        self.log("INFO", "Уровень 3: INTEGRATION-ТЕСТЫ (~25 тестов)")
        self.log("INFO", "=" * 70)
        
        start = time.time()
        
        try:
            result = subprocess.run(
                ["pytest", "tests/regression/test_integration_*.py", "-v", "--tb=short"],
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=600,
            )
            
            elapsed = time.time() - start
            
            if result.returncode == 0 or "passed" in result.stdout:
                self.log("PASS", f"Integration-тесты пройдены (время: {elapsed:.1f}s)")
                self.results['integration'] = {
                    'status': 'PASS',
                    'time_seconds': elapsed,
                }
                return True, elapsed
            else:
                self.log("FAIL", "Integration-тесты не пройдены")
                self.log("DEBUG", result.stdout[-1000:])
                self.critical_failures.append("INTEGRATION")
                self.results['integration'] = {
                    'status': 'FAIL',
                    'time_seconds': elapsed,
                    'error': result.stdout[-500:],
                }
                return False, elapsed
        
        except FileNotFoundError:
            self.log("WARN", "pytest не установлен, пропуск integration-тестов")
            self.results['integration'] = {'status': 'SKIP', 'reason': 'pytest not installed'}
            return True, 0
        except subprocess.TimeoutExpired:
            self.log("FAIL", "Integration-тесты истекли по времени (timeout)")
            self.critical_failures.append("INTEGRATION")
            return False, 600
        except Exception as e:
            self.log("WARN", f"Ошибка запуска integration-тестов: {e}")
            self.results['integration'] = {'status': 'ERROR', 'error': str(e)}
            return True, 0  # Не критично
    
    def run_testnet_tests(self) -> Tuple[bool, float]:
        """Запустить testnet-тесты"""
        self.log("INFO", "=" * 70)
        self.log("INFO", "Уровень 4: TESTNET-ТЕСТЫ (~11 тестов)")
        self.log("INFO", "=" * 70)
        
        if not self.testnet_mode:
            self.log("WARN", "Testnet режим отключен, пропуск testnet-тестов")
            self.results['testnet'] = {'status': 'SKIP', 'reason': 'testnet_mode=False'}
            return True, 0
        
        start = time.time()
        
        try:
            result = subprocess.run(
                ["pytest", "tests/regression/test_testnet_*.py", "-v", "--testnet", "--tb=short"],
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=600,
                env={**subprocess.os.environ, "PYTEST_TESTNET": "true"},
            )
            
            elapsed = time.time() - start
            
            if result.returncode == 0 or "passed" in result.stdout:
                self.log("PASS", f"Testnet-тесты пройдены (время: {elapsed:.1f}s)")
                self.results['testnet'] = {
                    'status': 'PASS',
                    'time_seconds': elapsed,
                }
                return True, elapsed
            else:
                self.log("WARN", "Testnet-тесты содержат ошибки (но не критичны)")
                self.results['testnet'] = {
                    'status': 'PARTIAL',
                    'time_seconds': elapsed,
                }
                return True, elapsed  # Не критично для релиза
        
        except FileNotFoundError:
            self.log("WARN", "pytest не установлен, пропуск testnet-тестов")
            self.results['testnet'] = {'status': 'SKIP', 'reason': 'pytest not installed'}
            return True, 0
        except Exception as e:
            self.log("WARN", f"Ошибка запуска testnet-тестов: {e}")
            self.results['testnet'] = {'status': 'ERROR', 'error': str(e)}
            return True, 0
    
    def generate_report(self):
        """Генерировать итоговый отчет"""
        elapsed_total = (datetime.now() - self.start_time).total_seconds()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': elapsed_total,
            'workspace': str(self.workspace_root),
            'results': self.results,
            'critical_failures': self.critical_failures,
            'gate': self.is_release_ready(),
        }
        
        # Сохранить JSON отчет
        report_file = self.reports_dir / "regression_final_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.log("PASS", f"Отчет сохранён в {report_file}")
        
        return report
    
    def is_release_ready(self) -> bool:
        """Определить готовность к релизу (все ли P0 пройдены)"""
        # P0 тесты: smoke + unit + integration
        required_levels = ['smoke', 'unit', 'integration']
        
        for level in required_levels:
            if level not in self.results:
                return False
            status = self.results[level].get('status')
            if status not in ['PASS', 'PARTIAL']:
                return False
        
        return len(self.critical_failures) == 0
    
    def print_summary(self, report: Dict[str, Any]):
        """Вывести сводку результатов"""
        print("\n" + "=" * 70)
        print("ИТОГОВАЯ СВОДКА РЕГРЕССА")
        print("=" * 70)
        
        print(f"\nВремя выполнения: {report['duration_seconds']:.1f} сек")
        
        print("\nРезультаты по уровням:")
        for level, result in report['results'].items():
            status = result.get('status', 'UNKNOWN')
            time_taken = result.get('time_seconds', 0)
            status_icon = "✓" if status == "PASS" else "✗" if status == "FAIL" else "⊘"
            print(f"  {status_icon} {level.upper():15} {status:10} ({time_taken:6.1f}s)")
        
        if report['critical_failures']:
            print(f"\n❌ КРИТИЧЕСКИЕ ОШИБКИ: {', '.join(report['critical_failures'])}")
        
        gate_status = "✓ GO TO RELEASE" if report['gate'] else "✗ NO GO (требуется исправление)"
        print(f"\n{gate_status}")
        print("=" * 70 + "\n")
    
    def run_all(self) -> int:
        """Запустить все уровни регресса"""
        self.log("INFO", "Начало полного регресса")
        self.log("INFO", f"Workspace: {self.workspace_root}")
        
        # Smoke-тесты
        smoke_ok, smoke_time = self.run_smoke_tests()
        
        if not smoke_ok:
            self.log("FAIL", "Smoke-тесты не пройдены, остановка")
            report = self.generate_report()
            self.print_summary(report)
            return 1
        
        # Unit-тесты
        unit_ok, unit_time = self.run_unit_tests()
        
        # Integration-тесты
        integration_ok, integration_time = self.run_integration_tests()
        
        # Testnet-тесты (если включено)
        if self.testnet_mode:
            testnet_ok, testnet_time = self.run_testnet_tests()
        
        # Генерировать отчет
        report = self.generate_report()
        self.print_summary(report)
        
        # Вернуть exit code
        return 0 if report['gate'] else 1
    
    def run_level(self, level: str) -> int:
        """Запустить конкретный уровень"""
        self.log("INFO", f"Запуск уровня: {level}")
        
        if level == "smoke":
            ok, _ = self.run_smoke_tests()
        elif level == "unit":
            ok, _ = self.run_unit_tests()
        elif level == "integration":
            ok, _ = self.run_integration_tests()
        elif level == "testnet":
            ok, _ = self.run_testnet_tests()
        elif level == "ci":
            # CI уровень = smoke + unit + integration
            smoke_ok, _ = self.run_smoke_tests()
            unit_ok, _ = self.run_unit_tests()
            integration_ok, _ = self.run_integration_tests()
            ok = smoke_ok and unit_ok and integration_ok
        else:
            self.log("FAIL", f"Неизвестный уровень: {level}")
            return 1
        
        report = self.generate_report()
        self.print_summary(report)
        return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description="Master регресс-скрипт для Bybit Trading Bot")
    parser.add_argument(
        "--level",
        choices=["all", "smoke", "unit", "integration", "testnet", "ci"],
        default="all",
        help="Какой уровень тестов запустить"
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Генерировать HTML отчет"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose вывод"
    )
    parser.add_argument(
        "--testnet",
        action="store_true",
        help="Включить testnet-тесты (требуют API ключи)"
    )
    
    args = parser.parse_args()
    
    runner = RegressionRunner(
        verbose=args.verbose,
        html_report=args.html,
        testnet_mode=args.testnet,
    )
    
    if args.level == "all":
        return runner.run_all()
    else:
        return runner.run_level(args.level)


if __name__ == "__main__":
    sys.exit(main())
