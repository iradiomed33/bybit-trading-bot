"""Тест API логов с детальной информацией"""
import requests
import json

url = "http://localhost:8000/api/signals/logs?limit=10&level=all"
print("🔍 Testing /api/signals/logs endpoint...")
print(f"📡 URL: {url}\n")

response = requests.get(url)
print(f"📡 Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"✅ Response OK")
    print(f"📊 File: {data.get('file', 'N/A')}")
    print(f"📊 Count: {data.get('count', 0)}")
    print(f"📊 Total logs: {len(data.get('data', []))}\n")
    
    print("📋 Log entries:")
    for i, log in enumerate(data.get('data', [])[:5], 1):
        print(f"\n{i}. Log Entry:")
        print(f"   Timestamp: {log.get('timestamp', 'N/A')}")
        print(f"   Level: {log.get('level', 'N/A')}")
        print(f"   Type: {log.get('type', 'N/A')}")
        print(f"   Message: {log.get('message', 'N/A')[:150]}...")
else:
    print(f"❌ Error: {response.status_code}")
    print(response.text)
