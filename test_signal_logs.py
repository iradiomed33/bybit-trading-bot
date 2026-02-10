#!/usr/bin/env python
"""
Проверить загрузку логов сигналов через API
"""
import asyncio
import json
from pathlib import Path
from datetime import datetime

# Проверить файлы логов
logs_dir = Path("logs")
print("📁 Checking logs directory...")
signal_logs = sorted(
    logs_dir.glob("signals_*.log"),
    key=lambda p: p.stat().st_mtime,
    reverse=True
)

print(f"Found {len(signal_logs)} signal log files:")
for log_file in signal_logs[:5]:
    size = log_file.stat().st_size
    lines = len(open(log_file, "r", encoding="utf-8").readlines())
    print(f"  - {log_file.name}: {lines} lines, {size} bytes")

# Если нет логов сегодня, показать вчерашние
if signal_logs:
    latest = signal_logs[0]
    print(f"\n📄 Latest log file: {latest.name}")
    
    # Показать последние 5 логов
    with open(latest, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    
    print(f"📊 Total log entries: {len(all_lines)}")
    
    if all_lines:
        print("\n🔍 Last 5 log entries:")
        for line in all_lines[-5:]:
            print(f"  {line.strip()}")
    else:
        print("❌ Log file is empty!")
else:
    print("⚠️  No signal log files found!")

print("\n✓ Test complete")
