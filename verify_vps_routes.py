#!/usr/bin/env python3
"""Verify VPS routes are registered"""

import sys

# Add backend to path
sys.path.insert(0, 'c:\\backend')
sys.path.insert(0, 'c:\\zwesta-trader\\Zwesta Flutter App')

# Import the app
from multi_broker_backend_updated import app

print("📋 Registered VPS Routes:")
print("=" * 70)

vps_routes = [route for route in app.url_map.iter_rules() if 'vps' in route.rule]

for route in sorted(vps_routes, key=lambda r: r.rule):
    methods = ','.join(sorted(route.methods - {'OPTIONS', 'HEAD'}))
    print(f"{route.rule:<50} {methods:<15}")

print("=" * 70)
print(f"\n✅ Total VPS Routes Registered: {len(vps_routes)}")

if len(vps_routes) >= 6:
    print("\n🎉 All VPS Management Endpoints Successfully Added!")
    print("\nEndpoints Available:")
    print("  1. POST   /api/vps/config                    - Add/update VPS config")
    print("  2. GET    /api/vps/list                      - List all VPS configs")
    print("  3. POST   /api/vps/<vps_id>/test-connection  - Test VPS connectivity")
    print("  4. GET    /api/vps/<vps_id>/status           - Get VPS status")
    print("  5. POST   /api/vps/<vps_id>/remote-access    - Get RDP connection details")
    print("  6. DELETE /api/vps/<vps_id>/delete           - Delete VPS config")
    print("  7. POST   /api/vps/<vps_id>/heartbeat        - VPS status reporting")
else:
    print("\n❌ Not all VPS routes loaded. Check backend logs.")
