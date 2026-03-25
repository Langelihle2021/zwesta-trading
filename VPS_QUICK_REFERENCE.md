# VPS Management - Quick Reference

## Your VPS Details (From Screenshot)
```
IP Address:     38.247.146.198
RDP Port:       3389
Backend Port:   5000
MT5 Status:     ✅ ONLINE
Account:        104254514
Status:         ✅ Connected
```

## API Endpoints Quick Reference

### 1️⃣ Register VPS
```bash
POST /api/vps/config
Headers: X-Session-Token: your_token
Body: {
  "vps_name": "Prod VPS",
  "vps_ip": "38.247.146.198",
  "username": "Administrator", 
  "password": "xxx",
  "rdp_port": 3389,
  "api_port": 5000
}
Response: {"vps_id": "vps_xyz123"}
```

### 2️⃣ List My VPS Instances
```bash
GET /api/vps/list
Headers: X-Session-Token: your_token
Response: {"vps_configs": [...]}
```

### 3️⃣ Test VPS Connection
```bash
POST /api/vps/<vps_id>/test-connection
Headers: X-Session-Token: your_token
Response: {"status": "connected", "ping_reachable": true}
```

### 4️⃣ Get VPS Health Status
```bash
GET /api/vps/<vps_id>/status
Headers: X-Session-Token: your_token
Response: {
  "mt5_status": "online",
  "backend_running": true,
  "cpu_usage": 35.5,
  "memory_usage": 62.3,
  "active_bots": 3
}
```

### 5️⃣ Get RDP Connection
```bash
POST /api/vps/<vps_id>/remote-access
Headers: X-Session-Token: your_token
Response: {
  "connection_string": "mstsc /v:38.247.146.198:3389",
  "username": "Administrator"
}
```

### 6️⃣ Delete VPS Config
```bash
DELETE /api/vps/<vps_id>/delete
Headers: X-Session-Token: your_token
Response: {"success": true}
```

### 7️⃣ VPS Sends Heartbeat (No Auth Required)
```bash
POST /api/vps/<vps_id>/heartbeat
Headers: Content-Type: application/json
Body: {
  "mt5_status": "online",
  "backend_running": true,
  "cpu_usage": 35.5,
  "memory_usage": 62.3,
  "uptime_hours": 24,
  "active_bots": 3,
  "total_value_locked": 50000
}
Response: {"success": true}
```

## Connection Status Indicators

| Status | Meaning |
|--------|---------|
| ✅ connected | VPS reachable, backend running |
| ⚠️ online | MT5 running but backend may be paused |
| ❌ disconnected | VPS unreachable or offline |
| 🔄 updating | VPS recently reported status |

## Database Tables

### vps_config
- Stores VPS credentials
- Links to users via user_id
- Tracks last connection time

### vps_monitoring
- Stores periodic health reports
- CPU, memory, uptime metrics
- Active bot count and TVL

## Testing Your VPS

```bash
# 1. Verify backend is running
curl http://localhost:9000/api/health

# 2. Test VPS heartbeat
curl -X POST http://localhost:9000/api/vps/test/heartbeat \
  -H "Content-Type: application/json" \
  -d '{"mt5_status":"online","backend_running":true,"cpu_usage":35}'

# 3. List registered VPS (requires session)
curl -H "X-Session-Token: YOUR_TOKEN" \
  http://localhost:9000/api/vps/list
```

## Implementing Heartbeat on Your VPS

Add this to your VPS backend (runs every 5 minutes):

```python
import requests
import threading

def send_heartbeat():
    while True:
        try:
            requests.post(
                'http://main_backend:9000/api/vps/vps_prod_001/heartbeat',
                json={
                    "mt5_status": "online",
                    "backend_running": True,
                    "cpu_usage": get_cpu(),
                    "memory_usage": get_memory(),
                    "uptime_hours": get_uptime(),
                    "active_bots": len(active_bots),
                    "total_value_locked": calculate_tvl()
                },
                timeout=5
            )
        except:
            pass
        time.sleep(300)  # Every 5 minutes

# Start in background
threading.Thread(target=send_heartbeat, daemon=True).start()
```

## Documentation Files

- 📖 `VPS_MANAGEMENT_API.md` - Complete API docs
- 📋 `VPS_IMPLEMENTATION_COMPLETE.md` - Implementation summary
- 🧪 `test_vps_endpoints.py` - Test endpoint script
- ✅ `verify_vps_routes.py` - Verify routes are loaded

## Status

```
✅ All 7 Endpoints Registered
✅ Database Tables Created
✅ Security Implemented
✅ Documentation Complete
✅ Testing Complete
✅ Production Ready
```

**Ready to go! 🚀**
