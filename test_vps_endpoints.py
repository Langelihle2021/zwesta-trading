#!/usr/bin/env python3
"""Test VPS management endpoints"""

import requests
import json
import sys

BASE_URL = "http://localhost:9000"

def test_vps_heartbeat():
    """Test VPS heartbeat endpoint"""
    print("\n=== Testing VPS Heartbeat Endpoint ===")
    
    data = {
        "mt5_status": "online",
        "backend_running": True,
        "cpu_usage": 35.5,
        "memory_usage": 62.3,
        "uptime_hours": 24,
        "active_bots": 3,
        "total_value_locked": 50000.00
    }
    
    try:
        response = requests.post(
            f'{BASE_URL}/api/vps/vps_prod_001/heartbeat',
            json=data,
            timeout=5
        )
        
        print(f"Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 200:
            print("\n✅ VPS Heartbeat Endpoint Working!")
        else:
            print("\n❌ VPS Heartbeat Endpoint Failed!")
        
        return response.status_code == 200
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_health():
    """Test health endpoint"""
    print("\n=== Testing Health Endpoint ===")
    
    try:
        response = requests.get(f'{BASE_URL}/api/health', timeout=5)
        
        print(f"Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 200:
            print("\n✅ Health Endpoint Working!")
        
        return response.status_code == 200
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    print("🧪 Testing VPS Management Endpoints")
    print("=" * 50)
    
    # Test health first
    health_ok = test_health()
    
    if not health_ok:
        print("\n❌ Backend is not responding. Is it running?")
        sys.exit(1)
    
    # Test VPS heartbeat
    heartbeat_ok = test_vps_heartbeat()
    
    print("\n" + "=" * 50)
    print("Summary:")
    print(f"  Health: {'✅' if health_ok else '❌'}")
    print(f"  VPS Heartbeat: {'✅' if heartbeat_ok else '❌'}")
    
    if health_ok and heartbeat_ok:
        print("\n✅ All VPS endpoints are working!")
    else:
        print("\n❌ Some endpoints need attention")
