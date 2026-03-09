# Bot Monitoring & Auto-Withdrawal Deployment Checklist

## ✅ Pre-Deployment Verification

### Code Implementation
- [x] 4 API endpoints implemented in `multi_broker_backend_updated.py`
  - [x] `GET /api/bot/<bot_id>/health`
  - [x] `POST /api/bot/<bot_id>/auto-withdrawal`
  - [x] `GET /api/bot/<bot_id>/auto-withdrawal-status`
  - [x] `POST /api/bot/<bot_id>/disable-auto-withdrawal`
- [x] Database schema included (already exists in DB initialization)
  - [x] `bot_monitoring` table
  - [x] `auto_withdrawal_settings` table
  - [x] `auto_withdrawal_history` table
- [x] Background monitoring thread implemented
  - [x] Threading import added
  - [x] `auto_withdrawal_monitor()` function created
  - [x] Thread started in main block
  - [x] Graceful shutdown handling

### Documentation
- [x] Full API documentation (`BOT_MONITORING_AND_WITHDRAWAL_GUIDE.md`)
- [x] Quick reference guide (`BOT_MONITORING_QUICK_REFERENCE.md`)
- [x] Implementation summary (`BOT_MONITORING_IMPLEMENTATION_SUMMARY.md`)
- [x] Code examples in Python and Dart/Flutter
- [x] Testing guidance and troubleshooting

### Testing
- [x] Test script created (`test_bot_monitoring.py`)
- [x] 9 comprehensive test cases
- [x] Success/failure output
- [x] Error message verification

---

## 🔍 Pre-Deployment Testing Checklist

### Local Testing
- [ ] Start backend server:
  ```bash
  python multi_broker_backend_updated.py
  ```
  - [ ] Server starts successfully
  - [ ] No import errors
  - [ ] No database errors
  - [ ] Monitoring thread starts
  - [ ] Logs show initialization

- [ ] Run test script:
  ```bash
  python test_bot_monitoring.py
  ```
  - [ ] All 9 tests pass
  - [ ] No connection errors
  - [ ] Responses format correct
  - [ ] Error handling works

### Manual Testing
- [ ] Health endpoint returns data:
  ```bash
  curl http://localhost:9000/api/bot/bot_demo_1/health \
    -H "X-API-Key: your_api_key"
  ```
  - [ ] 200 status code
  - [ ] Valid JSON response
  - [ ] All health fields present

- [ ] Set auto-withdrawal:
  ```bash
  curl -X POST http://localhost:9000/api/bot/bot_demo_1/auto-withdrawal \
    -H "X-API-Key: your_api_key" \
    -H "Content-Type: application/json" \
    -d '{"user_id": "user_123", "target_profit": 500}'
  ```
  - [ ] 200 status code
  - [ ] Setting created successfully
  - [ ] Response includes setting_id

- [ ] Verify withdrawal settings:
  ```bash
  curl http://localhost:9000/api/bot/bot_demo_1/auto-withdrawal-status \
    -H "X-API-Key: your_api_key"
  ```
  - [ ] 200 status code
  - [ ] Current settings displayed
  - [ ] History returned (if any)

- [ ] Disable auto-withdrawal:
  ```bash
  curl -X POST http://localhost:9000/api/bot/bot_demo_1/disable-auto-withdrawal \
    -H "X-API-Key: your_api_key"
  ```
  - [ ] 200 status code
  - [ ] Confirmation message returned

---

## 📦 Deployment Steps

### Step 1: Backup Current System
- [ ] Backup `multi_broker_backend.py` (original)
- [ ] Export database (if data to preserve)
- [ ] Document current API key

### Step 2: Deploy New Backend
- [ ] Copy `multi_broker_backend_updated.py` to production
- [ ] Update file ownership/permissions
- [ ] Verify file integrity

### Step 3: Database Verification
- [ ] Database schema auto-creates on startup
- [ ] Run database integrity check
- [ ] Verify 3 new tables created:
  ```sql
  SELECT name FROM sqlite_master WHERE type='table' 
  ORDER BY name;
  ```
  - [ ] `auto_withdrawal_history` exists
  - [ ] `auto_withdrawal_settings` exists
  - [ ] `bot_monitoring` exists

### Step 4: Service Startup
- [ ] Start backend service
- [ ] Monitor startup logs
- [ ] Verify listening on correct port
- [ ] Verify monitoring thread started

### Step 5: Health Check
- [ ] All endpoints responding (test 5 endpoints)
- [ ] Health status working
- [ ] Error handling working
- [ ] Logging working

---

## 🔒 Security Verification

### API Security
- [ ] API Key authentication enabled
  ```bash
  # This should fail (no API key)
  curl http://localhost:9000/api/bot/bot_demo_1/health
  ```
  - [ ] Returns 401/403 error

- [ ] API Key validation working
  ```bash
  # This should work
  curl http://localhost:9000/api/bot/bot_demo_1/health \
    -H "X-API-Key: correct_key"
  ```
  - [ ] Returns 200 with data

### Input Validation
- [ ] Minimum profit target enforced
  ```bash
  curl -X POST http://localhost:9000/api/bot/bot_demo_1/auto-withdrawal \
    -H "X-API-Key: your_api_key" \
    -H "Content-Type: application/json" \
    -d '{"user_id": "user_123", "target_profit": 5}'
  ```
  - [ ] Returns 400 error
  - [ ] Error message: "Minimum profit target is $10"

- [ ] Maximum profit target enforced
  ```bash
  curl -X POST http://localhost:9000/api/bot/bot_demo_1/auto-withdrawal \
    -H "X-API-Key: your_api_key" \
    -H "Content-Type: application/json" \
    -d '{"user_id": "user_123", "target_profit": 100000}'
  ```
  - [ ] Returns 400 error
  - [ ] Error message: "Maximum profit target is $50,000"

- [ ] Database injection protection
  - [ ] Parameterized queries used
  - [ ] No string concatenation in SQL

### Data Protection
- [ ] Database transactions use ACID
- [ ] Withdrawal history recorded
- [ ] Profit reset on withdrawal
- [ ] Fee calculation accurate

---

## 📊 Monitoring & Verification

### Log File Creation
- [ ] `multi_broker_backend.log` created
- [ ] Contains initialization messages
- [ ] Contains monitoring start message
- [ ] No error messages in startup

### Monitoring Thread Status
- [ ] Thread running as daemon
- [ ] Thread checks every 30 seconds
- [ ] Thread handles errors gracefully
- [ ] Thread stops on shutdown

### Performance Monitoring
- [ ] CPU usage normal (<5%)
- [ ] Memory usage stable
- [ ] Database responsive
- [ ] No file descriptor leaks

---

## 🚀 Integration Checklist

### Frontend Integration
- [ ] Update API endpoints in Flutter app
- [ ] Add bot health display
- [ ] Add auto-withdrawal settings UI
- [ ] Add withdrawal history view
- [ ] Add error handling

### User Documentation
- [ ] Update user guide with new features
- [ ] Create tutorial for auto-withdrawal
- [ ] Document how to monitor bots
- [ ] Document withdrawal frequency limits

### Team Communication
- [ ] Notify QA team of new features
- [ ] Inform support team
- [ ] Update API documentation
- [ ] Schedule training session

---

## ✋ Production Deployment Approval

### Pre-Deployment Review
- [ ] Code review completed
- [ ] Security review completed
- [ ] Testing report reviewed
- [ ] Documentation reviewed

### Final Approval Gates
- [ ] Lead developer approval: ___________
- [ ] QA lead approval: ___________
- [ ] Security approval: ___________
- [ ] Ops/DevOps approval: ___________

### Deployment Authorization
- [ ] Authorized by: ___________
- [ ] Date: ___________
- [ ] Time: ___________
- [ ] Rollback plan approved: Yes / No

---

## 📋 Post-Deployment Checklist

### Immediate (First 1 hour)
- [ ] Service is running
- [ ] All endpoints responding
- [ ] Database tables exist
- [ ] Logs showing normal operation
- [ ] No error spikes

### Short-term (First 24 hours)
- [ ] Monitor log files
- [ ] Test with real trading bots
- [ ] Verify auto-withdrawals trigger correctly
- [ ] Monitor database growth
- [ ] Check error rates

### Medium-term (First week)
- [ ] Review withdrawal history
- [ ] Verify fee calculations
- [ ] Check for any issues
- [ ] Monitor system resources
- [ ] Get user feedback

### Long-term (First month)
- [ ] Review performance metrics
- [ ] Update documentation as needed
- [ ] Plan future enhancements
- [ ] Gather usage statistics
- [ ] Optimize based on performance

---

## 🆘 Rollback Plan

### If Issues Occur:
1. **Stop current service**
   ```bash
   # Kill the Python process
   pkill -f "multi_broker_backend_updated.py"
   ```

2. **Restore previous version**
   ```bash
   # Copy previous backup
   cp multi_broker_backend.py.backup multi_broker_backend.py
   ```

3. **Restore database**
   ```bash
   # Restore from backup if needed
   sqlite3 trading_data.db < backup.sql
   ```

4. **Restart service**
   ```bash
   python multi_broker_backend.py
   ```

5. **Verify operation**
   - Test basic endpoints
   - Monitor logs
   - Notify team

---

## 📞 Troubleshooting Hotline

If deployment issues occur:

### Issue: Server won't start
- [ ] Check Python is installed: `python --version`
- [ ] Check dependencies: `pip list | grep flask`
- [ ] Check port is free: `netstat -an | grep 9000`
- [ ] Check logs: `tail -100 multi_broker_backend.log`

### Issue: Tests fail
- [ ] Check server is running
- [ ] Check API key is correct
- [ ] Check network connectivity
- [ ] Run with verbose output: `python test_bot_monitoring.py -v`

### Issue: No auto-withdrawal
- [ ] Check monitoring thread started (in logs)
- [ ] Check auto-withdrawal setting exists
- [ ] Check bot profit is >= target
- [ ] Wait for next check cycle (30 sec)
- [ ] Check database records

### Issue: API errors
- [ ] Check request format (JSON)
- [ ] Check headers (X-API-Key)
- [ ] Check content-type
- [ ] Check parameter names
- [ ] Review error message

---

## ✅ Deployment Sign-Off

**Deployment Date:** ___________
**Deployed By:** ___________
**Verified By:** ___________
**Notes:** 
___________________________________________________________________
___________________________________________________________________

---

## 📞 Support Contact

For issues or questions:
- Email: support@zwesta.com
- Slack: #trading-platform
- Issue Tracker: GitHub Issues
- Documentation: See BOT_MONITORING_AND_WITHDRAWAL_GUIDE.md

---

**Checklist Version:** 1.0
**Last Updated:** January 2024
**Status:** Ready for Deployment ✅
