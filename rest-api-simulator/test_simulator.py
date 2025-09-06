#!/usr/bin/env python3
"""
Test script for the REST API Simulator.
Tests all endpoints and validates data format.
"""
import requests
import json
import time
from datetime import datetime

def test_endpoint(url, endpoint_name):
    """Test a single endpoint."""
    try:
        print(f"\n🔍 Testing {endpoint_name}: {url}")
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ {endpoint_name} - Status: {response.status_code}")
            
            if 'data' in data and isinstance(data['data'], list):
                print(f"📊 Records: {len(data['data'])}")
                if len(data['data']) > 0:
                    sample = data['data'][0]
                    print(f"📋 Sample record keys: {list(sample.keys())}")
            elif 'total_records' in data:
                print(f"📊 Total records: {data['total_records']}")
            
            return True
        else:
            print(f"❌ {endpoint_name} - Status: {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ {endpoint_name} - Error: {e}")
        return False

def main():
    """Run tests against the REST API simulator."""
    base_url = "http://localhost:8002"
    
    print("🚀 Testing REST API Simulator")
    print("=" * 50)
    
    # Test endpoints
    endpoints = [
        ("/", "Root endpoint"),
        ("/health", "Health check"),
        ("/api/sensors/all", "All sensors (main endpoint)"),
        ("/api/sensors/temperature", "Temperature sensors"),
        ("/api/sensors/air-quality", "Air quality sensors"),
        ("/api/sensors/traffic", "Traffic sensors"), 
        ("/api/sensors/parking", "Parking sensors"),
        ("/api/sensors/energy", "Energy meters")
    ]
    
    passed = 0
    total = len(endpoints)
    
    for endpoint, name in endpoints:
        if test_endpoint(f"{base_url}{endpoint}", name):
            passed += 1
        time.sleep(0.5)  # Small delay between requests
    
    print(f"\n📊 Test Results: {passed}/{total} endpoints passed")
    
    if passed == total:
        print("✅ All tests passed! The REST API Simulator is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the service logs.")

if __name__ == "__main__":
    main()
