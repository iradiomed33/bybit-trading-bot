#!/usr/bin/env python
"""Тест API эндпоинта для загрузки логов сигналов"""
import requests
import json

try:
    print("🔍 Testing /api/signals/logs endpoint...")
    response = requests.get("http://localhost:8000/api/signals/logs?limit=5", timeout=5)
    
    print(f"📡 Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Response OK")
        print(f"📊 File: {data.get('file', 'N/A')}")
        print(f"📊 Count: {data.get('count', 0)}")
        print(f"📊 Logs: {len(data.get('data', []))}")
        
        if data.get('data'):
            print("\n🔍 First log entry:")
            first_log = data['data'][0]
            print(f"  Timestamp: {first_log.get('timestamp', 'N/A')}")
            print(f"  Level: {first_log.get('level', 'N/A')}")
            print(f"  Message: {first_log.get('message', 'N/A')[:100]}...")
        else:
            print("⚠️  No log entries in response")
            print(f"   Message: {data.get('message', 'N/A')}")
    else:
        print(f"❌ Error: {response.text[:200]}")
        
except requests.exceptions.ConnectionError:
    print("❌ Connection failed - is API server running?")
except Exception as e:
    print(f"❌ Error: {e}")
