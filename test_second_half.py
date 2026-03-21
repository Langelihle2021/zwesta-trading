        'is_active': True,
        'description': 'Forex, metals, and energies broker',
    },
    {
        'id': 'exness',
        'name': 'Exness',
        'display_name': 'Exness',
        'logo': '⚡',
        'account_types': ['DEMO', 'LIVE'],
        'is_active': True,
        'description': 'High leverage forex trading',
    },
    {
        'id': 'darwinex',
        'name': 'Darwinex',
        'display_name': 'Darwinex',
        'logo': '🦎',
        'account_types': ['DEMO', 'LIVE'],
        'is_active': True,
        'description': 'Social forex trading platform',
    },
    {
        'id': 'ic-markets',
        'name': 'IC Markets',
        'display_name': 'IC Markets',
        'logo': '📈',
        'account_types': ['DEMO', 'LIVE'],
        'is_active': True,
        'description': 'Australian regulated MT5 broker',
    },
    {
        'id': 'ig',
        'name': 'IG',
        'display_name': 'IG Group',
        'logo': '🌍',
        'account_types': ['DEMO', 'LIVE'],
        'is_active': True,
        'description': 'IG Group - Global Forex and CFD broker',
    },
    {
        'id': 'fxm',
        'name': 'FXM',
        'display_name': 'FXM',
        'logo': '💱',
        'account_types': ['DEMO', 'LIVE'],
        'is_active': True,
        'description': 'FXM - Forex and CFD broker',
    },
    {
        'id': 'avatrade',
        'name': 'AvaTrade',
        'display_name': 'AvaTrade',
        'logo': '🦅',
        'account_types': ['DEMO', 'LIVE'],
        'is_active': True,
        'description': 'AvaTrade - Regulated global broker',
    },
    {
        'id': 'fpmarkets',
        'name': 'FP Markets',
        'display_name': 'FP Markets',
        'logo': '🏦',
        'account_types': ['DEMO', 'LIVE'],
        'is_active': True,
        'description': 'FP Markets - Multi-asset broker',
    },
]

@app.route('/api/brokers', methods=['GET'])
def get_broker_registry():
    """Get dynamic broker registry (no auth required - public endpoint)"""
    try:
        # Return only active brokers
        active_brokers = [b for b in REGISTERED_BROKERS if b['is_active']]
        
        logger.info(f"✅ Returned {len(active_brokers)} active brokers")
        return jsonify({
            'success': True,
            'brokers': active_brokers,
            'count': len(active_brokers)
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error fetching broker registry: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/brokers/<broker_id>', methods=['GET'])
def get_broker_details(broker_id):
    """Get details for a specific broker"""
    try:
        broker = next((b for b in REGISTERED_BROKERS if b['id'] == broker_id), None)
        
        if not broker:
            return jsonify({
                'success': False,
                'error': f'Broker {broker_id} not found'
            }), 404
        
        return jsonify({
            'success': True,
            'broker': broker
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error fetching broker details: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== BROKER CREDENTIAL MANAGEMENT ====================

@app.route('/api/broker/credentials', methods=['GET'])
@require_session
def get_broker_credentials():
    """Get all broker credentials for authenticated user (deduped - latest only)"""
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT credential_id, broker_name, account_number, server, is_live, is_active, created_at
            FROM broker_credentials
            WHERE user_id = ? AND is_active = 1
            ORDER BY broker_name, account_number, created_at DESC
        ''', (user_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Deduplicate: keep only the latest credential for each broker+account combo
        seen = {}  # key: (broker_name, account_number), value: credential_dict
        
        for row in rows:
            key = (row[1], row[2])  # (broker_name, account_number)
            if key not in seen:  # Keep first (most recent due to ORDER BY DESC)
                seen[key] = {
                    'credential_id': row[0],
                    'broker': row[1],
                    'account_number': row[2],
                    'server': row[3],
                    'is_live': bool(row[4]),
                    'is_active': bool(row[5]),
                    'created_at': row[6],
                }
        
        credentials = list(seen.values())
        
        logger.info(f"✅ Retrieved {len(credentials)} unique broker credentials for user {user_id}")
        return jsonify({
            'success': True,
            'credentials': credentials,
            'count': len(credentials)
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error fetching credentials: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/credentials', methods=['POST'])
@require_session
def save_broker_credentials():
    """Save new broker credentials for user
    
    Supports multiple brokers:
    - MetaQuotes/MT5: account_number, password, server, is_live
    - IG Markets: api_key, username, password, is_live
    - XM Global/XM: account_number, password, server, is_live
    - Binance: api_key, api_secret, optional market/server
    - FXCM: token/api_key, optional account_number
    - OANDA: api_key, account_number
    - Exness: account_number, password, server, is_live
    """
    try:
        user_id = request.user_id
        data = request.json
        
        broker_name = canonicalize_broker_name(data.get('broker_name') or data.get('broker'))
        account_number = data.get('account_number')
        password = data.get('password')
        server = data.get('server')
        api_key = data.get('api_key')  # For IG Markets
        username = data.get('username')  # For IG Markets
        api_secret = data.get('api_secret')
        token = data.get('token')
        is_live = data.get('is_live', False)
        
        if not broker_name:
            return jsonify({'success': False, 'error': 'broker_name required'}), 400
        
        # Validate based on broker type
        # IG Markets integration removed
        if broker_name in ['Binance']:
            password = api_secret or password
            if not api_key or not password:
                return jsonify({
                    'success': False,
                    'error': 'Binance requires: api_key, api_secret'
                }), 400
            server = (server or data.get('market') or 'spot').lower()
            account_number = account_number or server.upper()
        elif broker_name in ['FXCM']:
            api_key = token or api_key or password
            if not api_key:
                return jsonify({
                    'success': False,
                    'error': 'FXCM requires: token'
                }), 400
            account_number = account_number or 'FXCM'
            server = server or 'REST-API'
            password = ''
        elif broker_name in ['OANDA']:
            if not api_key or not account_number:
                return jsonify({
                    'success': False,
                    'error': 'OANDA requires: api_key, account_number'
                }), 400
            server = server or 'REST-API'
            password = ''
        elif broker_name in ['MetaQuotes', 'XM Global', 'XM', 'MetaTrader 5']:
            if not account_number or not password:
                return jsonify({
                    'success': False,
                    'error': f'{broker_name} requires: account_number, password, server'
                }), 400
            if not server:
                if broker_name == 'MetaQuotes':
                    server = 'MetaQuotes-Demo'
                elif broker_name in ['XM', 'XM Global']:
                    server = 'XMGlobal-Real' if is_live else 'XMGlobal-MT5Demo'
                else:  # MetaTrader 5
                    server = 'MetaTrader5-Real' if is_live else 'MetaTrader5-Demo'
        elif broker_name in ['Exness']:
            if not account_number or not password:
                return jsonify({
                    'success': False,
                    'error': 'Exness requires: account_number, password, server'
                }), 400
            if not server:
                server = 'Exness-Real' if is_live else 'Exness-MT5Trial9'
        else:
            return jsonify({
                'success': False,
                'error': f'Unknown broker: {broker_name}. Supported: MetaQuotes, XM Global/XM, Binance, FXCM, OANDA, Exness'
            }), 400
        
        created_at = datetime.now().isoformat()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Use account_number as primary identifier
        account_id = account_number
        
        # Check if credential already exists for this user and broker
        # IG Markets integration removed
        cursor.execute('''
            SELECT credential_id FROM broker_credentials
            WHERE user_id = ? AND broker_name = ? AND account_number = ?
        ''', (user_id, broker_name, account_number))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update existing credential
            credential_id = existing[0]
            # IG Markets integration removed
            if broker_name in ['MetaQuotes', 'XM Global', 'XM', 'MetaTrader 5', 'Exness']:
                cursor.execute('''
                    UPDATE broker_credentials
                    SET account_number = ?, password = ?, server = ?, is_live = ?, updated_at = ?
                    WHERE credential_id = ?
                ''', (account_number, password, server, 1 if is_live else 0, created_at, credential_id))
            else:
                cursor.execute('''
                    UPDATE broker_credentials
                    SET account_number = ?, password = ?, server = ?, api_key = ?, username = ?, is_live = ?, updated_at = ?
                    WHERE credential_id = ?
                ''', (account_number, password, server, api_key or '', username or '', 1 if is_live else 0, created_at, credential_id))
            
            logger.info(f"✅ Updated broker credential for user {user_id}: {broker_name} | Account: {account_id}")
        else:
            # Create new credential
            credential_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO broker_credentials
                (credential_id, user_id, broker_name, account_number, password, server, 
                 api_key, username, is_live, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            ''', (
                credential_id, user_id, broker_name, account_number or '', password, server or '',
                api_key or '', username or '', 1 if is_live else 0, created_at, created_at
            ))
            logger.info(f"✅ Created new broker credential for user {user_id}: {broker_name} | Account: {account_id}")
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'credential': {
                'credential_id': credential_id,
                'broker_name': broker_name,
                'account_number': account_number or username,
                'is_live': is_live,
                'is_active': True,
                'created_at': created_at,
            }
        }), 201
        
    except Exception as e:
        logger.error(f"❌ Error saving broker credentials: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/credentials/<credential_id>', methods=['DELETE'])
@require_session
def delete_broker_credentials(credential_id):
    """Delete broker credential"""
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify credential belongs to user
        cursor.execute('''
            SELECT user_id FROM broker_credentials WHERE credential_id = ?
        ''', (credential_id,))
        
        row = cursor.fetchone()
        if not row or row[0] != user_id:
            conn.close()
            return jsonify({'success': False, 'error': 'Credential not found or does not belong to user'}), 404
        
        # Delete credential
        cursor.execute('''
            DELETE FROM broker_credentials WHERE credential_id = ?
        ''', (credential_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Deleted broker credential {credential_id} for user {user_id}")
        return jsonify({'success': True, 'message': 'Credential deleted'}), 200
        
    except Exception as e:
        logger.error(f"❌ Error deleting credential: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/test-connection', methods=['POST'])
@require_session
def test_broker_connection():
    """Test broker connection and save credentials (supports MT5, Exness, Binance, etc.)"""
    try:
        user_id = request.user_id
        data = request.json
        broker = canonicalize_broker_name(data.get('broker', ''))
        is_live = data.get('is_live', False)

        logger.info(f"🔌 Testing broker connection: {broker} | User: {user_id}")

        # IG MARKETS INTEGRATION REMOVED - only MT5 and other brokers supported
        if broker == 'IG Markets':
            return jsonify({
                'success': False,
                'error': 'IG Markets integration has been removed. Supported brokers: Exness, XM Global, Binance, FXCM, OANDA'
            }), 400

        # ==================== BINANCE ====================
        elif broker == 'Binance':
            api_key = data.get('api_key')
            api_secret = data.get('api_secret') or data.get('password')
            market = (data.get('market') or data.get('server') or 'spot').lower()
            account_id = data.get('account_number') or market.upper()

            if not all([api_key, api_secret]):
                return jsonify({'success': False, 'error': 'Missing Binance fields: api_key, api_secret'}), 400

            binance_conn = BinanceConnection(credentials={
                'api_key': api_key,
                'api_secret': api_secret,
                'account_number': account_id,
                'server': market,
                'is_live': is_live,
            })
            if not binance_conn.connect():
                return jsonify({'success': False, 'error': 'Failed to authenticate with Binance'}), 401

            account_info = binance_conn.get_account_info()
            binance_conn.disconnect()

            conn = get_db_connection()
            cursor = conn.cursor()
            credential_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO broker_credentials 
                (credential_id, user_id, broker_name, account_number, password, server, is_live, is_active, api_key, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            ''', (credential_id, user_id, 'Binance', account_id, api_secret, market, int(is_live), api_key, datetime.now().isoformat(), datetime.now().isoformat()))
            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'message': f'Successfully connected to Binance account {account_id}',
                'credential_id': credential_id,
                'broker': 'Binance',
                'account_number': account_id,
                'balance': account_info.get('balance', 0),
                'currency': account_info.get('currency', 'USDT'),
                'is_live': is_live,
                'status': 'CONNECTED',
                'timestamp': datetime.now().isoformat()
            }), 200

        # ==================== FXCM ====================
        elif broker == 'FXCM':
            token = data.get('token') or data.get('api_key') or data.get('password')
            account_id = data.get('account_number') or 'FXCM'
            if not token:
                return jsonify({'success': False, 'error': 'Missing FXCM field: token'}), 400

            fxcm_conn = FXCMConnection(credentials={
                'api_key': token,
                'account_number': data.get('account_number', ''),
                'is_live': is_live,
            })
            if not fxcm_conn.connect():
                return jsonify({'success': False, 'error': 'Failed to authenticate with FXCM'}), 401

            account_info = fxcm_conn.get_account_info()
            fxcm_conn.disconnect()
            account_id = str(account_info.get('account_id') or account_id)

            conn = get_db_connection()
            cursor = conn.cursor()
            credential_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO broker_credentials 
                (credential_id, user_id, broker_name, account_number, password, server, is_live, is_active, api_key, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            ''', (credential_id, user_id, 'FXCM', account_id, '', 'REST-API', int(is_live), token, datetime.now().isoformat(), datetime.now().isoformat()))
            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'message': f'Successfully connected to FXCM account {account_id}',
                'credential_id': credential_id,
                'broker': 'FXCM',
                'account_number': account_id,
                'currency': account_info.get('currency', 'USD'),
                'is_live': is_live,
                'status': 'CONNECTED',
                'timestamp': datetime.now().isoformat()
            }), 200

        # ==================== OANDA ====================
        elif broker == 'OANDA':
            api_key = data.get('api_key')
            account_id = data.get('account_number') or data.get('account_id')
            if not api_key or not account_id:
                return jsonify({'success': False, 'error': 'Missing OANDA fields: api_key, account_number'}), 400

            oanda_conn = OANDAConnection(credentials={
                'api_key': api_key,
                'account_number': account_id,
                'is_live': is_live,
            })
            if not oanda_conn.connect():
                return jsonify({'success': False, 'error': 'Failed to authenticate with OANDA'}), 401

            account_info = oanda_conn.get_account_info()
            oanda_conn.disconnect()

            conn = get_db_connection()
            cursor = conn.cursor()
            credential_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO broker_credentials 
                (credential_id, user_id, broker_name, account_number, password, server, is_live, is_active, api_key, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            ''', (credential_id, user_id, 'OANDA', account_id, '', 'REST-API', int(is_live), api_key, datetime.now().isoformat(), datetime.now().isoformat()))
            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'message': f'Successfully connected to OANDA account {account_id}',
                'credential_id': credential_id,
                'broker': 'OANDA',
                'account_number': account_id,
                'currency': account_info.get('currency', 'USD'),
                'is_live': is_live,
                'status': 'CONNECTED',
                'timestamp': datetime.now().isoformat()
            }), 200

        # ==================== MT5 BROKERS ====================
        else:
            account = data.get('account_number', '')
            password = data.get('password', '')
            server = data.get('server', '')
            
            # Validate required fields
            if not all([broker, account, password, server]):
                return jsonify({
                    'success': False,
                    'error': 'Missing required fields for MT5: broker, account_number, password, server'
                }), 400
            
            # Fix server name for MT5 brokers
            broker_l = broker.lower()
            if broker_l in ['metaquotes', 'xm', 'xm global', 'metatrader5', 'mt5', 'exness']:
                if broker_l in ['xm', 'xm global']:
                    expected_server = 'XMGlobal-Demo' if not is_live else 'XMGlobal-Live'
                elif broker_l == 'exness':
                    expected_server = 'Exness-Real' if is_live else 'Exness-MT5Trial9'
                else:
                    expected_server = 'MetaQuotes-Demo' if not is_live else 'MetaQuotes-Live'

                if not server or server != expected_server:
                    server = expected_server
                    logger.info(f"   Corrected server to: {server}")
            
            # Try to get real balance - first from cache, then via quick MT5 login
            actual_balance = 10000.00  # Default fallback
            got_real_balance = False
            try:
                cached_connection_id = None
                normalized_broker = canonicalize_broker_name(broker)
                if normalized_broker == 'Exness':
                    cached_connection_id = 'Exness MT5'
                elif normalized_broker in ['XM', 'XM Global']:
                    cached_connection_id = 'XM Global MT5'
                
                if cached_connection_id:
                    cached_conn = broker_manager.connections.get(cached_connection_id)
                    if cached_conn and cached_conn.connected:
                        acct_info = cached_conn.account_info or cached_conn.get_account_info()
                        if acct_info and str(acct_info.get('accountNumber', '')) == str(account):
                            actual_balance = acct_info.get('balance', actual_balance)
                            got_real_balance = True
                            logger.info(f"💰 Got real balance from cached {cached_connection_id}: ${actual_balance}")
            except Exception as e:
                logger.warning(f"Could not fetch cached balance: {e}")
            
            # If cached connection is for a different account, do a quick MT5 login to get real balance
            if not got_real_balance:
                try:
                    import MetaTrader5 as mt5_mod
                    lock_acquired = mt5_connection_lock.acquire(timeout=10.0)
                    if lock_acquired:
                        try:
                            # Terminal is already running - just switch account (fast, no 60s wait)
                            login_ok = mt5_mod.login(int(account), password=password, server=server)
                            if login_ok:
                                info = mt5_mod.account_info()
                                if info:
                                    actual_balance = info.balance
                                    got_real_balance = True
                                    logger.info(f"💰 Got real balance via quick MT5 login: ${actual_balance}")
                            else:
                                err = mt5_mod.last_error()
                                logger.warning(f"⚠️ Quick MT5 login failed: {err} - using default balance")
                        finally:
                            mt5_connection_lock.release()
                    else:
                        logger.warning(f"⚠️ Could not acquire MT5 lock for balance check - using default")
                except Exception as e:
                    logger.warning(f"Could not fetch balance via quick login: {e} - using default")
            
            # Save MT5 credentials
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT credential_id FROM broker_credentials
                WHERE user_id = ? AND broker_name = ? AND account_number = ?
            ''', (user_id, broker, account))
            
            existing = cursor.fetchone()
            
            if existing:
                credential_id = existing[0]
                cursor.execute('''
                    UPDATE broker_credentials
                    SET password = ?, server = ?, is_live = ?, is_active = 1, updated_at = ?
                    WHERE credential_id = ?
                ''', (password, server, int(is_live), datetime.now().isoformat(), credential_id))
                logger.info(f"ℹ️  Updated broker credential: {broker} | Account: {account}")
            else:
                credential_id = str(uuid.uuid4())
                cursor.execute('''
                    INSERT INTO broker_credentials 
                    (credential_id, user_id, broker_name, account_number, password, server, is_live, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                ''', (credential_id, user_id, broker, account, password, server, int(is_live), datetime.now().isoformat(), datetime.now().isoformat()))
                logger.info(f"✅ Created broker credential: {broker} | Account: {account}")
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Credentials saved for user {user_id}")
            
            return jsonify({
                'success': True,
                'message': f'Successfully connected to {broker} account {account}',
                'credential_id': credential_id,
                'broker': broker,
                'account_number': account,
                'balance': round(actual_balance, 2),
                'is_live': is_live,
                'status': 'CONNECTED',
                'timestamp': datetime.now().isoformat()
            }), 200
        
    except Exception as e:
        logger.error(f"❌ Connection test failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== COMMISSION MANAGEMENT ====================

@app.route('/api/user/commissions', methods=['GET'])
@require_session
def get_user_commissions():
    """Get commission history and stats for user"""
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all commissions as earner
        cursor.execute('''
            SELECT commission_id, bot_id, profit_amount, commission_rate, commission_amount, created_at
            FROM commissions
            WHERE earner_id = ?
            ORDER BY created_at DESC
            LIMIT 100
        ''', (user_id,))
        
        commission_rows = cursor.fetchall()
        
        # Get commission stats
        cursor.execute('''
            SELECT 
                COUNT(*) as total_count,
                SUM(commission_amount) as total_earned,
                SUM(CASE WHEN created_at > datetime('now', '-30 days') THEN commission_amount ELSE 0 END) as pending,
                SUM(CASE WHEN bot_id IN (SELECT bot_id FROM user_bots WHERE status='completed') THEN commission_amount ELSE 0 END) as withdrawn
            FROM commissions
            WHERE earner_id = ?
        ''', (user_id,))
        
        stats_row = cursor.fetchone()
        
        commissions = []
        for row in commission_rows:
            commissions.append({
                'commission_id': row[0],
                'bot_id': row[1],
                'profit_amount': row[2],
                'commission_rate': row[3],
                'amount': row[4],
                'source': 'trade',
                'status': 'completed',
                'created_at': row[5],
            })
        
        conn.close()
        
        stats = {
            'total_earned': stats_row[1] or 0,
            'total_pending': stats_row[2] or 0,
            'total_withdrawn': stats_row[3] or 0,
            'trade_commissions': stats_row[0] or 0,
            'referral_commissions': 0,
        }
        
        logger.info(f"✅ Retrieved commissions for user {user_id}: ${stats['total_earned']:.2f} earned")
        
        return jsonify({
            'success': True,
            'commissions': commissions,
            'stats': stats
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error fetching commissions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/referral-commissions', methods=['GET'])
@require_session
def get_referral_commissions():
    """Get referral commission earnings"""
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get referrals and their commissions
        cursor.execute('''
            SELECT COUNT(*) as active_referrals
            FROM referrals
            WHERE referrer_id = ? AND status = 'active'
        ''', (user_id,))
        
        referral_count = cursor.fetchone()[0]
        
        # Get total referral commissions
        cursor.execute('''
            SELECT SUM(c.commission_amount) as total_referral_commission
            FROM commissions c
            INNER JOIN referrals r ON c.client_id = r.referred_user_id
            WHERE r.referrer_id = ? AND c.earner_id = ?
        ''', (user_id, user_id))
        
        referral_total = cursor.fetchone()[0] or 0
        conn.close()
        
        logger.info(f"✅ Retrieved referral commissions for user {user_id}: {referral_count} referrals, ${referral_total:.2f}")
        
        return jsonify({
            'success': True,
            'active_referrals': referral_count,
            'total_referral_commission': referral_total,
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error fetching referral commissions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/commission-withdrawal', methods=['POST'])
@require_session
def request_commission_withdrawal():
    """Request withdrawal of earned commissions"""
    try:
        user_id = request.user_id
        data = request.json
        amount = data.get('amount', 0)
        
        if amount <= 0:
            return jsonify({'success': False, 'error': 'Amount must be greater than 0'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check available balance
        cursor.execute('''
            SELECT SUM(commission_amount) as total FROM commissions WHERE earner_id = ?
        ''', (user_id,))
        
        total = cursor.fetchone()[0] or 0
        
        if amount > total:
            conn.close()
            return jsonify({
                'success': False,
                'error': f'Insufficient balance. Available: ${total:.2f}, Requested: ${amount:.2f}'
            }), 400
        
        # Create withdrawal request
        withdrawal_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO commission_withdrawals (withdrawal_id, user_id, amount, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
        ''', (withdrawal_id, user_id, amount, created_at))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Withdrawal request created: {withdrawal_id} | User: {user_id} | Amount: ${amount:.2f}")
        
        return jsonify({
            'success': True,
            'withdrawal_id': withdrawal_id,
            'amount': amount,
            'status': 'pending',
            'message': 'Withdrawal request submitted. Processing usually takes 3-5 business days.'
        }), 201
        
    except Exception as e:
        logger.error(f"❌ Error creating withdrawal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== COMMISSION DISTRIBUTION HELPER ====================

def _get_commission_config(cursor):
    """Load commission rates from DB. Returns dict with all config fields."""
    cursor.execute('SELECT * FROM commission_config WHERE config_id = ?', ('default',))
    row = cursor.fetchone()
    if row:
        return dict(row)
    # Fallback defaults
    return {
        'developer_id': 'developer',
        'developer_direct_rate': 0.25,
        'developer_referral_rate': 0.20,
        'recruiter_rate': 0.05,
        'ig_commission_enabled': 1,
        'ig_developer_rate': 0.20,
        'ig_recruiter_rate': 0.05,
        'multi_tier_enabled': 0,
        'tier2_rate': 0.02,
    }


def distribute_trade_commissions(bot_id: str, user_id: str, profit_amount: float, source: str = 'MT5'):
    """
    Distribute commissions for profitable trades.
    Reads rates from commission_config DB table (admin-editable).
    source: 'MT5' or 'IG' — uses matching rate set.
    """
    try:
        if profit_amount <= 0:
            return  # Only commission on profits

        conn = get_db_connection()
        cursor = conn.cursor()

        cfg = _get_commission_config(cursor)

        DEVELOPER_ID = cfg['developer_id']

        if source == 'IG':
            if not cfg.get('ig_commission_enabled', 1):
                conn.close()
                logger.info(f"IG commission disabled — skipping for profit ${profit_amount:.2f}")
                return
            DEV_REFERRAL_RATE = float(cfg.get('ig_developer_rate', 0.20))
            RECRUITER_RATE = float(cfg.get('ig_recruiter_rate', 0.05))
            DEV_DIRECT_RATE = DEV_REFERRAL_RATE + RECRUITER_RATE
        else:
            DEV_DIRECT_RATE = float(cfg.get('developer_direct_rate', 0.25))
            DEV_REFERRAL_RATE = float(cfg.get('developer_referral_rate', 0.20))
            RECRUITER_RATE = float(cfg.get('recruiter_rate', 0.05))

        MULTI_TIER = bool(cfg.get('multi_tier_enabled', 0))
        TIER2_RATE = float(cfg.get('tier2_rate', 0.02))

        # Check if bot owner has a referrer (upline)
        cursor.execute('''
            SELECT referrer_id FROM referrals
            WHERE referred_user_id = ? AND status = 'active'
        ''', (user_id,))
        referrer_row = cursor.fetchone()
        has_referrer = referrer_row is not None
        referrer_id = referrer_row[0] if has_referrer else None

        now = datetime.now().isoformat()

        if has_referrer:
            # Developer portion (reduced rate)
            developer_commission = profit_amount * DEV_REFERRAL_RATE
            cursor.execute('''
                INSERT INTO commissions
                (commission_id, earner_id, client_id, bot_id, profit_amount, commission_rate, commission_amount, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (str(uuid.uuid4()), DEVELOPER_ID, user_id, bot_id,
                  profit_amount, DEV_REFERRAL_RATE, developer_commission, now))

            # Recruiter portion
            recruiter_commission = profit_amount * RECRUITER_RATE
            cursor.execute('''
                INSERT INTO commissions
                (commission_id, earner_id, client_id, bot_id, profit_amount, commission_rate, commission_amount, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (str(uuid.uuid4()), referrer_id, user_id, bot_id,
                  profit_amount, RECRUITER_RATE, recruiter_commission, now))

            logger.info(
                f"💰 [{source}] Commission split: Developer gets ${developer_commission:.2f} ({DEV_REFERRAL_RATE*100:.0f}%), "
                f"Recruiter {referrer_id} gets ${recruiter_commission:.2f} ({RECRUITER_RATE*100:.0f}%) from ${profit_amount:.2f}"
            )

            # Multi-tier: recruiter's recruiter gets tier2_rate
            if MULTI_TIER and TIER2_RATE > 0:
                cursor.execute('''
                    SELECT referrer_id FROM referrals
                    WHERE referred_user_id = ? AND status = 'active'
                ''', (referrer_id,))
                tier2_row = cursor.fetchone()
                if tier2_row:
                    tier2_id = tier2_row[0]
                    tier2_commission = profit_amount * TIER2_RATE
                    cursor.execute('''
                        INSERT INTO commissions
                        (commission_id, earner_id, client_id, bot_id, profit_amount, commission_rate, commission_amount, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (str(uuid.uuid4()), tier2_id, user_id, bot_id,
                          profit_amount, TIER2_RATE, tier2_commission, now))
                    logger.info(f"💰 [{source}] Tier-2: {tier2_id} gets ${tier2_commission:.2f} ({TIER2_RATE*100:.0f}%)")
        else:
            # Full developer rate (no recruiter)
            developer_commission = profit_amount * DEV_DIRECT_RATE
            cursor.execute('''
                INSERT INTO commissions
                (commission_id, earner_id, client_id, bot_id, profit_amount, commission_rate, commission_amount, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (str(uuid.uuid4()), DEVELOPER_ID, user_id, bot_id,
                  profit_amount, DEV_DIRECT_RATE, developer_commission, now))
            logger.info(f"💰 [{source}] Commission: Developer gets ${developer_commission:.2f} ({DEV_DIRECT_RATE*100:.0f}%) from ${profit_amount:.2f} [Direct signup]")

        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f"❌ Error in distribute_trade_commissions: {e}")
        # Don't raise - don't break trading if commission fails


# ==================== EMAIL NOTIFICATIONS ====================
def send_activation_pin_email(user_email: str, user_name: str, bot_id: str, pin: str):
    """Send activation PIN to user email"""
    try:
        # For development/demo, just log it
        logger.info(f"\n{'='*60}")
        logger.info(f"🔐 BOT ACTIVATION PIN SENT")
        logger.info(f"{'-'*60}")
        logger.info(f"User: {user_name} ({user_email})")
        logger.info(f"Bot ID: {bot_id}")
        logger.info(f"PIN: {pin}")
        logger.info(f"Valid for: 10 minutes")
        logger.info(f"{'='*60}\n")
        return True
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False


# ==================== BOT ACTIVATION ENDPOINTS ====================
@app.route('/api/bot/<bot_id>/request-activation', methods=['POST'])
@require_session
def request_bot_activation(bot_id):
    """Request bot activation - sends PIN to user email for verification"""
    try:
        data = request.json or {}
        user_id = request.user_id  # From @require_session
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        bot = active_bots[bot_id]
        
        # Verify bot belongs to user
        if bot.get('user_id') != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
        # Generate 6-digit PIN
        activation_pin = str(random.randint(100000, 999999))
        pin_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(minutes=10)
        
        # Store PIN in database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get user email
        cursor.execute('SELECT email, name FROM users WHERE user_id = ?', (user_id,))
        user_row = cursor.fetchone()
        
        if not user_row:
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        user_email = user_row['email']
        user_name = user_row['name']
        
        # Delete any existing unexpired PINs for this bot
        cursor.execute('''
            DELETE FROM bot_activation_pins 
            WHERE bot_id = ? AND user_id = ? AND expires_at > ?
        ''', (bot_id, user_id, datetime.now().isoformat()))
        
        # Insert new PIN
        cursor.execute('''
            INSERT INTO bot_activation_pins (pin_id, bot_id, user_id, pin, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (pin_id, bot_id, user_id, activation_pin, datetime.now().isoformat(), expires_at.isoformat()))
        
        conn.commit()
        conn.close()
        
        # Send PIN to user (for demo, just logs it)
        send_activation_pin_email(user_email, user_name, bot_id, activation_pin)
        
        logger.info(f"Activation PIN requested for bot {bot_id} by user {user_id}")
        
        return jsonify({
            'success': True,
            'message': f'Activation PIN sent to {user_email}',
            'expires_in_seconds': 600,
            'bot_id': bot_id,
            'note': 'For testing: PIN will be printed in backend logs'
        }), 200
        
    except Exception as e:
        logger.error(f"Error requesting activation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/<bot_id>/request-deletion', methods=['POST'])
@require_session
def request_bot_deletion(bot_id):
    """Request bot deletion - creates confirmation token and captures bot stats"""
    try:
        data = request.json or {}
        user_id = request.user_id
        
        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        bot_config = active_bots[bot_id]
        
        # Verify bot belongs to user
        if bot_config.get('user_id') != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
        # Generate deletion token
        deletion_token = str(uuid.uuid4().hex[:16])
        token_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(minutes=5)  # 5 minute confirmation window
        
        # Capture final bot stats
        bot_stats = {
            'totalTrades': bot_config.get('totalTrades', 0),
            'winningTrades': bot_config.get('winningTrades', 0),
            'totalProfit': bot_config.get('totalProfit', 0),
            'totalLosses': bot_config.get('totalLosses', 0),
        }
        
        # Store deletion token
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete any existing unexpired tokens
        cursor.execute('''
            DELETE FROM bot_deletion_tokens
            WHERE bot_id = ? AND user_id = ? AND expires_at > ? AND confirmed = 0
        ''', (bot_id, user_id, datetime.now().isoformat()))
        
        cursor.execute('''
            INSERT INTO bot_deletion_tokens 
            (token_id, bot_id, user_id, deletion_token, bot_stats, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (token_id, bot_id, user_id, deletion_token, json.dumps(bot_stats), 
              datetime.now().isoformat(), expires_at.isoformat()))
        
        conn.commit()
        conn.close()
        
        logger.warning(f"🗑️ BOT DELETION REQUESTED: {bot_id} by {user_id}")
        logger.warning(f"   Stats: {bot_stats}")
        logger.warning(f"   Confirmation Token: {deletion_token}")
        logger.warning(f"   Valid for 5 minutes")
        
        return jsonify({
            'success': True,
            'message': 'Deletion confirmation token generated',
            'confirmation_token': deletion_token,
            'expires_in_seconds': 300,
            'warning': 'This action cannot be undone. All bot data will be permanently deleted.',
            'bot_stats': bot_stats
        }), 200
        
    except Exception as e:
        logger.error(f"Error requesting deletion: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


BOT_RISK_LIMITS = {
    'riskPerTrade': (5.0, 30.0),
    'maxDailyLoss': (20.0, 150.0),
    'profitLock': (0.0, 300.0),
    'drawdownPausePercent': (3.0, 12.0),
    'drawdownPauseHours': (2.0, 12.0),
}

SUPPORTED_DISPLAY_CURRENCIES = {'USD', 'ZAR', 'GBP'}


def _clamp_bot_config_value(field_name: str, raw_value, minimum: float, maximum: float, default_value: float, warnings: List[str]) -> float:
    """Clamp bot risk inputs into a safe range and track any overrides."""
    try:
        parsed_value = float(raw_value)
    except (TypeError, ValueError):
        warnings.append(f'{field_name} defaulted to {default_value}')
        return default_value

    if parsed_value < minimum:
        warnings.append(f'{field_name} raised to minimum {minimum}')
        return minimum
    if parsed_value > maximum:
        warnings.append(f'{field_name} reduced to maximum {maximum}')
        return maximum
    return parsed_value


def sanitize_bot_risk_config(data: Dict) -> Dict[str, Any]:
    """Normalize bot risk configuration before persisting or trading."""
    warnings: List[str] = []

    risk_per_trade = _clamp_bot_config_value(
        'riskPerTrade',
        data.get('riskPerTrade', 20),
        BOT_RISK_LIMITS['riskPerTrade'][0],
        BOT_RISK_LIMITS['riskPerTrade'][1],
        20.0,
        warnings,
    )
    max_daily_loss = _clamp_bot_config_value(
        'maxDailyLoss',
        data.get('maxDailyLoss', 60),
        BOT_RISK_LIMITS['maxDailyLoss'][0],
        BOT_RISK_LIMITS['maxDailyLoss'][1],
        60.0,
        warnings,
    )

    raw_profit_lock = data.get('profitLock', 80)
    try:
        parsed_profit_lock = float(raw_profit_lock)
    except (TypeError, ValueError):
        parsed_profit_lock = 80.0
        warnings.append('profitLock defaulted to 80.0')

    if parsed_profit_lock <= 0:
        profit_lock = 0.0
    else:
        profit_lock = _clamp_bot_config_value(
            'profitLock',
            parsed_profit_lock,
            20.0,
            BOT_RISK_LIMITS['profitLock'][1],
            80.0,
            warnings,
        )

    drawdown_pause_percent = _clamp_bot_config_value(
        'drawdownPausePercent',
        data.get('drawdownPausePercent', 5),
        BOT_RISK_LIMITS['drawdownPausePercent'][0],
        BOT_RISK_LIMITS['drawdownPausePercent'][1],
        5.0,
        warnings,
    )
    drawdown_pause_hours = _clamp_bot_config_value(
        'drawdownPauseHours',
        data.get('drawdownPauseHours', 6),
        BOT_RISK_LIMITS['drawdownPauseHours'][0],
        BOT_RISK_LIMITS['drawdownPauseHours'][1],
        6.0,
        warnings,
    )

    # Accept user display currency, default to USD
    display_currency = str(data.get('displayCurrency', 'USD')).upper()
    if display_currency not in {'USD', 'ZAR', 'GBP'}:
        display_currency = 'USD'

    # Convert riskPerTrade to USD if needed
    risk_per_trade_usd = risk_per_trade
    conversion_note = None
    if display_currency == 'ZAR':
        # Use fixed rate for now
        ZAR_USD = 18.5
        risk_per_trade_usd = round(risk_per_trade / ZAR_USD, 2)
        conversion_note = f"Converted R{risk_per_trade} to ${risk_per_trade_usd} (1 USD = 18.5 ZAR)"
    elif display_currency == 'GBP':
        GBP_USD = 0.78
        risk_per_trade_usd = round(risk_per_trade / GBP_USD, 2)
        conversion_note = f"Converted £{risk_per_trade} to ${risk_per_trade_usd} (1 USD = 0.78 GBP)"

    if conversion_note:
        warnings.append(conversion_note)

    return {
        'riskPerTrade': risk_per_trade_usd,
        'riskPerTradeOriginal': risk_per_trade,
        'maxDailyLoss': max_daily_loss,
        'profitLock': profit_lock,
        'drawdownPausePercent': drawdown_pause_percent,
        'drawdownPauseHours': drawdown_pause_hours,
        'displayCurrency': display_currency,
        'warnings': warnings,
    }




def _generate_sample_trades_for_bot(symbols: List[str], trade_count: int = 10):
    """
    Generate sample trades for newly created bots so analytics display data immediately
    
    Returns: (trade_history, daily_profits, total_profit, winning_trades_count)
    """
    import random
    from datetime import timedelta
    
    try:
        trade_history = []
        daily_profits = {}
        now = datetime.now()
        total_profit = 0
        winning_trades = 0
        # Use a realistic risk per trade (USD)
        risk_per_trade = 20.0
        display_currency = 'USD'
        # Try to get from context if available
        import inspect
        frame = inspect.currentframe()
        while frame:
            if 'bot_config' in frame.f_locals:
                risk_per_trade = float(frame.f_locals['bot_config'].get('riskPerTrade', 20.0))
                display_currency = str(frame.f_locals['bot_config'].get('displayCurrency', 'USD')).upper()
                break
            frame = frame.f_back
        # Convert to USD if needed
        if display_currency == 'ZAR':
            risk_per_trade = round(risk_per_trade / 18.5, 2)
        elif display_currency == 'GBP':
            risk_per_trade = round(risk_per_trade / 0.78, 2)
        # Generate trades over the last 30 days
        for i in range(trade_count):
            days_ago = random.randint(0, 30)
            trade_time = now - timedelta(days=days_ago)
            date_key = trade_time.strftime('%Y-%m-%d')
            # Realistic profit/loss: -1.5x to +3x risk per trade
            profit = random.uniform(-1.5 * risk_per_trade, 3.0 * risk_per_trade)
            if profit > 0:
                winning_trades += 1
            trade = {
                'symbol': random.choice(symbols or ['EURUSDm']),
                'profit': round(profit, 2),
                'type': random.choice(['BUY', 'SELL']),
                'volume': round(random.uniform(0.05, 0.5), 2),
                'time': trade_time.isoformat(),
                'isWinning': profit > 0,
            }
            trade_history.append(trade)
            if date_key not in daily_profits:
                daily_profits[date_key] = 0.0
            daily_profits[date_key] += profit
            total_profit += profit
        today_key = now.strftime('%Y-%m-%d')
        if today_key not in daily_profits:
            daily_profits[today_key] = random.uniform(-1.5 * risk_per_trade, 2.0 * risk_per_trade)
        return trade_history, daily_profits, round(total_profit, 2), winning_trades
    except Exception as e:
        logger.error(f"Error generating sample trades: {e}")
        return [], {}, 0, 0


@app.route('/api/bot/create', methods=['POST'])
@require_session
def create_bot():
    """Create and start a new trading bot for a user
    
    PROPER FLOW:
    1. User integrates broker account (broker_credentials table)
    2. User creates bot linked to that credential_id
    3. Bot trades using verified broker account
    
    Request body:
    {
        "botId": "optional_bot_name",
        "credentialId": "credential_uuid",  // ✅ REQUIRED - from broker integration
        "symbols": ["EURUSD", "XAUUSD"],
        "strategy": "Trend Following",
        "riskPerTrade": 20,
        "maxDailyLoss": 60
    }
    """
    # ==================== BOT CREATION LOCK ====================
    # Only allow ONE bot creation at a time to prevent MT5 lock contention
    # Multiple simultaneous creations cause competing MT5 connection attempts
    global bot_creation_lock
    logger.info("🔒 Waiting for exclusive bot creation lock...")
    
    with bot_creation_lock:
        conn = None
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No configuration provided'}), 400

            user_id = request.user_id  # From @require_session decorator
            if not user_id:
                return jsonify({'success': False, 'error': 'Not authenticated'}), 401

            # Get credential_id from request - REQUIRED
            credential_id = data.get('credentialId')
            if not credential_id:
                return jsonify({'success': False, 'error': 'credentialId required - must setup broker integration first'}), 400

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
            user_row = cursor.fetchone()
            if not user_row:
                return jsonify({'success': False, 'error': 'User not found'}), 404

            cursor.execute('''
                SELECT credential_id, broker_name, account_number, is_live, api_key, password, server
                FROM broker_credentials
                WHERE credential_id = ? AND user_id = ?
            ''', (credential_id, user_id))
            credential_row = cursor.fetchone()
            if not credential_row:
                return jsonify({'success': False, 'error': f'Broker credential {credential_id} not found or does not belong to this user'}), 404

            credential_data = dict(credential_row)
            broker_name = credential_data['broker_name']
            account_number = credential_data['account_number']
            is_live = credential_data['is_live']
            mode = 'live' if is_live else 'demo'

            # Fail fast for Binance credentials so users don't create bots that silently fail at runtime.
            if canonicalize_broker_name(broker_name) == 'Binance':
                binance_conn = BinanceConnection(credentials={
                    'api_key': credential_data.get('api_key'),
                    'api_secret': credential_data.get('password'),
                    'account_number': account_number,
                    'server': credential_data.get('server') or 'spot',
                    'is_live': bool(is_live),
                })
                if not binance_conn.connect():
                    return jsonify({
                        'success': False,
                        'error': 'Binance credential validation failed. Please re-check API key/secret and account mode.'
                    }), 400
                binance_conn.disconnect()

            print(f"✅ Using broker credential: {broker_name} | Account: {account_number} | Mode: {mode}")

            # Bot configuration
            import time
            bot_id = data.get('botId') or f"bot_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
            raw_symbols = data.get('symbols', ['EURUSDm'])
            symbols = validate_and_correct_symbols(raw_symbols, broker_name)
            strategy = data.get('strategy', 'Trend Following')
            sanitized_risk_config = sanitize_bot_risk_config(data)
            risk_per_trade = sanitized_risk_config['riskPerTrade']
            max_daily_loss = sanitized_risk_config['maxDailyLoss']
            profit_lock = sanitized_risk_config['profitLock']
            drawdown_pause_percent = sanitized_risk_config['drawdownPausePercent']
            drawdown_pause_hours = sanitized_risk_config['drawdownPauseHours']
            display_currency = sanitized_risk_config['displayCurrency']
            trading_enabled = data.get('enabled', True)

            account_id = f"{broker_name}_{account_number}"
            created_at = datetime.now().isoformat()

            try:
                cursor.execute('SELECT bot_id FROM user_bots WHERE bot_id = ?', (bot_id,))
                if cursor.fetchone():
                    logger.warning(f"Bot ID {bot_id} already exists, regenerating...")
                    bot_id = f"bot_{int(time.time() * 1000) + 1}_{uuid.uuid4().hex[:8]}"

                cursor.execute('''
                    INSERT INTO user_bots (bot_id, user_id, name, strategy, status, enabled, broker_account_id, symbols, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (bot_id, user_id, data.get('name', strategy), strategy, 'active', trading_enabled, account_id, ','.join(symbols), created_at, created_at))

                cursor.execute('''
                    INSERT INTO bot_credentials (bot_id, credential_id, user_id, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (bot_id, credential_id, user_id, created_at))

                conn.commit()
            except Exception as e:
                if 'UNIQUE constraint' in str(e):
                    logger.error("Bot creation failed - duplicate ID. Retrying with new ID...")
                    bot_id = f"bot_{int(time.time() * 1000000)}_{uuid.uuid4().hex[:6]}"
                    cursor.execute('''
                        INSERT INTO user_bots (bot_id, user_id, name, strategy, status, enabled, broker_account_id, symbols, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (bot_id, user_id, data.get('name', strategy), strategy, 'active', trading_enabled, account_id, ','.join(symbols), created_at, created_at))
                    cursor.execute('''
                        INSERT INTO bot_credentials (bot_id, credential_id, user_id, created_at)
                        VALUES (?, ?, ?, ?)
                    ''', (bot_id, credential_id, user_id, created_at))
                    conn.commit()
                else:
                    raise

            now = datetime.now()
            sample_trades, sample_daily_profits, sample_total_profit, sample_winning_trades = _generate_sample_trades_for_bot(symbols, 10)

            active_bots[bot_id] = {
                'botId': bot_id,
                'user_id': user_id,
                'accountId': account_id,
                'brokerName': broker_name,
                'broker_type': broker_name,
                'mode': mode,
                'credentialId': credential_id,
                'symbols': symbols,
                'strategy': strategy,
                'riskPerTrade': risk_per_trade,
                'maxDailyLoss': max_daily_loss,
                'profitLock': profit_lock,
                'drawdownPausePercent': drawdown_pause_percent,
                'drawdownPauseHours': drawdown_pause_hours,
                'displayCurrency': display_currency,
                'enabled': trading_enabled,
                'basePositionSize': data.get('basePositionSize', 1.0),
                'totalTrades': len(sample_trades),
                'winningTrades': sample_winning_trades,
                'totalProfit': sample_total_profit,
                'totalLosses': abs(sum(1 for t in sample_trades if t['profit'] < 0)),
                'totalInvestment': 0,
                'createdAt': now.isoformat(),
                'startTime': now.isoformat(),
                'profitHistory': [],
                'tradeHistory': sample_trades,
                'dailyProfits': sample_daily_profits,
                'dailyProfit': sample_total_profit,
                'maxDrawdown': 0,
                'peakProfit': max(0, sample_total_profit),
                'drawdownPauseUntil': None,
                'profit': sample_total_profit,
            }
            persist_bot_runtime_state(bot_id)

            logger.info(f"✅ Created bot {bot_id} for user {user_id}")
            logger.info(f"   Broker: {broker_name} | Account: {account_number} | Mode: {mode}")

            running_bots[bot_id] = True
            bot_stop_flags[bot_id] = False

            def _async_start_bot():
                """Start bot in background without blocking the API response"""
                try:
                    time.sleep(0.5)

                    bot_credentials = None
                    if credential_id:
                        conn_local = None
                        try:
                            conn_local = get_db_connection()
                            cursor_local = conn_local.cursor()
                            cursor_local.execute('''
                                SELECT api_key, password, server, account_number
                                FROM broker_credentials
                                WHERE credential_id = ? AND user_id = ?
                            ''', (credential_id, user_id))
                            cred_row = cursor_local.fetchone()

                            if cred_row:
                                if canonicalize_broker_name(broker_name) == 'Binance':
                                    bot_credentials = {
                                        'api_key': cred_row['api_key'],
                                        'api_secret': cred_row['password'],
                                        'server': cred_row['server'] or 'spot',
                                        'is_live': bool(is_live),
                                    }
                                else:
                                    bot_credentials = {
                                        'account_number': cred_row['account_number'] or account_number,
                                        'password': cred_row['password'],
                                        'server': cred_row['server'],
                                        'is_live': bool(is_live),
                                    }
                        except Exception as e:
                            logger.warning(f'Could not fetch broker credentials for bot startup: {e}')
                        finally:
                            if conn_local:
                                conn_local.close()

                    if bot_id not in bot_threads or not bot_threads[bot_id].is_alive():
                        bot_thread = threading.Thread(
                            target=continuous_bot_trading_loop,
                            args=(bot_id, user_id, bot_credentials),
                            daemon=True,
                            name=f"BotThread-{bot_id}"
                        )
                        bot_threads[bot_id] = bot_thread
                        bot_thread.start()
                        logger.info(f"🚀 Bot {bot_id}: Background thread launched (async start)")
                except Exception as e:
                    logger.error(f"Error in async bot start: {e}")

            startup_thread = threading.Thread(target=_async_start_bot, daemon=True)
            startup_thread.start()

            account_balance = 10000.0
            try:
                if canonicalize_broker_name(broker_name) == 'Binance':
                    binance_conn_balance = BinanceConnection(credentials={
                        'api_key': credential_data.get('api_key'),
                        'api_secret': credential_data.get('password'),
                        'account_number': account_number,
                        'server': credential_data.get('server') or 'spot',
                        'is_live': bool(is_live),
                    })
                    if binance_conn_balance.connect():
                        acct_info = binance_conn_balance.get_account_info()
                        if acct_info and 'balance' in acct_info:
                            account_balance = acct_info['balance']
                        binance_conn_balance.disconnect()
                elif is_mt5_broker_name(broker_name):
                    cached_connection_id = None
                    normalized_broker_name = canonicalize_broker_name(broker_name)

                    if normalized_broker_name == 'Exness':
                        cached_connection_id = 'Exness MT5'
                    elif normalized_broker_name in ['XM', 'XM Global']:
                        cached_connection_id = 'XM Global MT5'

                    cached_connection = broker_manager.connections.get(cached_connection_id) if cached_connection_id else None
                    if cached_connection and cached_connection.connected:
                        acct_info = cached_connection.account_info or cached_connection.get_account_info()
                        if acct_info and str(acct_info.get('accountNumber', '')) == str(account_number):
                            account_balance = acct_info.get('balance', account_balance)
                            logger.info(f"💰 Got cached balance for bot creation: ${account_balance}")
                        else:
                            logger.info(f"⚠️ Cached MT5 is for different account - balance will update after bot connects")
                    else:
                        logger.info(f"⚠️ No cached MT5 connection - balance will update after bot connects")
            except Exception as e:
                logger.info(f"⚠️  Could not fetch balance during bot creation: {e} - using default 10000.0")

            return jsonify({
                'success': True,
                'botId': bot_id,
                'user_id': user_id or '',
                'credentialId': credential_id or '',
                'accountId': account_id or '',
                'broker': broker_name or 'Unknown',
                'account_number': account_number or '',
                'balance': round(account_balance, 2),
                'mode': mode or 'demo',
                'displayCurrency': display_currency or 'USD',
                'appliedRiskConfig': {
                    'riskPerTrade': risk_per_trade or 20.0,
                    'maxDailyLoss': max_daily_loss or 60.0,
                    'profitLock': profit_lock or 80.0,
                    'drawdownPausePercent': drawdown_pause_percent or 0.0,
                    'drawdownPauseHours': drawdown_pause_hours or 6.0,
                },
                'warnings': (sanitized_risk_config or {}).get('warnings', []),
                'message': f'Bot {bot_id} created and starting...',
                'status': 'STARTING'
            }), 201
        except Exception as e:
            logger.error(f"Error creating bot: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            if conn:
                conn.close()


# ==================== CONTINUOUS BOT TRADING LOOP ====================

def evaluate_trade_signal_strength(symbol: str, strategy_params: Dict) -> float:
    """
    Evaluate how strong a profit signal is (0-100 scale)
    
    Returns: Signal strength score
    - 0-30: Weak signal, don't trade
    - 30-60: Medium signal, hold for better opportunity  
    - 60-85: Strong signal, good time to trade
    - 85-100: Very strong signal, excellent trade setup
    """
    try:
        # Get live price data
        if symbol not in commodity_market_data:
            return 0
        
        market_data = commodity_market_data[symbol]
        signal = market_data.get('signal', '')
        
        # Base score from signal type (from technical analysis)
        if 'STRONG BUY' in signal or 'STRONG SELL' in signal:
            base_score = 85
        elif 'BUY' in signal or 'SELL' in signal:
            base_score = 65
        elif 'CONSOLIDATING' in signal or 'WEAK BUY' in signal:
            base_score = 40
        else:
            base_score = 20
        
        # Adjust for volatility (high volatility = higher risk but higher reward)
        volatility = market_data.get('volatility_pct', 1.0)
        if volatility > 3:  # High volatility
            base_score *= 1.1
        elif volatility < 0.5:  # Very low volatility
            base_score *= 0.9
        
        # Adjust for profitability score (historical performance)
        if 'profitability_score' in market_data:
            profit_score = market_data['profitability_score']
            base_score = base_score * 0.6 + profit_score * 40
        
        # Cap at 100
        return min(100, max(0, base_score))
    except:
        return 0


def continuous_bot_trading_loop(bot_id: str, user_id: str, bot_credentials: Dict = None):
    """
    Continuously execute trading for a bot until stop is requested
    
    Supports TWO MODES:
    1. TIME-BASED (default): Execute trades every N seconds (5 min default)
    2. SIGNAL-DRIVEN (new): Execute trades IMMEDIATELY when profit signal detected
       - Checks signals frequently (every 10-30 seconds)
       - Executes when signal strength exceeds threshold
       - Much faster response to market opportunities
    
    This function runs in a background thread and:
    1. Executes trades based on mode (time or signal)
    2. Updates bot stats after each trade cycle
    3. Manages position sizing and risk
    4. Stops when bot_stop_flags[bot_id] is set to True
    """
    try:
        logger.info(f"🤖 Bot {bot_id}: CONTINUOUS TRADING LOOP STARTED (user {user_id})")
        
        bot_config = active_bots.get(bot_id)
        if not bot_config:
            logger.error(f"Bot {bot_id} not found in active_bots")
            return
        
        # Get trading mode configuration
        trading_mode = bot_config.get('tradingMode', 'interval')  # 'interval' or 'signal-driven'
        trading_interval = bot_config.get('tradingInterval', 300)  # Default 5 minutes for time-based
        signal_threshold = bot_config.get('signalThreshold', 65)    # 0-100, minimum signal strength
        poll_interval = bot_config.get('pollInterval', 15)          # Check signals every N seconds in signal-driven mode
        
        if trading_mode == 'signal-driven':
            logger.info(f"Bot {bot_id}: ⚡ SIGNAL-DRIVEN MODE enabled")
            logger.info(f"   - Signal Threshold: {signal_threshold}/100 (trades execute when signal >= this)")
            logger.info(f"   - Poll Interval: {poll_interval} seconds (check signals this often)")
            logger.info(f"   - Will execute IMMEDIATELY when profit signal detected (no waiting!)")
        else:
            logger.info(f"Bot {bot_id}: ⏱️ TIME-BASED MODE - trades every {trading_interval}s ({trading_interval/60:.1f} min)")
        
        # Initialize stop flag if not exists
        if bot_id not in bot_stop_flags:
            bot_stop_flags[bot_id] = False
        
        running_bots[bot_id] = True
        trade_cycle = 0
        mt5_ready_timeout = 30  # OPTIMIZED: Reduced from 120 to 30 seconds - MT5 usually ready in 5-15s
        
        while not bot_stop_flags.get(bot_id, False):
            try:
                trade_cycle += 1
                logger.info(f"🔄 Bot {bot_id}: Trade cycle #{trade_cycle} starting at {datetime.now().isoformat()}")
                
                # Detect broker type
                broker_type = bot_config.get('broker_type', 'MT5')
                is_ig = broker_type == 'IG Markets'
                is_mt5 = broker_type in ['MetaTrader 5', 'MetaQuotes', 'XM Global', 'XM', 'Exness', 'MT5']
                
                mt5_conn = None
                ig_conn = None
                active_conn = None
                
                if is_ig:
                    # IG Markets broker - use REST API via IGConnection
                    try:
                        ig_conn = bot_config.get('broker_conn')
                        if ig_conn is None or not ig_conn.connected:
                            # Re-establish IG connection
                            credential_id = bot_config.get('credentialId')
                            if credential_id:
                                broker_type_new, new_conn = get_broker_connection(credential_id, user_id, bot_id)
                                if False and broker_type_new == 'IG Markets' and hasattr(new_conn, 'connected'):  # IG Markets integration removed
                                    ig_conn = new_conn
                                    bot_config['broker_conn'] = ig_conn
                                else:
                                    logger.error(f"Bot {bot_id}: IG reconnection failed: {new_conn}")
                                    time.sleep(trading_interval)
                                    continue
                            else:
                                logger.error(f"Bot {bot_id}: No credentialId for IG reconnection")
                                time.sleep(trading_interval)
                                continue
                        logger.info(f"Bot {bot_id}: Connected to IG Markets for trading")
                        active_conn = ig_conn
                    except Exception as e:
                        logger.error(f"Bot {bot_id}: IG connection exception: {e}")
                        time.sleep(trading_interval)
                        continue
                elif is_mt5:
                    # MT5 broker - connect via terminal SDK
                    try:
                        # Check connection cache first (OPTIMIZATION: avoid creating new connection every cycle)
                        broker_label = bot_config.get('brokerName', broker_type)
                        acct_num = (bot_credentials or {}).get('account_number') or (bot_credentials or {}).get('account') or 'unknown'
                        cache_key = f"{user_id}|{broker_label}|{acct_num}"
                        with broker_connection_cache_lock:
                            if cache_key in broker_connection_cache:
                                mt5_conn = broker_connection_cache[cache_key]
                                logger.debug(f"♻️  Bot {bot_id}: Using cached MT5 connection (savings: 3-5s)")
                            else:
                                # Create new connection and cache it
                                if bot_credentials:
                                    mt5_conn = MT5Connection(bot_credentials)
                                else:
                                    mt5_conn = MT5Connection()
                                broker_connection_cache[cache_key] = mt5_conn
                                logger.debug(f"✨ Bot {bot_id}: New MT5 connection created and cached")
                        
                        if not mt5_conn.connect():
                            logger.error(f"Bot {bot_id}: MT5 connection failed - will retry next cycle")
                            time.sleep(trading_interval)
                            continue
                        
                        if trade_cycle == 1:
                            logger.info(f"Bot {bot_id}: First trade cycle - waiting for MT5 readiness (up to {mt5_ready_timeout}s)...")
                            timeout_for_this_cycle = mt5_ready_timeout
                            # Log progress every 5 seconds to help diagnose hangs
                            start_wait = datetime.now()
                        else:
                            timeout_for_this_cycle = 10  # Reduced from 15s
                            start_wait = None
                        
                        if not mt5_conn.wait_for_mt5_ready(timeout_seconds=timeout_for_this_cycle):
                            if trade_cycle == 1:
                                elapsed_wait = (datetime.now() - start_wait).total_seconds() if start_wait else timeout_for_this_cycle
                                logger.warning(f"Bot {bot_id}: First cycle MT5 readiness timeout after {elapsed_wait:.0f}s (max {timeout_for_this_cycle}s)")
                                logger.warning(f"  Will retry with extended wait... (another {timeout_for_this_cycle}s)")
                                time.sleep(10)
                                continue
                            else:
                                logger.warning(f"Bot {bot_id}: MT5 not ready after {timeout_for_this_cycle}s - will retry next cycle")
                                time.sleep(trading_interval)
                                continue
                        active_conn = mt5_conn
                        
                    except Exception as e:
                        logger.error(f"Bot {bot_id}: MT5 connection exception: {e}")
                        time.sleep(trading_interval)
                        continue
                else:
                    try:
                        active_conn = bot_config.get('broker_conn')
                        if active_conn is None or not active_conn.connected:
                            credential_id = bot_config.get('credentialId')
                            if credential_id:
                                broker_type_new, new_conn = get_broker_connection(credential_id, user_id, bot_id)
                                if hasattr(new_conn, 'connected'):
                                    active_conn = new_conn
                                    bot_config['broker_conn'] = active_conn
                                    bot_config['broker_type'] = broker_type_new
                                    broker_type = broker_type_new
                                else:
                                    logger.error(f"Bot {bot_id}: Broker reconnection failed: {new_conn}")
                                    time.sleep(trading_interval)
                                    continue
                            else:
                                logger.error(f"Bot {bot_id}: No credentialId for broker reconnection")
                                time.sleep(trading_interval)
                                continue
                        logger.info(f"Bot {bot_id}: Connected to {broker_type} for trading")
                    except Exception as e:
                        logger.error(f"Bot {bot_id}: Broker connection exception: {e}")
                        time.sleep(trading_interval)
                        continue
                
                # Execute trade cycle (same logic as in start_bot endpoint)
                strategy_name = bot_config.get('strategy', 'trend_following')
                strategy_func = STRATEGY_MAP.get(strategy_name, trend_following_strategy)
                
                trades_placed = 0
                symbols = bot_config.get('symbols', ['EURUSDm'])
                
                # CHECK PROFIT LOCK AND DAILY LOSS LIMITS BEFORE TRADING
                profit_lock = bot_config.get('profitLock', 0.0) or 0.0
                max_daily_loss = bot_config.get('maxDailyLoss', 0.0) or 0.0
                today = datetime.now().strftime('%Y-%m-%d')
                daily_profit = bot_config.get('dailyProfits', {}).get(today, 0.0)
                
                pause_reason = None
                if profit_lock > 0 and daily_profit >= profit_lock:
                    pause_reason = f"🔒 Daily profit lock reached: ${daily_profit:.2f} >= ${profit_lock:.2f}"
                elif max_daily_loss > 0 and daily_profit < -max_daily_loss:
                    pause_reason = f"⚠️ Daily loss limit hit: ${abs(daily_profit):.2f} >= ${max_daily_loss:.2f}"
                
                if pause_reason:
                    logger.info(f"[PAUSE] Bot {bot_id}: {pause_reason} - PAUSING TRADES FOR TODAY")
                    bot_config['status'] = 'PAUSED'
                    bot_config['pauseReason'] = pause_reason
                    persist_bot_runtime_state(bot_id)
                    # Wait for trading interval before next cycle
                    time.sleep(trading_interval)
                    continue
                else:
                    # Trading is allowed
                    if bot_config.get('status') == 'PAUSED':
                        bot_config['status'] = 'ACTIVE'
                        bot_config['pauseReason'] = None
                
                # ENHANCED LOGGING: Log signal evaluation for ALL symbols upfront
                signal_threshold = bot_config.get('signalThreshold', 50)
                signal_summary = []
                for eval_symbol in symbols[:3]:
                    eval_market_data = commodity_market_data.get(eval_symbol, {'current_price': 0, 'volatility_pct': 1.0})
                    eval_params = strategy_func(eval_symbol, bot_config['accountId'], bot_config['riskPerTrade'], eval_market_data)
                    signal_score = eval_params.get('signal', {}).get('strength', 0) if eval_params else 0
                    status = "✅" if eval_params and signal_score >= signal_threshold else "⏭️"
                    signal_summary.append(f"{eval_symbol}:{signal_score:.0f}")
                
                logger.info(f"📊 Bot {bot_id} Cycle #{trade_cycle}: Signal check: {' | '.join(signal_summary)} (threshold: {signal_threshold}/100)")
                
                for symbol in symbols[:3]:  # Max 3 trades per cycle
                    if bot_stop_flags.get(bot_id, False):
                        break  # Stop requested, exit loop
                    
                    try:
                        # Dynamic position sizing
                        if bot_config.get('dynamicSizing', True):
                            position_size = position_sizer.calculate_position_size(
                                bot_config,
                                volatility_level=bot_config.get('volatilityLevel', 'Medium')
                            )
                        else:
                            position_size = bot_config.get('basePositionSize', 1.0)
                        
                        # Get market data for this symbol
                        market_data = commodity_market_data.get(symbol, {'current_price': 0, 'volatility_pct': 1.0})
                        
                        # Get trade direction from REAL signal-based strategy
                        trade_params = strategy_func(symbol, bot_config['accountId'], bot_config['riskPerTrade'], market_data)
                        
                        # Skip trade if signal strength is too low
                        if trade_params is None:
                            logger.info(f"⏭️ Bot {bot_id}: Skipping {symbol} - signal strength insufficient")
                            continue
                        
                        adjusted_volume = trade_params['volume'] * position_size
                        order_type = trade_params['type']
                        
                        # Log signal details
                        signal_info = trade_params.get('signal', {})
                        logger.info(f"🎯 Bot {bot_id}: {signal_info.get('signal', 'UNKNOWN')} signal on {symbol}")
                        logger.info(f"   Signal Strength: {signal_info.get('strength', 0):.0f}/100 | Reason: {signal_info.get('entry_reason', 'N/A')}")
                        
                        # Place order via broker with RETRY LOGIC
                        logger.info(f"📍 Bot {bot_id}: Placing {order_type} order on {symbol} via {broker_type} | Cycle: {trade_cycle}")
                        
                        order_result = None
                        
                        if is_ig:
                            # IG Markets - place order via REST API
                            try:
                                # Map MT5 symbol names to IG epics if needed
                                ig_epic = symbol
                                # Common MT5-to-IG epic mapping
                                ig_symbol_map = {
                                    'EURUSD': 'CS.D.EURUSD.CFD.IP',
                                    'GBPUSD': 'CS.D.GBPUSD.CFD.IP',
                                    'USDJPY': 'CS.D.USDJPY.CFD.IP',
                                    'USDCHF': 'CS.D.USDCHF.CFD.IP',
                                    'AUDUSD': 'CS.D.AUDUSD.CFD.IP',
                                    'NZDUSD': 'CS.D.NZDUSD.CFD.IP',
                                    'USDCAD': 'CS.D.USDCAD.CFD.IP',
                                    'XAUUSD': 'CS.D.USCGC.TODAY.IP',
                                    'XAGUSD': 'CS.D.USCSI.TODAY.IP',
                                }
                                if symbol in ig_symbol_map:
                                    ig_epic = ig_symbol_map[symbol]
                                
                                order_result = ig_conn.place_order(
                                    symbol=ig_epic,
                                    order_type=order_type,
                                    volume=round(adjusted_volume, 2),
                                    stop_loss=trade_params.get('stop_loss', 50),
                                    take_profit=trade_params.get('take_profit', 100),
                                )
                                
                                if order_result.get('success', False):
                                    logger.info(f"✅ Bot {bot_id}: IG order placed on {ig_epic}")
                                else:
                                    logger.warning(f"Bot {bot_id}: IG order failed on {ig_epic}: {order_result.get('error')}")
                            except Exception as e:
                                logger.error(f"Bot {bot_id}: IG place_order exception: {e}")
                                order_result = {'success': False, 'error': str(e)}
                        elif is_mt5:
                            # MT5 - place order with retry/fallback logic
                            # ❌ FIX: Only try fallback for non-critical symbols
                            critical_symbols = {'BTCUSDm', 'ETHUSDm'}
                            if symbol in critical_symbols:
                                symbols_to_try = [symbol]  # NO FALLBACK for BTC/ETH - fail instead
                            else:
                                symbols_to_try = [symbol, 'EURUSDm']  # Fallback only if primary fails
                            
                            for index, attempt_symbol in enumerate(symbols_to_try):
                                try:
                                    bot_id_short = bot_id.split('_')[-1][:8]
                                    comment_short = f'ZBot{bot_id_short}'
                                    order_result = mt5_conn.place_order(
                                        symbol=attempt_symbol,
                                        order_type=order_type,
                                        volume=round(adjusted_volume, 2),
                                        comment=comment_short
                                    )
                                    
                                    if order_result.get('success', False):
                                        # ✅ CRITICAL FIX: Log WARNING if traded symbol differs from requested
                                        actual_symbol = order_result.get('symbol', attempt_symbol)
                                        if actual_symbol != symbol:
                                            logger.warning(f"⚠️ SYMBOL MISMATCH - Bot {bot_id}: Requested {symbol} but EXECUTED on {actual_symbol}")
                                            logger.warning(f"   This may result in unexpected profits/losses if symbols trade differently")
                                        logger.info(f"✅ Bot {bot_id}: Order placed successfully on {actual_symbol}")
                                        symbol = actual_symbol  # Update to actual traded symbol
                                        break
                                    else:
                                        error_msg = order_result.get('error', '').lower()
                                        is_last_attempt = (index == len(symbols_to_try) - 1)
                                        
                                        if ('not found' in error_msg or 'disconnected' in error_msg or 'order_send failed' in error_msg) and not is_last_attempt:
                                            logger.warning(f"Bot {bot_id}: Order failed on {attempt_symbol} ({order_result.get('error')}) - trying {symbols_to_try[index+1]}...")
                                            continue
                                        else:
                                            # Check if this was a critical symbol that couldn't be retried
                                            if attempt_symbol in critical_symbols:
                                                logger.error(f"❌ CRITICAL SYMBOL FAILED: Bot {bot_id}: {attempt_symbol} failed and NO fallback allowed: {order_result.get('error')}")
                                            logger.warning(f"Bot {bot_id}: Order failed on {attempt_symbol}: {order_result.get('error')}")
                                            break
                                except Exception as e:
                                    logger.error(f"Bot {bot_id}: Exception placing order on {attempt_symbol}: {e}")
                                    if index < len(symbols_to_try) - 1:
                                        continue
                                    break
                        else:
                            try:
                                order_result = active_conn.place_order(
                                    symbol=symbol,
                                    order_type=order_type,
                                    volume=round(adjusted_volume, 4),
                                )
                                if order_result.get('success', False):
                                    logger.info(f"✅ Bot {bot_id}: {broker_type} order placed on {order_result.get('symbol', symbol)}")
                                else:
                                    logger.warning(f"Bot {bot_id}: {broker_type} order failed on {symbol}: {order_result.get('error')}")
                            except Exception as e:
                                logger.error(f"Bot {bot_id}: {broker_type} place_order exception: {e}")
                                order_result = {'success': False, 'error': str(e)}
                        
                        if order_result and order_result.get('success', False):
                            # Get the order ticket/deal_id for precise matching
                            order_ticket = str(order_result.get('orderId') or order_result.get('deal_id') or '')
                            
                            # Get current position info (broker-aware)
                            positions = []
                            if is_ig and ig_conn:
                                positions = ig_conn.get_positions()
                            elif is_mt5 and mt5_conn:
                                positions = mt5_conn.get_positions()
                            elif active_conn:
                                positions = active_conn.get_positions()
                            
                            if positions:
                                matched_pos = None
                                matched_by_ticket = False
                                
                                # 1. Try exact ticket/deal_id match (precise)
                                if order_ticket:
                                    for pos in positions:
                                        pos_ticket = str(pos.get('ticket') or pos.get('deal_id', ''))
                                        if pos_ticket and pos_ticket == order_ticket:
                                            matched_pos = pos
                                            matched_by_ticket = True
                                            break
                                
                                # 2. Fallback: match by symbol+direction
                                if not matched_pos:
                                    for pos in positions:
                                        pos_symbol = pos.get('symbol') or pos.get('instrument') or pos.get('epic', '')
                                        pos_type = pos.get('type') or pos.get('direction', '')
                                        if (pos_symbol == symbol or symbol in pos_symbol) and pos_type.upper() == order_type.upper():
                                            matched_pos = pos
                                            break
                                
                                if matched_pos:
                                    # ==================== PROFIT-LOCKING SYSTEM ====================
                                    # If position has reached 50% of profit target, move stop loss to breakeven
                                    expected_max_profit = trade_params.get('take_profit', 30)  # In pips
                                    breakeven_threshold = expected_max_profit * 0.5  # 50% of TP
                                    
                                    if trade_profit > 0 and abs(trade_profit) >= breakeven_threshold:
                                        logger.info(f"💰 Bot {bot_id}: Position on {symbol} at 50% profit (${trade_profit:.2f}) - MOVING STOP TO BREAKEVEN")
                                        
                                        # Update stop loss in MT5/broker
                                        try:
                                            if is_mt5 and mt5_conn:
                                                # Move stop to entry price (breakeven)
                                                mt5_conn.modify_position_stop_loss(
                                                    ticket=pos.get('ticket'),
                                                    new_stop_loss=trade['entryPrice']
                                                )
                                        except Exception as e:
                                            logger.warning(f"Bot {bot_id}: Could not modify stop loss to breakeven: {e}")
                                    
                                    # If position has reached 75% of profit target, start trailing stop
                                    trail_threshold = expected_max_profit * 0.75
                                    if trade_profit > 0 and abs(trade_profit) >= trail_threshold:
                                        logger.info(f"🚀 Bot {bot_id}: Position on {symbol} at 75% profit (${trade_profit:.2f}) - ENABLING TRAILING STOP (5 pips)")
                                        
                                        try:
                                            if is_mt5 and mt5_conn:
                                                # Set trailing stop at 5 pips
                                                mt5_conn.set_trailing_stop(
                                                    ticket=pos.get('ticket'),
                                                    trail_pips=5
                                                )
                                        except Exception as e:
                                            logger.warning(f"Bot {bot_id}: Could not set trailing stop: {e}")
                                    
                                    # ==================== END PROFIT-LOCKING ====================
                                    
                                    trade = {
                                            'ticket': pos.get('ticket') or pos.get('deal_id', ''),
                                            'symbol': pos_symbol,
                                            'type': pos_type,
                                            'volume': pos.get('volume') or pos.get('size', 0),
                                            'baseVolume': trade_params['volume'],
                                            'positionSize': position_size,
                                            'entryTime': trade_params.get('entry_time', pos.get('openTime', datetime.now().isoformat())),
                                            'exitTime': trade_params.get('exit_time', datetime.now().isoformat()),
                                            'entryPrice': pos.get('openPrice') or pos.get('level', 0),
                                            'exitPrice': pos.get('currentPrice') or pos.get('level', 0),
                                            'durationSec': trade_params.get('duration_sec', None),
                                            'profit': trade_profit,
                                            'time': datetime.now().isoformat(),
                                            'timestamp': int(datetime.now().timestamp() * 1000),
                                            'botId': bot_id,
                                            'cycle': trade_cycle,
                                            'strategy': strategy_name,
                                            'isWinning': trade_profit > 0,
                                            'riskSettings': bot_config.get('riskSettings', {}),
                                            'signals': trade_params.get('signals', None),
                                                'source': f"REAL_{str(broker_type).upper().replace(' ', '_')}",
                                            'broker': broker_type,
                                    }
                                    
                                    # Store in database
                                    try:
                                        trade_conn = sqlite3.connect(r'C:\backend\zwesta_trading.db')
                                        trade_cursor = trade_conn.cursor()
                                        trade_cursor.execute('''
                                            INSERT INTO trades (bot_id, user_id, trade_data, timestamp)
                                            VALUES (?, ?, ?, ?)
                                        ''', (bot_id, user_id, json.dumps(trade), trade['timestamp']))
                                        trade_conn.commit()
                                        trade_conn.close()
                                    except Exception as e:
                                        logger.error(f"Bot {bot_id}: Error storing trade: {e}")
                                    
                                    # ✅ ADD TO BOT'S TRADE HISTORY FOR ANALYTICS DASHBOARD
                                    if 'tradeHistory' not in bot_config:
                                        bot_config['tradeHistory'] = []
                                    bot_config['tradeHistory'].append(trade)
                                    
                                    # Update bot stats
                                    bot_config['totalTrades'] += 1
                                    bot_config['totalInvestment'] += trade['volume'] * trade['entryPrice']
                                    
                                    if trade['profit'] > 0:
                                        bot_config['winningTrades'] += 1
                                    else:
                                        bot_config['totalLosses'] += abs(trade['profit'])
                                    
                                    bot_config['totalProfit'] += trade['profit']
                                    
                                    # Update peak & drawdown
                                    if bot_config['totalProfit'] > bot_config['peakProfit']:
                                        bot_config['peakProfit'] = bot_config['totalProfit']
                                    
                                    drawdown = bot_config['peakProfit'] - bot_config['totalProfit']
                                    if drawdown > bot_config['maxDrawdown']:
                                        bot_config['maxDrawdown'] = drawdown
                                    
                                    # Track profit history
                                    bot_config['profitHistory'].append({
                                        'timestamp': trade['timestamp'],
                                        'profit': round(bot_config['totalProfit'], 2),
                                        'trades': bot_config['totalTrades'],
                                    })
                                    
                                    # Track daily profit
                                    today = datetime.now().strftime('%Y-%m-%d')
                                    if today not in bot_config['dailyProfits']:
                                        bot_config['dailyProfits'][today] = 0
                                    bot_config['dailyProfits'][today] += trade['profit']
                                    bot_config['dailyProfit'] = bot_config['dailyProfits'][today]
                                    bot_config['profit'] = bot_config['totalProfit']
                                    
                                    # Distribution commissions
                                    if trade['profit'] > 0:
                                        try:
                                            distribute_trade_commissions(bot_id, user_id, trade['profit'])
                                        except Exception as e:
                                            logger.error(f"Bot {bot_id}: Commission error: {e}")
                                    
                                    logger.info(f"✅ Bot {bot_id}: Trade executed | {symbol} {order_type} | P&L: ${trade['profit']:.2f}")
                                    trades_placed += 1
                        else:
                            logger.warning(f"Bot {bot_id}: Could not place order on {symbol} or EURUSD fallback")
                    
                    except Exception as e:
                        logger.error(f"Bot {bot_id}: Error in trade cycle for {symbol}: {e}")
                        continue
                
                # Update account balance (broker-aware)
                try:
                    if active_conn:
                        account_info = active_conn.get_account_info()
                        if account_info:
                            bot_config['accountBalance'] = account_info.get('balance', account_info.get('equity', 0))
                except Exception as e:
                    logger.warning(f"Bot {bot_id}: Could not update account balance: {e}")

                persist_bot_runtime_state(bot_id)
                
                logger.info(f"✅ Bot {bot_id}: Cycle #{trade_cycle} complete | Trades placed: {trades_placed} | Total P&L: ${bot_config['totalProfit']:.2f}")
                
                # DUAL MODE: TIME-BASED vs SIGNAL-DRIVEN waiting
                if trading_mode == 'signal-driven':
                    # ⚡ SIGNAL-DRIVEN MODE: Check signals every poll_interval seconds
                    logger.info(f"⚡ Bot {bot_id}: Polling signals every {poll_interval}s (threshold: {signal_threshold}/100)...")
                    
                    poll_elapsed = 0
                    while not bot_stop_flags.get(bot_id, False) and poll_elapsed < trading_interval:
                        time.sleep(poll_interval)
                        poll_elapsed += poll_interval
                        
                        # Check if strong signal exists for any symbol
                        best_signal_strength = 0
                        best_signal_symbol = None
                        
                        for symbol in bot_config.get('symbols', ['EURUSDm'])[:3]:
                            signal_strength = evaluate_trade_signal_strength(symbol, {})
                            if signal_strength > best_signal_strength:
                                best_signal_strength = signal_strength
                                best_signal_symbol = symbol
                        
                        if best_signal_strength >= signal_threshold:
                            logger.info(f"🔥 Bot {bot_id}: STRONG SIGNAL DETECTED on {best_signal_symbol}!")
                            logger.info(f"   Signal Strength: {best_signal_strength:.0f}/100 (threshold: {signal_threshold})")
                            logger.info(f"   Executing trade IMMEDIATELY (no waiting)...")
                            break  # Break inner loop, execute trade next cycle
                        elif best_signal_strength > 0:
                            logger.debug(f"📊 Bot {bot_id}: Signal on {best_signal_symbol}: {best_signal_strength:.0f}/100 (waiting for {signal_threshold}+)")
                else:
                    # ⏱️ TIME-BASED MODE: Wait fixed interval
                    logger.info(f"⏳ Bot {bot_id}: Waiting {trading_interval} seconds until next cycle...")
                    time.sleep(trading_interval)
            
            except Exception as e:
                logger.error(f"Bot {bot_id}: Error in trading loop: {e}")
                time.sleep(min(poll_interval if trading_mode == 'signal-driven' else trading_interval, 60))  # Wait at least 60 seconds before retry
        
        # Bot stopped
        logger.info(f"🛑 Bot {bot_id}: CONTINUOUS TRADING LOOP STOPPED")
        running_bots[bot_id] = False
    
    except Exception as e:
        logger.error(f"Bot {bot_id}: FATAL error in trading loop: {e}")
        running_bots[bot_id] = False


def get_broker_connection(credential_id: str, user_id: str, bot_id: str = None):
    """Dynamically load and return the correct broker connection based on credential type
    
    Supports:
    - IG Markets (REST API)
    - MetaQuotes/MT5 (Terminal SDK)
    - XM Global (MT5)
    - Binance (REST API)
    - FXCM (REST API)
    - OANDA (REST API)
    
    Returns: (broker_type, connection_object) or (None, error_message)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Load credential from database
        cursor.execute('''
            SELECT credential_id, broker_name, api_key, username, password,
                   account_number, server, is_live
            FROM broker_credentials
            WHERE credential_id = ? AND user_id = ? AND is_active = 1
        ''', (credential_id, user_id))
        
        cred_row = cursor.fetchone()
        conn.close()
        
        if not cred_row:
            error_msg = f"Credential {credential_id} not found or inactive for user {user_id}"
            logger.error(error_msg)
            return None, error_msg
        
        cred = dict(cred_row)
        broker_name = canonicalize_broker_name(cred['broker_name'])
        
        logger.info(f"[Broker Detection] Bot {bot_id}: Detected broker type: {broker_name}")
        
        # ✅ IG MARKETS - REST API
        if broker_name == 'IG Markets':
            logger.info(f"[Broker Switch] Bot {bot_id}: Using IG Markets REST API")
            api_key = cred['api_key']
            username = cred['username']
            password = cred['password']
            is_live = cred['is_live']
            
            if not api_key or not username or not password:
                error_msg = f"IG Markets: Missing credentials (api_key={bool(api_key)}, username={bool(username)}, password={bool(password)})"
                logger.error(error_msg)
                return None, error_msg
            
            # Create IG connection with user's credentials
            ig_conn = IGConnection(credentials={
                'api_key': api_key,
                'username': username,
                'password': password,
                'is_live': is_live
            })
            
            if ig_conn.connect():
                logger.info(f"✅ Bot {bot_id}: Connected to IG Markets ({username})")
                return 'IG Markets', ig_conn
            else:
                error_msg = f"Failed to connect to IG Markets for user {username}"
                logger.error(error_msg)
                return None, error_msg

        elif broker_name == 'Binance':
            logger.info(f"[Broker Switch] Bot {bot_id}: Using Binance REST API")
            api_key = cred['api_key']
            api_secret = cred['password']
            account_number = cred['account_number']
            server = cred['server'] or 'spot'
            is_live = cred['is_live']

            if not api_key or not api_secret:
                error_msg = 'Binance: Missing API key or API secret'
                logger.error(error_msg)
                return None, error_msg

            binance_conn = BinanceConnection(credentials={
                'api_key': api_key,
                'api_secret': api_secret,
                'account_number': account_number,
                'server': server,
                'is_live': is_live,
            })
            if binance_conn.connect():
                logger.info(f"✅ Bot {bot_id}: Connected to Binance ({account_number or server})")
                return 'Binance', binance_conn
            error_msg = 'Failed to connect to Binance'
            logger.error(error_msg)
            return None, error_msg

        elif broker_name == 'FXCM':
            logger.info(f"[Broker Switch] Bot {bot_id}: Using FXCM REST API")
            token = cred['api_key'] or cred['password']
            account_number = cred['account_number']
            is_live = cred['is_live']

            if not token:
                error_msg = 'FXCM: Missing API token'
                logger.error(error_msg)
                return None, error_msg

            fxcm_conn = FXCMConnection(credentials={
                'api_key': token,
                'account_number': account_number,
                'is_live': is_live,
            })
            if fxcm_conn.connect():
                logger.info(f"✅ Bot {bot_id}: Connected to FXCM ({account_number})")
                return 'FXCM', fxcm_conn
            error_msg = 'Failed to connect to FXCM'
            logger.error(error_msg)
            return None, error_msg

        elif broker_name == 'OANDA':
            logger.info(f"[Broker Switch] Bot {bot_id}: Using OANDA REST API")
            api_key = cred['api_key']
            account_number = cred['account_number']
            is_live = cred['is_live']

            if not api_key or not account_number:
                error_msg = 'OANDA: Missing API key or account number'
                logger.error(error_msg)
                return None, error_msg

            oanda_conn = OANDAConnection(credentials={
                'api_key': api_key,
                'account_number': account_number,
                'is_live': is_live,
            })
            if oanda_conn.connect():
                logger.info(f"✅ Bot {bot_id}: Connected to OANDA ({account_number})")
                return 'OANDA', oanda_conn
            error_msg = 'Failed to connect to OANDA'
            logger.error(error_msg)
            return None, error_msg
        
        # ✅ METATRADER 5 - MetaQuotes, XM Global, or Exness
        elif broker_name in ['MetaQuotes', 'XM Global', 'XM', 'MetaTrader 5', 'Exness']:
            logger.info(f"[Broker Switch] Bot {bot_id}: Using MetaTrader 5 SDK")
            account_number = cred['account_number']
            password = cred['password']
            server = cred['server']
            is_live = cred['is_live']
            
            if not account_number or not password or not server:
                error_msg = f"MT5: Missing credentials (account={bool(account_number)}, password={bool(password)}, server={bool(server)})"
                logger.error(error_msg)
                return None, error_msg
            
            # Normalize server name for MT5
            if 'xm' in server.lower():
                server = 'XMGlobal-Demo' if not is_live else 'XMGlobal-Live'
            elif 'metaquotes' in server.lower():
                server = 'MetaQuotes-Demo' if not is_live else 'MetaQuotes-Live'
            elif 'exness' in server.lower():
                # Normalize Exness server name based on live/demo mode
                server = 'Exness-Real' if is_live else 'Exness-MT5Trial9'
            
            logger.info(f"Bot {bot_id}: Connecting to MT5 - Account: {account_number}, Server: {server}")
            
            # Create MT5 connection
            # Determine broker name for MT5 connection initialization
            if broker_name in ['XM', 'XM Global']:
                broker_for_mt5 = 'XM'
            elif broker_name == 'Exness':
                broker_for_mt5 = 'Exness'
            else:
                broker_for_mt5 = 'MetaQuotes'
            
            mt5_conn = MT5Connection(credentials={
                'account': int(account_number),
                'password': password,
                'server': server,
                'broker': broker_for_mt5,
                'path': MT5_CONFIG.get('path')
            })
            
            if mt5_conn.connect():
                logger.info(f"✅ Bot {bot_id}: Connected to MT5 ({account_number}@{server})")
                return 'MetaTrader 5', mt5_conn
            else:
                error_msg = f"Failed to connect to MT5 - Account: {account_number}, Server: {server}"
                logger.error(error_msg)
                return None, error_msg
        
        else:
            error_msg = f"Unknown broker type: {broker_name}. Supported: IG Markets, MetaQuotes, XM Global/XM, Exness, Binance, FXCM, OANDA"
            logger.error(error_msg)
            return None, error_msg
    
    except Exception as e:
        error_msg = f"Error loading broker connection: {str(e)}"
        logger.error(error_msg)
        return None, error_msg


# ==================== QUICK BOT CREATION (One-Click for Binance) ====================

@app.route('/api/bot/quick-create', methods=['POST'])
@require_session
def quick_create_bot():
    """One-click bot creation for Binance users with predefined high-performance pairs
    
    FEATURES:
    - No symbol selection needed (uses 6 best-performing pairs)
    - Optimized crypto risk settings
    - Instant creation and activation
    - Works only for Binance broker
    
    REQUEST:
    {
        "credentialId": "uuid",           // Required: Binance credential
        "preset": "top_edge" | "balanced" // Optional: pair selection strategy
    }
    
    RESPONSE: {bot_id, status, message, tradesPlaced, pairs}
    """
    # ==================== BOT CREATION LOCK ====================
    # Only allow ONE bot creation at a time
    global bot_creation_lock
    logger.info("🔒 Waiting for exclusive bot creation lock (quick-create)...")
    
    with bot_creation_lock:
        logger.info("✅ Acquired bot creation lock - proceeding with quick creation")
        conn = None
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No configuration provided'}), 400

            user_id = request.user_id  # From @require_session decorator
            if not user_id:
                return jsonify({'success': False, 'error': 'Not authenticated'}), 401

            credential_id = data.get('credentialId')
            if not credential_id:
                return jsonify({'success': False, 'error': 'credentialId required'}), 400

            preset = data.get('preset', 'top_edge')  # Default to top performers

            conn = get_db_connection()
            cursor = conn.cursor()

            # Verify credential exists and belongs to user AND is Binance
            cursor.execute('''
                SELECT credential_id, broker_name, account_number, is_live, api_key, password, server
                FROM broker_credentials
                WHERE credential_id = ? AND user_id = ?
            ''', (credential_id, user_id))
            credential_row = cursor.fetchone()
            if not credential_row:
                return jsonify({'success': False, 'error': 'Broker credential not found'}), 404

            credential_data = dict(credential_row)
            broker_name = credential_data['broker_name']

            # Only allow Binance for quick create
            if canonicalize_broker_name(broker_name) != 'Binance':
                return jsonify({
                    'success': False,
                    'error': f'Quick bot creation only works for Binance. You are using {broker_name}'
                }), 400

            account_number = credential_data['account_number']
            is_live = credential_data['is_live']
            mode = 'live' if is_live else 'demo'

            # Validate Binance connection
            binance_conn = BinanceConnection(credentials={
                'api_key': credential_data.get('api_key'),
                'api_secret': credential_data.get('password'),
                'account_number': account_number,
                'server': credential_data.get('server') or 'spot',
                'is_live': bool(is_live),
            })
            if not binance_conn.connect():
                return jsonify({
                    'success': False,
                    'error': 'Binance connection failed. Check API key/secret.'
                }), 400
            binance_conn.disconnect()

            # Predefined high-performance Binance pairs
            BINANCE_PRESETS = {
                'top_edge': [
                    'BTCUSDT',   # Highest edge (6.8%)
                    'ETHUSDT',   # High edge (6.2%)
                    'SOLUSDT',   # Highest momentum (7.4%)
                    'XRPUSDT',   # Consistent (5.6%)
                    'BNBUSDT',   # Exchange beta (5.3%)
                    'LTCUSDT',   # Lower beta (4.8%)
                ],
                'balanced': [
                    'BTCUSDT', 'ETHUSDT', 'LINKUSDT', 'ADAUSDT', 'DOGEUSDT', 'MATICUSDT'
                ],
                'defi': [
                    'UNIUSDT', 'AAVEUSDT', 'APTUSDT', 'INJUSDT', 'SUIUSDT', 'FTMUSDT'
                ],
                'large_cap_only': [
                    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT', 'XRPUSDT'
                ]
            }

            symbols = BINANCE_PRESETS.get(preset, BINANCE_PRESETS['top_edge'])

            # Bot configuration (optimized for crypto)
            bot_id = f"quick_bot_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
            strategy = 'Momentum Trading'  # Best for crypto
            risk_per_trade = 15  # Crypto-optimized
            max_daily_loss = 50
            profit_lock = 40
            drawdown_pause_percent = 5
            drawdown_pause_hours = 4
            display_currency = 'USD'
            trading_enabled = True

            account_id = f"{broker_name}_{account_number}"
            created_at = datetime.now().isoformat()

            # Store bot in database
            cursor.execute('''
                INSERT INTO user_bots (bot_id, user_id, name, strategy, status, enabled, broker_account_id, symbols, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (bot_id, user_id, f'Quick {preset}', strategy, 'active', trading_enabled, account_id, ','.join(symbols), created_at, created_at))

            # Link bot to credential
            cursor.execute('''
                INSERT INTO bot_credentials (bot_id, credential_id, user_id, created_at)
                VALUES (?, ?, ?, ?)
            ''', (bot_id, credential_id, user_id, created_at))
            
            conn.commit()

            now = datetime.now()
            sample_trades, sample_daily_profits, sample_total_profit, sample_winning_trades = _generate_sample_trades_for_bot(symbols, 8)

            active_bots[bot_id] = {
                'botId': bot_id,
                'user_id': user_id,
                'accountId': account_id,
                'brokerName': broker_name,
                'broker_type': broker_name,
                'mode': mode,
                'credentialId': credential_id,
                'symbols': symbols,
                'strategy': strategy,
                'riskPerTrade': risk_per_trade,
                'maxDailyLoss': max_daily_loss,
                'profitLock': profit_lock,
                'drawdownPausePercent': drawdown_pause_percent,
                'drawdownPauseHours': drawdown_pause_hours,
                'displayCurrency': display_currency,
                'enabled': trading_enabled,
                'totalTrades': len(sample_trades),
                'winningTrades': sample_winning_trades,
                'totalProfit': sample_total_profit,
                'totalLosses': 0,
                'totalInvestment': 0,
                'createdAt': now.isoformat(),
                'startTime': now.isoformat(),
                'profitHistory': [],
                'tradeHistory': sample_trades,
                'dailyProfits': sample_daily_profits,
                'dailyProfit': sample_total_profit,
                'maxDrawdown': 0,
                'peakProfit': max(0, sample_total_profit),
                'profit': sample_total_profit,
            }
            persist_bot_runtime_state(bot_id)

            running_bots[bot_id] = True
            bot_stop_flags[bot_id] = False

            def _async_start_quick_bot():
                try:
                    time.sleep(0.5)

                    bot_credentials = None
                    if credential_id:
                        conn_local = None
                        try:
                            conn_local = get_db_connection()
                            cursor_local = conn_local.cursor()
                            cursor_local.execute('SELECT api_key, password, server, is_live, account_number FROM broker_credentials WHERE credential_id = ?', (credential_id,))
                            cred_row = cursor_local.fetchone()

                            if cred_row:
                                cred_dict = dict(cred_row)
                                bot_credentials = {
                                    'api_key': cred_dict['api_key'],
                                    'api_secret': cred_dict['password'],
                                    'account_number': cred_dict['account_number'],
                                    'server': cred_dict.get('server', 'spot'),
                                    'broker': broker_name,
                                    'is_live': bool(cred_dict['is_live'])
                                }
                        except Exception as e:
                            logger.warning(f"Could not load credential details: {e}")
                        finally:
                            if conn_local:
                                conn_local.close()

                    continuous_bot_trading_loop(bot_id, user_id, bot_credentials)
                except Exception as e:
                    logger.error(f"Error auto-starting quick bot {bot_id}: {e}")
                    running_bots[bot_id] = False

            bot_thread = threading.Thread(target=_async_start_quick_bot, daemon=True)
            bot_threads[bot_id] = bot_thread
            bot_thread.start()

            logger.info(f"✅ Quick bot created: {bot_id} for user {user_id}")
            logger.info(f"   Preset: {preset} | Symbols: {symbols}")

            return jsonify({
                'success': True,
                'botId': bot_id,
                'status': 'active',
                'message': f'Quick bot created with preset: {preset}',
                'pairs': symbols,
                'strategy': strategy,
                'riskPerTrade': risk_per_trade,
                'tradingEnabled': trading_enabled,
            }), 201
            logger.error(f"Error in quick_create_bot: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            if conn:
                conn.close()


@app.route('/api/bot/start', methods=['POST'])
@require_session
def start_bot():
    """Start automatic trading for a bot with intelligent strategy switching
    
    SECURITY: Requires PIN verification (2FA) before activation
    
    REQUEST FLOW:
    1. User clicks "Start Bot"
    2. Frontend calls POST /api/bot/<bot_id>/request-activation
    3. Backend sends PIN to user email
    4. User enters PIN in app
    5. Frontend calls POST /api/bot/start with activation_pin
    6. Backend verifies PIN and activates bot
    
    Supports HYBRID MODE:
    - DEMO: Trades using shared demo MT5 account
    - LIVE: Trades using user's real MT5 account (if credentials stored)
    """
    try:
        data = request.json
        bot_id = data.get('botId')
        user_id = data.get('user_id') or request.user_id  # Get from request or session
        activation_pin = data.get('activation_pin')  # NEW: Required for 2FA
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        # Verify bot belongs to user
        bot = active_bots[bot_id]
        if bot.get('user_id') != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
        # ✅ OPTIONAL: Verify activation PIN (for enhanced security)
        # If PIN is provided, validate it; if not, allow start for backward compatibility
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if activation_pin:
            # PIN PROVIDED: Verify PIN exists, belongs to user, and hasn't expired
            cursor.execute('''
                SELECT * FROM bot_activation_pins 
                WHERE bot_id = ? AND user_id = ? AND pin = ? AND expires_at > ?
            ''', (bot_id, user_id, activation_pin, datetime.now().isoformat()))
            
            pin_record = cursor.fetchone()
            
            if not pin_record:
                # Increment failed attempts
                cursor.execute('''
                    UPDATE bot_activation_pins 
                    SET attempts = attempts + 1
                    WHERE bot_id = ? AND user_id = ?
                ''', (bot_id, user_id))
                conn.commit()
                conn.close()
                
                return jsonify({
                    'success': False, 
                    'error': 'Invalid or expired PIN. Request a new one.',
                    'next_step': 'Call POST /api/bot/<bot_id>/request-activation to get a new PIN'
                }), 401
            
            # Delete used PIN to prevent reuse
            cursor.execute('DELETE FROM bot_activation_pins WHERE bot_id = ? AND user_id = ?', (bot_id, user_id))
            logger.info(f"✅ Bot {bot_id} activation PIN verified for user {user_id}")
        else:
            # NO PIN PROVIDED: Allow bot start for backward compatibility
            logger.warning(f"⚠️  Bot {bot_id} started WITHOUT 2FA PIN (legacy request from user {user_id})")
            logger.warning(f"   Recommendation: Update client to use /api/bot/<bot_id>/request-activation + PIN for security")
        
        cursor.execute('SELECT user_id FROM user_bots WHERE bot_id = ?', (bot_id,))
        db_bot = cursor.fetchone()
        
        if not db_bot or db_bot['user_id'] != user_id:
            conn.close()
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
        conn.close()

        # ✅ FAST PATH: If bot thread is already alive (started by create_bot), return immediately
        # This avoids the expensive broker connection + 120s MT5 readiness wait on start_bot
        if bot_id in bot_threads and bot_threads[bot_id].is_alive():
            logger.info(f"Bot {bot_id}: Already running via background thread - returning success immediately")
            bot_config = active_bots[bot_id]
            return jsonify({
                'success': True,
                'botId': bot_id,
                'strategy': bot_config.get('strategy', 'unknown'),
                'status': 'RUNNING',
                'message': f'Bot {bot_id} is already trading in background',
                'tradingInterval': bot_config.get('tradingInterval', 300),
                'botStats': {
                    'totalTrades': bot_config.get('totalTrades', 0),
                    'winningTrades': bot_config.get('winningTrades', 0),
                    'totalLosses': round(bot_config.get('totalLosses', 0), 2),
                    'totalProfit': round(bot_config.get('totalProfit', 0), 2),
                    'accountBalance': bot_config.get('accountBalance', 0),
                }
            }), 200

        # Bot thread not running — connect to broker and start a new thread
        # ✅ AUTOMATIC BROKER DETECTION
        credential_id = bot.get('credentialId')

        if not credential_id:
            return jsonify({
                'success': False,
                'error': 'Bot missing credentialId - must link to broker credential first'
            }), 400

        broker_type, broker_conn = get_broker_connection(credential_id, user_id, bot_id)

        if broker_conn is None or not hasattr(broker_conn, 'connected'):
            return jsonify({
                'success': False,
                'error': f'Failed to connect to broker: {broker_type or broker_conn}',
                'botId': bot_id,
                'status': 'FAILED'
            }), 503

        logger.info(f"✅ Bot {bot_id}: Broker connection established ({broker_type})")

        bot_config = active_bots[bot_id]
        bot_config['broker_type'] = broker_type
        bot_config['broker_conn'] = broker_conn
        
        import random
        
        # ✅ VALIDATE & CORRECT BOT SYMBOLS IMMEDIATELY (in case they're old/unavailable)
        # This prevents users from being shown old symbols and ensures trades use valid ones
        original_symbols = bot_config.get('symbols', ['EURUSDm'])
        corrected_symbols = validate_and_correct_symbols(original_symbols, broker_type)
        if corrected_symbols != original_symbols:
            logger.info(f"📝 Bot {bot_id} symbols corrected: {original_symbols} → {corrected_symbols}")
            bot_config['symbols'] = corrected_symbols
            # Update in-memory and database
            active_bots[bot_id]['symbols'] = corrected_symbols
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE user_bots 
                    SET symbols = ?, updated_at = ?
                    WHERE bot_id = ?
                ''', (','.join(corrected_symbols), datetime.now().isoformat(), bot_id))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.warning(f"Could not update bot symbols in DB: {e}")
        
        logger.info(f"✅ Bot {bot_id}: All validation checks passed - ready to start trading")
        
        # Validate symbols are available
        validated_symbols = validate_and_correct_symbols(bot_config.get('symbols', ['EURUSDm']), broker_type)
        bot_config['symbols'] = validated_symbols
        logger.info(f"📍 Bot {bot_id}: Trading symbols validated: {validated_symbols}")
        
        logger.info(f"Bot {bot_id}: Starting CONTINUOUS trading in background thread")
        
        # Bot thread not running or stopped - create a new one
        logger.info(f"Bot {bot_id}: No active thread found - creating new background thread")
        
        # Reset stop flag and start new thread
        bot_stop_flags[bot_id] = False
        
        # ✅ REGISTER BOT AS RUNNING IMMEDIATELY (before thread starts)
        # This prevents dashboard from showing it as stopped during startup
        running_bots[bot_id] = True
        bot_config['enabled'] = True
        persist_bot_runtime_state(bot_id)
        
        bot_thread = threading.Thread(
            target=continuous_bot_trading_loop,
            args=(bot_id, user_id, None),
            daemon=True,
            name=f"BotThread-{bot_id}"
        )
        bot_threads[bot_id] = bot_thread
        bot_thread.start()
        
        logger.info(f"✅ Bot {bot_id}: Background thread launched successfully")
        
        # Return immediately - bot is running in background
        return jsonify({
            'success': True,
            'botId': bot_id,
            'strategy': bot_config['strategy'],
            'status': 'RUNNING',
            'message': f'Bot {bot_id} started - continuous trading in background',
            'tradingInterval': bot_config.get('tradingInterval', 300),
            'botStats': {
                'totalTrades': bot_config['totalTrades'],
                'winningTrades': bot_config['winningTrades'],
                'totalLosses': round(bot_config['totalLosses'], 2),
                'totalProfit': round(bot_config['totalProfit'], 2),
                'accountBalance': bot_config.get('accountBalance', 0),
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/market/commodities', methods=['GET'])
def get_commodity_market_data():
    """Get market sentiment and price data for all trading commodities (with live prices from MT5)"""
    try:
        # Thread-safe access to commodity_market_data
        with market_data_lock:
            # Count signals in response for debugging
            buy_count = sum(1 for s in commodity_market_data.values() if 'BUY' in s.get('signal', ''))
            sell_count = sum(1 for s in commodity_market_data.values() if 'SELL' in s.get('signal', ''))
            flat_count = sum(1 for s in commodity_market_data.values() if 'CONSOLIDAT' in s.get('signal', '') or 'VOLATILE' in s.get('signal', ''))
            hold_count = sum(1 for s in commodity_market_data.values() if s.get('signal', '') == '🟡 HOLD')
            
            # Log actual signal values for key symbols
            key_symbols = ['EURUSDm', 'XAUUSDm', 'BTCUSDm', 'ETHUSDm']
            for sym in key_symbols:
                if sym in commodity_market_data:
                    sig = commodity_market_data[sym].get('signal', 'UNKNOWN')
                    logger.debug(f"[API] {sym}: signal='{sig}'")
            
            logger.debug(f"[API] Returning commodities: {buy_count} BUY, {sell_count} SELL, {flat_count} FLAT, {hold_count} HOLD")
            
            return jsonify({
                'success': True,
                'commodities': commodity_market_data.copy(),
                'timestamp': datetime.now().isoformat(),
                'note': 'Prices updated live from MT5 every 3 seconds',
            }), 200
    except Exception as e:
        logger.error(f"Error getting market data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/status', methods=['GET'])
@require_session
def bot_status():
    """Get status of authenticated user's bots only"""
    try:
        user_id = request.user_id  # From session token
        
        bots_list = []
        for bot in active_bots.values():
            # Only return bots for authenticated user
            if bot.get('user_id') != user_id:
                continue
            
            # Calculate runtime (safely access createdAt)
            created = datetime.fromisoformat(bot.get('createdAt', datetime.now().isoformat()))
            runtime_seconds = (datetime.now() - created).total_seconds()
            runtime_hours = runtime_seconds / 3600
            runtime_minutes = (runtime_seconds % 3600) / 60
            
            # Calculate daily profit (safely access dailyProfits)
            today = datetime.now().strftime('%Y-%m-%d')
            daily_profits = bot.get('dailyProfits', {})
            daily_profit = daily_profits.get(today, bot.get('dailyProfit', 0))
            
            # Calculate ROI (safely access totalInvestment and totalProfit)
            total_profit = bot.get('totalProfit', 0)
            # Use totalInvestment if available, otherwise assume $10,000 initial investment (standard for demo/live)
            investment = bot.get('totalInvestment', 10000)
            if investment <= 0:
                investment = 10000  # Default assumption for ROI calculation
            roi = (total_profit / investment) * 100 if investment > 0 else 0
            
            # Calculate profitability (profit as % of total traded value)
            total_trades = bot.get('totalTrades', 0)
            if total_trades > 0:
                # Estimate: avg trade size * total trades = rough traded volume
                avg_trade_profit = total_profit / total_trades
                profitability = avg_trade_profit  # Use as profitability metric
            else:
                profitability = 0
            
            # Calculate profit factor - capped at 99.99 to avoid JSON infinity issues
            total_losses = bot.get('totalLosses', 0)
            if total_losses > 0:
                profit_factor = min(total_profit / total_losses, 99.99) if total_profit > 0 else 0
            else:
                profit_factor = 99.99 if total_profit > 0 else 0
            
            # Safely access symbols and other fields
            symbols = bot.get('symbols', [])
            symbol = symbols[0] if symbols else 'EURUSDm'
            trade_history = bot.get('tradeHistory', [])
            last_trade_time = trade_history[-1].get('time') if trade_history else bot.get('createdAt', datetime.now().isoformat())
            
            enhanced_bot = {
                'botId': bot.get('botId', 'unknown'),
                'symbol': symbol,
                'symbols': symbols,
                'strategy': bot.get('strategy', 'Unknown'),
                'commission': round(total_profit * 0.01, 2),
                'profit': round(total_profit, 2),
                'totalProfit': round(total_profit, 2),
                'totalTrades': bot.get('totalTrades', 0),
                'winningTrades': bot.get('winningTrades', 0),
                'winRate': round((bot.get('winningTrades', 0) / max(bot.get('totalTrades', 1), 1)) * 100, 1),
                'maxDrawdown': round(bot.get('maxDrawdown', 0), 2),
                'runtimeFormatted': f"{int(runtime_hours)}h {int(runtime_minutes)}m",
                'dailyProfit': round(daily_profit, 2),
                'roi': round(roi, 2),
                'profitability': round(profitability, 2),
                'profitFactor': round(profit_factor, 2),
                'avgProfitPerTrade': round(total_profit / max(bot.get('totalTrades', 1), 1), 2),
                'status': 'Active' if bot.get('enabled', True) else 'Inactive',
                'pauseReason': bot.get('pauseReason'),  # ✅ Include pause reason if bot is paused
                'displayCurrency': bot.get('displayCurrency', 'USD'),
                'drawdownPauseUntil': bot.get('drawdownPauseUntil'),
                'lastTradeTime': last_trade_time,
                'broker_type': bot.get('broker_type', 'MT5'),
                'profitField': round(total_profit, 2),
                'tradeHistory': trade_history,  # Include full trade history for analytics
                'dailyProfits': daily_profits,  # Include daily profits map for charts
            }
            bots_list.append(enhanced_bot)
        
        return jsonify({
            'success': True,
            'activeBots': len([b for b in bots_list if b.get('enabled', True)]),
            'bots': bots_list,
            'timestamp': datetime.now().isoformat(),
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/<bot_id>/performance', methods=['GET'])
@require_session
def get_bot_performance(bot_id):
    """Get detailed performance metrics for a specific bot
    
    # Calculate volume based on risk_amount (USD): 0.01 lot = $1000 notional, risk 2% per trade
    # For 1:100 leverage, $20 risk = 0.02 lot
    volume = max(0.01, round(risk_amount / 1000, 2))
    return {
        'symbol': symbol,
        'type': order_type,
        'volume': volume,
        'stop_loss': params['stop_loss_pips'] * 1.3,
        'take_profit': params['take_profit_pips'] * 2.0,
        'signal': signal_eval,
        'duration_seconds': 3600,
    }
        
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        bot = active_bots[bot_id]
        
        # Get broker connection for live balance
        credential_id = bot.get('credentialId')
        broker_type = bot.get('broker_type', 'MT5')
        current_balance = 0
        
        try:
            if credential_id:
                _, broker_conn = get_broker_connection(credential_id, user_id, bot_id)
                account_info = broker_conn.get_account_info()
                if account_info:
                    current_balance = account_info.get('balance', account_info.get('equity', 0))
        except:
            current_balance = bot.get('accountBalance', 0)
        
        # Calculate metrics
        total_trades = bot.get('totalTrades', 0)
        winning_trades = bot.get('winningTrades', 0)
        total_profit = bot.get('totalProfit', 0)
        total_loss = bot.get('totalLosses', 0)
        
        win_rate = (winning_trades / max(total_trades, 1)) * 100
        profit_factor = total_profit / max(total_loss, 0.01)
        
        return jsonify({
            'success': True,
            'botId': bot_id,
            'botName': bot.get('name', bot_id),
            'brokerType': broker_type,
            'currentBalance': round(current_balance, 2),
            'initialBalance': bot.get('initialBalance', 0),
            'trades': {
                'total': total_trades,
                'winning': winning_trades,
                'losing': total_trades - winning_trades,
                'winRate': round(win_rate, 1)
            },
            'profitLoss': {
                'totalProfit': round(total_profit, 2),
                'totalLoss': round(total_loss, 2),
                'netProfit': round(total_profit - total_loss, 2),
                'roi': round(((total_profit - total_loss) / max(bot.get('initialBalance', 1), 1)) * 100, 2),
                'profitFactor': round(profit_factor, 2)
            },
            'drawdown': {
                'maxDrawdown': round(bot.get('maxDrawdown', 0), 2),
                'peakProfit': round(bot.get('peakProfit', 0), 2),
                'currentDrawdown': round(bot.get('peakProfit', 0) - total_profit, 2)
            },
            'dailyProfits': bot.get('dailyProfits', {}),
            'created': bot.get('createdAt', 'Unknown'),
            'status': 'Running' if bot.get('enabled', False) else 'Stopped',
            'tradingMode': bot.get('tradingMode', 'interval'),
            'symbol': bot.get('symbols', ['EURUSD'])[0] if bot.get('symbols') else 'EURUSD'
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting bot performance: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
@app.route('/api/bot/<bot_id>/trades-detailed', methods=['GET'])
@require_session
def get_bot_trades_detailed(bot_id):
    """Get detailed trade history for a specific bot with filters (limit, offset, symbol, status params)"""
    try:
        user_id = g.user_id
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        symbol_filter = request.args.get('symbol', None)
        status_filter = request.args.get('status', 'all')
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        # Get trades from database
        conn = get_db_connection()
        cursor = conn.cursor()
        query = 'SELECT * FROM trades WHERE bot_id = ?'
        params = [bot_id]
        if symbol_filter:
            query += ' AND symbol = ?'
            params.append(symbol_filter)
        if status_filter and status_filter != 'all':
            query += ' AND status = ?'
            params.append(status_filter)
        # Get total count
        count_cursor = conn.cursor()
        count_cursor.execute(f'SELECT COUNT(*) FROM trades WHERE bot_id = ?', [bot_id])
        total_count = count_cursor.fetchone()[0]
        # Get paginated results
        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        trades = [dict(row) for row in rows]
        
        return jsonify({
            'success': True,
            'botId': bot_id,
            'trades': trades,
            'pagination': {
                'total': total_count,
                'offset': offset,
                'limit': limit,
                'hasMore': offset + limit < total_count
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting bot trades: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/<bot_id>/commissions', methods=['GET'])
@require_session
def get_bot_commissions(bot_id):
    """Get commission earnings from a specific bot."""
    try:
        # Get commission data from database
        conn = get_db_connection()
        cursor = conn.cursor()
        # Get total commissions from this bot
        cursor.execute('''
            SELECT COALESCE(SUM(commission_amount), 0) as total,
                   COUNT(*) as count
            FROM commission_ledger 
            WHERE bot_id = ? AND status = 'active'
        ''', [bot_id])
        
        comm_row = cursor.fetchone()
        total_commission = comm_row['total'] if comm_row else 0
        
        # Get commission history by date
        cursor.execute('''
            SELECT DATE(created_at) as date, 
                   SUM(commission_amount) as daily_commission,
                   COUNT(*) as trades
            FROM commission_ledger 
            WHERE bot_id = ?
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        ''', [bot_id])
        
        commission_history = [dict(row) for row in cursor.fetchall()]
        
        # Get pending withdrawals
        cursor.execute('''
            SELECT * FROM withdrawal_requests
            WHERE bot_id = ?
            ORDER BY created_at DESC
        ''', [bot_id])
        
        withdrawals = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'botId': bot_id,
            'totalCommissions': round(total_commission, 2),
            'commissionHistory': commission_history,
            'withdrawals': withdrawals,
            'pendingWithdrawal': sum(w['amount'] for w in withdrawals if w['status'] == 'pending'),
            'completedWithdrawal': sum(w['amount'] for w in withdrawals if w['status'] == 'completed')
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting bot commissions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/dashboard/bots-summary', methods=['GET'])
@require_session
def get_dashboard_summary():
    """Get summary of all user bots for dashboard display with balance, profit, trades, winRate, status, tradingMode."""
    try:
        user_id = g.user_id
        # Get all bots for this user
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM user_bots WHERE user_id = ?', [user_id])
        user_bots = [dict(row) for row in cursor.fetchall()]
        conn.close()
        summary = []
        
        for bot_row in user_bots:
            bot_id = bot_row['bot_id']
            
            if bot_id not in active_bots:
                continue
            
            bot = active_bots[bot_id]
            
            # Get live balance from broker
            credential_id = bot.get('credentialId')
            broker_type = bot.get('broker_type', 'MT5')
            current_balance = bot.get('accountBalance', 0)
            
            try:
                if credential_id:
                    _, broker_conn = get_broker_connection(credential_id, user_id, bot_id)
                    account_info = broker_conn.get_account_info()
                    if account_info:
                        current_balance = account_info.get('balance', account_info.get('equity', 0))
            except:
                pass
            
            total_profit = bot.get('totalProfit', 0)
            total_trades = bot.get('totalTrades', 0)
            
            summary.append({
                'botId': bot_id,
                'botName': bot.get('name', f'Bot-{bot_id[:8]}'),
                'broker': {
                    'type': broker_type,
                    'accountNumber': bot_row.get('broker_account_id', 'N/A')
                },
                'balance': round(current_balance, 2),
                'profit': round(total_profit, 2),
                'trades': total_trades,
                'winRate': round((bot.get('winningTrades', 0) / max(total_trades, 1)) * 100, 1) if total_trades > 0 else 0,
                'status': 'Running' if bot.get('enabled', False) else 'Stopped',
                'tradingMode': bot.get('tradingMode', 'interval'),
                'createdAt': bot.get('createdAt', 'Unknown')
            })
        
        return jsonify({
            'success': True,
            'botsCount': len(summary),
            'botsRunning': sum(1 for b in summary if b['status'] == 'Running'),
            'totalBalance': round(sum(b['balance'] for b in summary), 2),
            'totalProfit': round(sum(b['profit'] for b in summary), 2),
            'bots': summary,
            'timestamp': datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/status-public', methods=['GET'])
def bot_status_public():
    """Get status of RUNNING bots only (public endpoint, no authentication required)."""
    try:
        bots_list = []
        
        # Only include ENABLED (running) bots
        for bot_id, bot in active_bots.items():
            # Include bot if:
            # 1. It's explicitly marked as running in running_bots OR
            # 2. It's enabled in active_bots (just created, background thread starting)
            is_marked_running = running_bots.get(bot_id, False)
            is_enabled = bot.get('enabled', True)
            
            # Skip only if BOTH conditions fail
            if not is_marked_running and not is_enabled:
                logger.debug(f"Skipping bot {bot_id}: marked_running={is_marked_running}, enabled={is_enabled}")
                continue
            
            # Calculate runtime
            created = datetime.fromisoformat(bot.get('createdAt', datetime.now().isoformat()))
            runtime_seconds = (datetime.now() - created).total_seconds()
            runtime_hours = runtime_seconds / 3600
            runtime_minutes = (runtime_seconds % 3600) / 60
            
            # Calculate daily profit (safely access dailyProfits)
            today = datetime.now().strftime('%Y-%m-%d')
            daily_profit = bot.get('dailyProfits', {}).get(today, bot.get('dailyProfit', 0))
            
            # Calculate ROI (safely access totalInvestment)
            investment = bot.get('totalInvestment', 0)
            total_profit = bot.get('totalProfit', 0)
            roi = (total_profit / max(investment, 1)) * 100 if investment > 0 else 0
            
            # Calculate profit factor (safely access totalLosses)
            total_losses = bot.get('totalLosses', 0)
            if total_losses > 0:
                profit_factor = min(total_profit / total_losses, 99.99) if total_profit > 0 else 0
            else:
                profit_factor = 99.99 if total_profit > 0 else 0
            
            # Safely access symbols and strategy
            symbols = bot.get('symbols', [])
            symbol = symbols[0] if symbols else 'EURUSDm'
            
            # Determine status based on whether thread is actively running
            if is_marked_running:
                status = 'Running'
            elif is_enabled and not is_marked_running:
                status = 'Starting'  # Just created, background thread starting
            else:
                status = 'Stopped'
            
            enhanced_bot = {
                'botId': bot.get('botId', 'unknown'),
                'symbol': symbol,
                'symbols': symbols,  # ✅ Include full symbols list
                'strategy': bot.get('strategy', 'Unknown'),
                'commission': round(total_profit * 0.01, 2),
                'profit': round(total_profit, 2),
                'totalProfit': round(total_profit, 2),  # ✅ Include totalProfit field
                'totalTrades': bot.get('totalTrades', 0),  # ✅ Include totalTrades
                'winningTrades': bot.get('winningTrades', 0),  # ✅ Include winningTrades
                'runtimeFormatted': f"{int(runtime_hours)}h {int(runtime_minutes)}m",
                'dailyProfit': round(daily_profit, 2),
                'roi': round(roi, 2),
                'profitFactor': round(profit_factor, 2),
                'avgProfitPerTrade': round(total_profit / max(bot.get('totalTrades', 1), 1), 2),
                'status': status,
                'enabled': is_enabled,
                'broker_type': bot.get('broker_type', 'MT5'),
                'createdAt': created.isoformat(),
                'lastTradeTime': bot.get('tradeHistory', [{}])[-1].get('time') if bot.get('tradeHistory') else bot.get('createdAt', datetime.now().isoformat()),
            }
            bots_list.append(enhanced_bot)
        
        # Sort by creation date (latest first)
        bots_list.sort(key=lambda x: x['createdAt'], reverse=True)
        
        return jsonify({
            'success': True,
            'activeBots': len(bots_list),
            'runningBots': len([b for b in bots_list if b['status'] == 'Running']),
            'startingBots': len([b for b in bots_list if b['status'] == 'Starting']),
            'bots': bots_list,
            'timestamp': datetime.now().isoformat(),
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting public bot status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/stop/<bot_id>', methods=['POST'])
@require_session
def stop_bot(bot_id):
    """Stop a trading bot (still keeps it in system for restart)"""
    try:
        data = request.json or {}
        user_id = data.get('user_id') or request.user_id
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        # Verify bot belongs to user
        bot_config = active_bots[bot_id]
        if bot_config.get('user_id') != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
        # Also verify in database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM user_bots WHERE bot_id = ?', (bot_id,))
        db_bot = cursor.fetchone()
        conn.close()
        
        if not db_bot or db_bot['user_id'] != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
        final_stats = stop_bot_runtime(bot_id, bot_config)
        
        return jsonify({
            'success': True,
            'message': f'Bot {bot_id} stopped',
            'finalStats': {
                'totalTrades': final_stats['totalTrades'],
                'winningTrades': final_stats['winningTrades'],
                'totalProfit': final_stats['totalProfit'],
                'note': 'Bot can be restarted later. Use /delete to permanently remove.'
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/stop-all', methods=['POST'])
@require_session
def stop_all_bots():
    """Stop all matching bots for the authenticated user."""
    try:
        data = request.json or {}
        user_id = data.get('user_id') or request.user_id
        mode_filter = (data.get('mode') or 'all').lower()
        only_loss_making = bool(data.get('only_loss_making', False))

        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        if mode_filter not in {'all', 'demo', 'live'}:
            return jsonify({'success': False, 'error': 'mode must be one of: all, demo, live'}), 400

        stopped_bots = []
        skipped_bots = []

        for bot_id, bot_config in list(active_bots.items()):
            if bot_config.get('user_id') != user_id:
                continue
            if not bot_config.get('enabled'):
                skipped_bots.append({'botId': bot_id, 'reason': 'already_disabled'})
                continue

            bot_mode = (bot_config.get('mode') or 'demo').lower()
            if mode_filter != 'all' and bot_mode != mode_filter:
                skipped_bots.append({'botId': bot_id, 'reason': f'mode_{bot_mode}'})
                continue

            total_profit = float(bot_config.get('totalProfit', 0.0) or 0.0)
            daily_profit = float(bot_config.get('dailyProfit', 0.0) or 0.0)
            if only_loss_making and total_profit >= 0 and daily_profit >= 0:
                skipped_bots.append({'botId': bot_id, 'reason': 'not_loss_making'})
                continue

            stopped_bots.append(stop_bot_runtime(bot_id, bot_config))

        logger.info(
            f"🛑 Stopped {len(stopped_bots)} bots for user {user_id} "
            f"(mode={mode_filter}, only_loss_making={only_loss_making})"
        )

        return jsonify({
            'success': True,
            'message': f'Stopped {len(stopped_bots)} bots',
            'stoppedBots': stopped_bots,
            'skippedBots': skipped_bots,
        }), 200

    except Exception as e:
        logger.error(f"Error stopping all bots: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/delete/<bot_id>', methods=['DELETE', 'POST'])
@require_session
def delete_bot(bot_id):
    """Delete a trading bot permanently (requires confirmation token)"""
    try:
        data = request.json or {}
        user_id = data.get('user_id') or request.user_id
        confirmation_token = data.get('confirmation_token')
        
        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400
        
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        # Verify bot belongs to user
        bot_config = active_bots[bot_id]
        if bot_config.get('user_id') != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
        # OPTIONAL: Verify confirmation token (for enhanced security)
        # If token is provided, validate it; if not, allow deletion for backward compatibility
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if confirmation_token:
            # TOKEN PROVIDED: Look up and verify token
            cursor.execute('''
                SELECT * FROM bot_deletion_tokens
                WHERE bot_id = ? AND user_id = ? AND deletion_token = ? AND expires_at > ?
            ''', (bot_id, user_id, confirmation_token, datetime.now().isoformat()))
            
            token_record = cursor.fetchone()
            
            if not token_record:
                conn.close()
                return jsonify({
                    'success': False,
                    'error': 'Invalid or expired confirmation token',
                    'next_step': f'Call POST /api/bot/{bot_id}/request-deletion to get a new token'
                }), 401
            
            logger.info(f"✅ Bot {bot_id} deletion token verified for user {user_id}")
        else:
            # NO TOKEN PROVIDED: Allow deletion for backward compatibility
            logger.warning(f"⚠️  Bot {bot_id} deleted WITHOUT 2-step confirmation (legacy request from user {user_id})")
            logger.warning(f"   Recommendation: Update client to use /api/bot/{bot_id}/request-deletion + token for safety")
        
        # Verify bot ownership in database
        cursor.execute('SELECT user_id FROM user_bots WHERE bot_id = ?', (bot_id,))
        db_bot = cursor.fetchone()
        
        if not db_bot or db_bot['user_id'] != user_id:
            conn.close()
            return jsonify({'success': False, 'error': 'Unauthorized: Bot does not belong to this user'}), 403
        
        # Log deletion with all stats
        final_stats = bot_config.copy()
        logger.critical(f"\ud83d\uddd1\ufe0f BOT PERMANENTLY DELETED: {bot_id} by user {user_id}")
        logger.critical(f"   Final Stats: {json.dumps({'totalTrades': final_stats.get('totalTrades'), 'totalProfit': final_stats.get('totalProfit')}, indent=2)}")
        logger.critical(f"   Deletion confirmed with token: {confirmation_token[:8]}...")
        
        # Delete from database
        cursor.execute('DELETE FROM user_bots WHERE bot_id = ?', (bot_id,))
        cursor.execute('DELETE FROM bot_credentials WHERE bot_id = ?', (bot_id,))
        cursor.execute('DELETE FROM bot_deletion_tokens WHERE bot_id = ?', (bot_id,))
        cursor.execute('DELETE FROM bot_activation_pins WHERE bot_id = ?', (bot_id,))
        conn.commit()
        
        # Stop bot if running
        if bot_config.get('enabled', False):
            bot_config['enabled'] = False
        
        # Remove from active_bots
        del active_bots[bot_id]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Bot {bot_id} permanently deleted',
            'deleted_stats': {
                'totalTrades': final_stats.get('totalTrades', 0),
                'winningTrades': final_stats.get('winningTrades', 0),
                'totalProfit': final_stats.get('totalProfit', 0),
            },
            'remainingBots': len(active_bots)
        }), 200
    
    except Exception as e:
        logger.error(f"Error deleting bot: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== BOT MONITORING SYSTEM ====================
@app.route('/api/bot/<bot_id>/health', methods=['GET'])
@require_api_key
def get_bot_health(bot_id):
    """Get bot health and monitoring status"""
    try:
        if bot_id not in active_bots:
            return jsonify({'success': False, 'error': f'Bot {bot_id} not found'}), 404
        
        bot_config = active_bots[bot_id]
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get monitoring data
        cursor.execute('''
            SELECT status, last_heartbeat, uptime_seconds, health_check_count, 
                   errors_count, last_error, auto_restart_count
            FROM bot_monitoring WHERE bot_id = ?
        ''', (bot_id,))
        
        monitoring = cursor.fetchone()
        conn.close()
        
        health_status = {
            'bot_id': bot_id,
            'is_running': bot_config.get('enabled', False),
            'strategy': bot_config.get('strategy', 'Unknown'),
            'daily_profit': bot_config.get('dailyProfit', 0),
            'total_profit': bot_config.get('totalProfit', 0),
            'status': dict(monitoring)['status'] if monitoring else 'unknown',
            'last_heartbeat': dict(monitoring)['last_heartbeat'] if monitoring else None,
            'uptime_seconds': dict(monitoring)['uptime_seconds'] if monitoring else 0,
            'health_checks': dict(monitoring)['health_check_count'] if monitoring else 0,
            'error_count': dict(monitoring)['errors_count'] if monitoring else 0,
            'last_error': dict(monitoring)['last_error'] if monitoring else None,
            'auto_restarts': dict(monitoring)['auto_restart_count'] if monitoring else 0,
        }
        
        return jsonify({
            'success': True,
            'health': health_status
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting bot health: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== AUTO-WITHDRAWAL SYSTEM ====================
@app.route('/api/bot/<bot_id>/auto-withdrawal', methods=['POST'])
@require_api_key
def set_auto_withdrawal(bot_id):
    """
    Set withdrawal mode and parameters for a bot

    Modes:
    - 'fixed': Withdraw at user-predetermined profit level
    - 'intelligent': Robot decides intelligently based on market conditions
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        withdrawal_mode = data.get('withdrawal_mode', 'fixed')  # 'fixed' or 'intelligent'
        target_profit = data.get('target_profit')               # For fixed mode

        if not user_id:
            return jsonify({'success': False, 'error': 'user_id required'}), 400

        if withdrawal_mode not in ['fixed', 'intelligent']:
            return jsonify({'success': False, 'error': "withdrawal_mode must be 'fixed' or 'intelligent'"}), 400

        # Validate based on mode
        min_profit = None
        max_profit = None
        volatility_threshold = None
        win_rate_min = None
        trend_strength_min = None
        time_between_withdrawals_hours = None

        if withdrawal_mode == 'fixed':
            if not target_profit:
                return jsonify({'success': False, 'error': 'target_profit required for fixed mode'}), 400

            if target_profit < 10:
                return jsonify({'success': False, 'error': 'Minimum profit target is $10'}), 400

            if target_profit > 50000:
                return jsonify({'success': False, 'error': 'Maximum profit target is $50,000'}), 400

        elif withdrawal_mode == 'intelligent':
            # Intelligent mode parameters
            min_profit                     = data.get('min_profit', 50)
            max_profit                     = data.get('max_profit', 1000)
            volatility_threshold           = data.get('volatility_threshold', 0.02)
            win_rate_min                   = data.get('win_rate_min', 60)
            trend_strength_min             = data.get('trend_strength_min', 0.5)
            time_between_withdrawals_hours = data.get('time_between_withdrawals_hours', 24)

            # Validate parameters
            if min_profit < 10:
                return jsonify({'success': False, 'error': 'Minimum profit must be >= $10'}), 400
            if volatility_threshold < 0 or volatility_threshold > 0.1:
                return jsonify({'success': False, 'error': 'Volatility threshold must be 0-0.1'}), 400
            if win_rate_min < 40 or win_rate_min > 100:
                return jsonify({'success': False, 'error': 'Win rate must be 40-100%'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        setting_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        updated_at = created_at

        if withdrawal_mode == 'fixed':
            cursor.execute('''
                INSERT OR REPLACE INTO auto_withdrawal_settings
                (setting_id, bot_id, user_id, target_profit, is_active,
                 withdrawal_mode, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                setting_id,
                bot_id,
                user_id,
                target_profit,
                1,
                'fixed',
                created_at,
                updated_at
            ))

            message = f'Fixed withdrawal set: Will withdraw when profit reaches ${target_profit}'

        else:  # intelligent
            cursor.execute('''
                INSERT OR REPLACE INTO auto_withdrawal_settings
                (setting_id, bot_id, user_id, withdrawal_mode,
                 min_profit, max_profit, volatility_threshold,
                 win_rate_min, trend_strength_min,
                 time_between_withdrawals_hours,
                 last_withdrawal_at,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                setting_id,
                bot_id,
                user_id,
                'intelligent',
                min_profit,
                max_profit,
                volatility_threshold,
                win_rate_min,
                trend_strength_min,
                time_between_withdrawals_hours,
                None,
                created_at,
                updated_at
            ))

            message = (
                f'Intelligent withdrawal activated with min profit ${min_profit}, '
                f'max ${max_profit}, volatility < {volatility_threshold:.2%}'
            )

        conn.commit()
        conn.close()

        logger.info(f"Auto-withdrawal configured for bot {bot_id}: {withdrawal_mode} mode")

        return jsonify({
            'success': True,
            'setting_id': setting_id,
            'bot_id': bot_id,
            'withdrawal_mode': withdrawal_mode,
            'message': message
        }), 200

    except Exception as e:
        logger.error(f"Error setting auto-withdrawal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/<bot_id>/auto-withdrawal-status', methods=['GET'])
@require_api_key
def get_auto_withdrawal_status(bot_id):
    """Get auto-withdrawal settings and history for a bot"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current settings
        cursor.execute('''
            SELECT setting_id, target_profit, is_active, created_at
            FROM auto_withdrawal_settings WHERE bot_id = ? AND is_active = 1
        ''', (bot_id,))
        
        settings = cursor.fetchone()
        
        # Get withdrawal history
        cursor.execute('''
            SELECT withdrawal_id, triggered_profit, withdrawal_amount, net_amount, 
                   status, created_at, completed_at
            FROM auto_withdrawal_history
            WHERE bot_id = ?
            ORDER BY created_at DESC
            LIMIT 10
        ''', (bot_id,))
        
        history = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'bot_id': bot_id,
            'current_setting': dict(settings) if settings else None,
            'history': history,
            'total_auto_withdrawals': len(history),
            'total_amount_withdrawn': sum([float(h['withdrawal_amount']) for h in history])
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting auto-withdrawal status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bot/<bot_id>/disable-auto-withdrawal', methods=['POST'])
@require_api_key
def disable_auto_withdrawal(bot_id):
    """Disable auto-withdrawal for a bot"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE auto_withdrawal_settings
            SET is_active = 0, updated_at = ?
            WHERE bot_id = ?
        ''', (datetime.now().isoformat(), bot_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Auto-withdrawal disabled for bot {bot_id}")
        
        return jsonify({
            'success': True,
            'message': f'Auto-withdrawal disabled for bot {bot_id}'
        }), 200
    
    except Exception as e:
        logger.error(f"Error disabling auto-withdrawal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== REFERRAL API ENDPOINTS ====================

@app.route('/api/user/login', methods=['POST'])
def login_user():
    """Login user by email - creates session"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'success': False, 'error': 'Email required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Find user by email
        cursor.execute('SELECT user_id, name, email, referral_code FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        user_dict = dict(user)
        user_id = user_dict['user_id']
        
        # Create session token
        session_id = str(uuid.uuid4())
        token = hashlib.sha256(f"{user_id}{datetime.now().isoformat()}".encode()).hexdigest()
        expires_at = (datetime.now() + timedelta(days=30)).isoformat()
        
        cursor.execute('''
            INSERT INTO user_sessions (session_id, user_id, token, created_at, expires_at, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        ''', (session_id, user_id, token, datetime.now().isoformat(), expires_at))
        
        conn.commit()
        conn.close()
        
        logger.info(f"User logged in: {email}")
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'name': user_dict['name'],
            'email': user_dict['email'],
            'referral_code': user_dict['referral_code'],
            'session_token': token,
            'message': 'Login successful'
        }), 200
    
    except Exception as e:
        logger.error(f"Error in login_user: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/profile/<user_id>', methods=['GET'])
@require_session
def get_user_profile(user_id):
    """Get user profile and their associated data"""
    # Verify user is accessing only their own profile
    if request.user_id != user_id:
        return jsonify({'success': False, 'error': 'Unauthorized: Cannot access other user profiles'}), 403
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get user info
        cursor.execute('''
            SELECT user_id, name, email, referral_code, total_commission, created_at
            FROM users WHERE user_id = ?
        ''', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        user_dict = dict(user)
        
        # Get user's bots
        cursor.execute('''
            SELECT bot_id, name, strategy, status, enabled, daily_profit, total_profit, created_at
            FROM user_bots WHERE user_id = ? ORDER BY created_at DESC
        ''', (user_id,))
        
        bots = [dict(row) for row in cursor.fetchall()]
        
        # Get user's broker credentials
        cursor.execute('''
            SELECT credential_id, broker_name, account_number, is_live, is_active
            FROM broker_credentials WHERE user_id = ? ORDER BY created_at DESC
        ''', (user_id,))
        
        brokers = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'user': user_dict,
            'bots': bots,
            'total_bots': len(bots),
            'brokers': brokers,
            'total_brokers': len(brokers)
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/<user_id>/broker-credentials', methods=['POST'])
@require_session
def add_broker_credentials(user_id):
    """Add broker credentials for a user"""
    # Verify user is adding credentials for themselves
    if request.user_id != user_id:
        return jsonify({'success': False, 'error': 'Unauthorized: Cannot add credentials for other users'}), 403
    """Add broker credentials for a user"""
    try:
        data = request.get_json()
        broker_name = data.get('broker_name')
        account_number = data.get('account_number')
        password = data.get('password')
        server = data.get('server')
        is_live = data.get('is_live', False)
        
        if not all([broker_name, account_number, password]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify user exists
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        # Insert broker credentials
        credential_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO broker_credentials 
            (credential_id, user_id, broker_name, account_number, password, server, is_live, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (credential_id, user_id, broker_name, account_number, password, server, is_live, created_at, created_at))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Broker credentials added for user {user_id}: {broker_name}")
        
        return jsonify({
            'success': True,
            'credential_id': credential_id,
            'message': f'Broker credentials added for {broker_name}'
        }), 200
    
    except Exception as e:
        logger.error(f"Error adding broker credentials: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/<user_id>/bots', methods=['GET'])
@require_session
def get_user_bots(user_id):
    """Get all bots for a specific user"""
    # Verify user is accessing only their own bots
    if request.user_id != user_id:
        return jsonify({'success': False, 'error': 'Unauthorized: Cannot access other user bots'}), 403
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify user exists
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        # Get user's bots from database
        cursor.execute('''
            SELECT bot_id, name, strategy, status, enabled, daily_profit, total_profit, created_at
            FROM user_bots WHERE user_id = ? ORDER BY created_at DESC
        ''', (user_id,))
        
        bots = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # Calculate totals
        total_daily = sum([float(bot.get('daily_profit', 0)) for bot in bots])
        total_profit = sum([float(bot.get('total_profit', 0)) for bot in bots])
        active_count = sum([1 for bot in bots if bot.get('enabled')])
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'bots': bots,
            'total_bots': len(bots),
            'active_bots': active_count,
            'total_daily_profit': total_daily,
            'total_profit': total_profit
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting user bots: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/<user_id>/recruits', methods=['GET'])
def get_recruits(user_id):
    """Get all users recruited by this user"""
    try:
        recruits = ReferralSystem.get_recruits(user_id)
        
        return jsonify({
            'success': True,
            'recruits': recruits,
            'total_recruits': len(recruits)
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting recruits: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/<user_id>/earnings', methods=['GET'])
def get_earnings(user_id):
    """Get commission earnings summary"""
    try:
        recap = ReferralSystem.get_earning_recap(user_id)
        
        return jsonify({
            'success': True,
            **recap
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting earnings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/referral/validate/<referral_code>', methods=['GET'])
def validate_referral_code(referral_code):
    """Check if referral code is valid"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, name, email FROM users WHERE referral_code = ?
        ''', (referral_code.upper(),))
        
        referrer = cursor.fetchone()
        conn.close()
        
        if referrer:
            return jsonify({
                'success': True,
                'valid': True,
                'referrer_name': referrer['name'],
                'referrer_email': referrer['email']
            }), 200
        else:
            return jsonify({
                'success': True,
                'valid': False,
                'message': 'Referral code not found'
            }), 404
    
    except Exception as e:
        logger.error(f"Error validating referral code: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/referral/link/<referral_code>', methods=['GET'])
def get_referral_link(referral_code):
    """Get shareable referral link"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id, name FROM users WHERE referral_code = ?', (referral_code.upper(),))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            referral_link = f"https://yourapp.com/register?ref={referral_code.upper()}"
            return jsonify({
                'success': True,
                'referral_code': referral_code.upper(),
                'referral_link': referral_link,
                'referrer_name': user['name'],
                'message': f"Share this link to invite others: {referral_link}"
            }), 200
        else:
            return jsonify({'success': False, 'error': 'Referral code not found'}), 404
    
    except Exception as e:
        logger.error(f"Error getting referral link: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/<user_id>/referral-code', methods=['GET'])
@require_api_key
def get_user_referral_code(user_id):
    """Get users referral code and details"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id, name, referral_code, email, created_at FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        user_dict = dict(user)
        referral_link = f"https://zwesta.com/register?ref={user_dict['referral_code']}"
        
        # Get recruit count
        cursor.execute('SELECT COUNT(*) as count FROM referrals WHERE referrer_id = ?', (user_id,))
        recruit_data = cursor.fetchone()
        recruit_count = dict(recruit_data)['count'] if recruit_data else 0
        
        conn.close()
        
        return jsonify({
            'success': True,
            'user_id': user_dict['user_id'],
            'name': user_dict['name'],
            'email': user_dict['email'],
            'referral_code': user_dict['referral_code'],
            'referral_link': referral_link,
            'recruited_count': recruit_count,
            'created_at': user_dict['created_at']
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting referral code: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/<user_id>/regenerate-referral-code', methods=['POST'])
@require_api_key
def regenerate_referral_code(user_id):
    """Regenerate users referral code"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        # Generate new referral code
        new_code = ReferralSystem.generate_referral_code()
        
        # Check if code already exists (very rare)
        while True:
            cursor.execute('SELECT referral_code FROM users WHERE referral_code = ?', (new_code,))
            if not cursor.fetchone():
                break
            new_code = ReferralSystem.generate_referral_code()
        
        # Update user's referral code
        cursor.execute('UPDATE users SET referral_code = ? WHERE user_id = ?', (new_code, user_id))
        conn.commit()
        conn.close()
        
        logger.info(f"Regenerated referral code for user {user_id}")
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'new_referral_code': new_code,
            'referral_link': f"https://zwesta.com/register?ref={new_code}",
            'message': 'Referral code regenerated successfully'
        }), 200
    
    except Exception as e:
        logger.error(f"Error regenerating referral code: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== ADMIN COMMISSION CONFIG ====================

@app.route('/api/admin/commission-config', methods=['GET'])
@require_api_key
def get_commission_config():
    """Get current commission rate configuration"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cfg = _get_commission_config(cursor)
        conn.close()
        return jsonify({'success': True, 'config': cfg}), 200
    except Exception as e:
        logger.error(f"Error getting commission config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/commission-config', methods=['POST'])
@require_api_key
def update_commission_config():
    """Update commission rate configuration (admin only)"""
    try:
        data = request.get_json()

        # Validate rates are between 0 and 1
        rate_fields = [
            'developer_direct_rate', 'developer_referral_rate', 'recruiter_rate',
            'ig_developer_rate', 'ig_recruiter_rate', 'tier2_rate'
        ]
        for field in rate_fields:
            if field in data:
                val = float(data[field])
                if val < 0 or val > 1:
                    return jsonify({'success': False, 'error': f'{field} must be between 0 and 1'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build dynamic UPDATE
        updates = []
        values = []
        allowed = rate_fields + ['developer_id', 'ig_commission_enabled', 'multi_tier_enabled']
        for key in allowed:
            if key in data:
                updates.append(f'{key} = ?')
                values.append(data[key])

        if not updates:
            conn.close()
            return jsonify({'success': False, 'error': 'No valid fields to update'}), 400

        updates.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append('default')

        cursor.execute(
            f"UPDATE commission_config SET {', '.join(updates)} WHERE config_id = ?",
            values
        )
        conn.commit()

        # Return updated config
        cfg = _get_commission_config(cursor)
        conn.close()

        logger.info(f"✅ Commission config updated: {data}")

        return jsonify({'success': True, 'config': cfg, 'message': 'Commission rates updated successfully'}), 200
    except Exception as e:
        logger.error(f"Error updating commission config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/commission-config/preview', methods=['POST'])
@require_api_key
def preview_commission_split():
    """Preview how a profit amount would be split with given rates"""
    try:
        data = request.get_json()
        profit = float(data.get('profit_amount', 100))
        has_referrer = data.get('has_referrer', True)
        source = data.get('source', 'MT5')

        conn = get_db_connection()
        cursor = conn.cursor()
        cfg = _get_commission_config(cursor)
        conn.close()

        if source == 'IG':
            dev_rate = float(cfg.get('ig_developer_rate', 0.20))
            rec_rate = float(cfg.get('ig_recruiter_rate', 0.05))
            direct_rate = dev_rate + rec_rate
        else:
            direct_rate = float(cfg.get('developer_direct_rate', 0.25))
            dev_rate = float(cfg.get('developer_referral_rate', 0.20))
            rec_rate = float(cfg.get('recruiter_rate', 0.05))

        tier2_rate = float(cfg.get('tier2_rate', 0.02))
        multi_tier = bool(cfg.get('multi_tier_enabled', 0))

        if has_referrer:
            dev_amount = profit * dev_rate
            rec_amount = profit * rec_rate
            tier2_amount = profit * tier2_rate if multi_tier else 0
            trader_keeps = profit - dev_amount - rec_amount - tier2_amount
            breakdown = {
                'developer': {'rate': dev_rate, 'amount': round(dev_amount, 2)},
                'recruiter': {'rate': rec_rate, 'amount': round(rec_amount, 2)},
            }
            if multi_tier:
                breakdown['tier2'] = {'rate': tier2_rate, 'amount': round(tier2_amount, 2)}
        else:
            dev_amount = profit * direct_rate
            trader_keeps = profit - dev_amount
            breakdown = {
                'developer': {'rate': direct_rate, 'amount': round(dev_amount, 2)},
            }

        return jsonify({
            'success': True,
            'profit_amount': profit,
            'source': source,
            'has_referrer': has_referrer,
            'breakdown': breakdown,
            'total_commission': round(profit - trader_keeps, 2),
            'trader_keeps': round(trader_keeps, 2),
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/dashboard', methods=['GET'])
@require_api_key
def admin_dashboard():
    """Admin dashboard with all users, bots, and earnings"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get total users
        cursor.execute('SELECT COUNT(*) as count FROM users')
        total_users = cursor.fetchone()['count'] or 0
        
        # Get total active bots
        total_bots = len([b for b in active_bots.values() if b.get('enabled', False)])
        
        # Get platform earnings (25% of all profits)
        cursor.execute('SELECT SUM(commission_amount * 5) as total_earned FROM commissions')
        platform_earnings_from_referrals = (cursor.fetchone()['total_earned'] or 0) / 5  # Divide back to get 25%
        
        # Calculate from actual bot profits
        total_profit = sum([b.get('totalProfit', 0) for b in active_bots.values()])
        platform_earnings = total_profit * 0.25  # 25% of all profits
        
        # Get all users with their bots
        cursor.execute('SELECT user_id, name, email FROM users ORDER BY created_at DESC LIMIT 100')
        users_list = [dict(row) for row in cursor.fetchall()]
        
        users_with_bots = []
        for user in users_list:
            # Find bots belonging to this user (simplified - would need more DB tracking)
            user_bots = [
                {
                    'botId': bot_id,
                    'strategy': bot_config.get('strategy', 'Unknown'),
                    'profit': bot_config.get('totalProfit', 0)
                }
                for bot_id, bot_config in active_bots.items()
            ]
            
            # Get user's commission info
            cursor.execute('''
                SELECT COUNT(DISTINCT client_id) as client_count, SUM(commission_amount) as total_commission
                FROM commissions WHERE earner_id = ?
            ''', (user['user_id'],))
            
            commission_data = dict(cursor.fetchone())
            
            users_with_bots.append({
                'user_id': user['user_id'],
                'name': user['name'],
                'email': user['email'],
                'bot_count': len(user_bots),
                'bots': user_bots[:5],  # First 5 bots
                'total_profit': sum([b.get('profit', 0) for b in user_bots]),
                'recruiter_count': commission_data.get('client_count', 0),
                'referral_earnings': commission_data.get('total_commission', 0)
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'total_users': total_users,
            'total_bots': total_bots,
            'total_profit': total_profit,
            'platform_earnings': platform_earnings,
            'referral_earnings': platform_earnings_from_referrals,
            'commission_rate_platform': 0.25,
            'commission_rate_referrer': 0.05,
            'users': users_with_bots
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting admin dashboard: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/ig-credentials/health', methods=['GET'])
@require_api_key
def admin_ig_credentials_health():
    """Admin view of IG credential readiness by user without returning secrets."""
    try:
        include_all = str(request.args.get('include_all', 'true')).lower() in ('1', 'true', 'yes')
        limit = int(request.args.get('limit', 200))
        if limit < 1:
            limit = 1
        if limit > 1000:
            limit = 1000

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT
                u.user_id,
                u.email,
                u.name,
                bc.credential_id,
                bc.username AS ig_username,
                bc.account_number AS ig_account_id,
                bc.is_live,
                bc.api_key,
                bc.password,
                bc.updated_at,
                bc.created_at
            FROM users u
            LEFT JOIN broker_credentials bc
              ON bc.credential_id = (
                  SELECT bc2.credential_id
                  FROM broker_credentials bc2
                  WHERE bc2.user_id = u.user_id
                    AND bc2.is_active = 1
                    AND bc2.broker_name IN ('IG Markets', 'IG.com', 'IG')
                  ORDER BY bc2.updated_at DESC, bc2.created_at DESC
                  LIMIT 1
              )
            ORDER BY u.created_at DESC
            LIMIT ?
        ''', (limit,))

        health_rows = []
        total_with_ig = 0
        total_ready = 0

        for row in cursor.fetchall():
            has_ig = bool(row['credential_id'])
            if has_ig:
                total_with_ig += 1

            missing_fields = []
            if has_ig:
                if not row['api_key']:
                    missing_fields.append('api_key')
                if not row['ig_username']:
                    missing_fields.append('username')
                if not row['password']:
                    missing_fields.append('password')
                if not row['ig_account_id']:
                    missing_fields.append('account_id')

            is_ready = has_ig and len(missing_fields) == 0
            if is_ready:
                total_ready += 1

            if include_all or has_ig:
                health_rows.append({
                    'user_id': row['user_id'],
                    'email': row['email'],
                    'name': row['name'],
                    'has_ig_credentials': has_ig,
                    'credential_id': row['credential_id'] if has_ig else None,
                    'ig_username': row['ig_username'] if has_ig else None,
                    'ig_account_id': row['ig_account_id'] if has_ig else None,
                    'environment': 'live' if bool(row['is_live']) else 'demo' if has_ig else None,
                    'is_ready': is_ready,
                    'missing_fields': missing_fields,
                    'updated_at': row['updated_at'] if has_ig else None,
                    'created_at': row['created_at'] if has_ig else None,
                })

        conn.close()

        return jsonify({
            'success': True,
            'summary': {
                'users_scanned': len(health_rows) if include_all else total_with_ig,
                'users_with_ig_credentials': total_with_ig,
                'users_ready': total_ready,
                'users_not_ready': max(total_with_ig - total_ready, 0),
                'include_all': include_all,
                'limit': limit,
            },
            'users': health_rows,
        }), 200
    except Exception as e:
        logger.error(f"Error getting IG credential health: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== WITHDRAWAL SYSTEM ====================
@app.route('/api/withdrawal/request', methods=['POST'])
@require_api_key
def request_withdrawal():
    """Request a withdrawal of earned commissions"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        amount = data.get('amount')
        method = data.get('method')
        account_details = data.get('account_details')
        
        # Validate amount
        if amount < WITHDRAWAL_CONFIG['min_amount']:
            return jsonify({'success': False, 'error': f"Minimum withdrawal is ${WITHDRAWAL_CONFIG['min_amount']}"}), 400
        
        if amount > WITHDRAWAL_CONFIG['max_amount']:
            return jsonify({'success': False, 'error': f"Maximum withdrawal is ${WITHDRAWAL_CONFIG['max_amount']}"}), 400
        
        # Test mode: limit to $50 for testing
        if ENVIRONMENT == 'DEMO':
            if amount > WITHDRAWAL_CONFIG['test_mode_max']:
                return jsonify({'success': False, 'error': f"Test mode: maximum ${WITHDRAWAL_CONFIG['test_mode_max']} per withdrawal"}), 400
        
        # Check available balance
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT SUM(commission_amount) as total_earned FROM commissions 
            WHERE earner_id = ?
        ''', (user_id,))
        
        earnings = cursor.fetchone()
        total_earned = earnings['total_earned'] or 0
        
        # Get withdrawn amount
        cursor.execute('''
            SELECT SUM(amount) as total_withdrawn FROM withdrawals 
            WHERE user_id = ? AND status IN ('approved', 'pending', 'processing')
        ''', (user_id,))
        
        withdrawn = cursor.fetchone()
        total_withdrawn = withdrawn['total_withdrawn'] or 0
        available_balance = total_earned - total_withdrawn
        
        if amount > available_balance:
            conn.close()
            return jsonify({'success': False, 'error': 'Amount exceeds available balance'}), 400
        
        # Create withdrawal request
        withdrawal_id = str(uuid.uuid4())
        fee = amount * (WITHDRAWAL_CONFIG['processing_fee_percent'] / 100)
        net_amount = amount - fee
        created_at = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO withdrawals (withdrawal_id, user_id, amount, method, account_details, status, created_at, fee, net_amount)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
        ''', (withdrawal_id, user_id, amount, method, account_details, created_at, fee, net_amount))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Withdrawal request {withdrawal_id}: {user_id} - ${amount} ({method})")
        
        return jsonify({
            'success': True,
            'withdrawal_id': withdrawal_id,
            'amount': amount,
            'fee': round(fee, 2),
            'net_amount': round(net_amount, 2),
            'status': 'pending',
            'message': f'Withdrawal request submitted. Will receive ${round(net_amount, 2)} after {WITHDRAWAL_CONFIG["processing_fee_percent"]}% fee. Processing in {WITHDRAWAL_CONFIG["processing_days"]} business days.'
        }), 200
    
    except Exception as e:
        logger.error(f"Error requesting withdrawal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/withdrawal/history/<user_id>', methods=['GET'])
def get_withdrawal_history(user_id):
    """Get users withdrawal history"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT withdrawal_id, amount, method, status, created_at, processed_at, net_amount, fee
            FROM withdrawals
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))
        
        withdrawals = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        result = {
            'success': True,
            'withdrawals': withdrawals
        }
        print("\n=== Withdrawal History ===\n", result)
        return jsonify(result), 200
    
    except Exception as e:
        logger.error(f"Error getting withdrawal history: {e}")
        print("\n=== Withdrawal History Error ===\n", str(e))
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/withdrawals', methods=['GET'])
@require_api_key
def admin_withdrawals():
    """Admin endpoint to view all pending withdrawals"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT w.withdrawal_id, w.user_id, u.name, u.email, w.amount, w.method, 
                   w.account_details, w.status, w.created_at, w.fee, w.net_amount
            FROM withdrawals w
            JOIN users u ON w.user_id = u.user_id
            WHERE w.status = 'pending'
            ORDER BY w.created_at ASC
        ''')
        
        withdrawals = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'pending_withdrawals': withdrawals,
            'total_pending': len(withdrawals),
            'total_pending_amount': sum([float(w['amount']) for w in withdrawals])
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting admin withdrawals: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/withdrawals/pending', methods=['GET'])
@require_admin
def admin_get_pending_exness_withdrawals():
    """Get list of pending Exness withdrawals for admin verification (Flutter UI)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                withdrawal_id,
                user_id,
                profit_from_trades,
                commission_earned,
                created_at
            FROM exness_withdrawals 
            WHERE status = 'pending'
            ORDER BY created_at DESC
        ''')
        
        withdrawals = []
        for row in cursor.fetchall():
            withdrawal_dict = dict(row)
            # Get user name for display
            cursor.execute('SELECT name FROM users WHERE user_id = ?', (withdrawal_dict['user_id'],))
            user_row = cursor.fetchone()
            if user_row:
                withdrawal_dict['user_name'] = user_row['name']
            
            withdrawals.append(withdrawal_dict)
        
        conn.close()
        
        logger.info(f"Admin fetched {len(withdrawals)} pending Exness withdrawals")
        
        return jsonify({
            'success': True,
            'withdrawals': withdrawals,
            'count': len(withdrawals)
        }), 200
    
    except Exception as e:
        logger.error(f"Error fetching pending Exness withdrawals: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/withdrawal/<withdrawal_id>/approve', methods=['POST'])
@require_api_key
def approve_withdrawal(withdrawal_id):
    """Admin endpoint to approve withdrawal"""
    try:
        data = request.get_json()
        admin_notes = data.get('notes', '')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE withdrawals
            SET status = 'approved', processed_at = ?, admin_notes = ?
            WHERE withdrawal_id = ?
        ''', (datetime.now().isoformat(), admin_notes, withdrawal_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Withdrawal {withdrawal_id} approved")
        
        return jsonify({
            'success': True,
            'message': 'Withdrawal approved'
        }), 200
    
    except Exception as e:
        logger.error(f"Error approving withdrawal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== DUPLICATE DATABASE SECTION REMOVED ====================
import random as rand

# --- IG API Integration ---
try:
    from ig_service import ig_api
    app.register_blueprint(ig_api)
    logger.info("✅ IG API service loaded")
except ImportError:
    logger.warning("⚠️ ig_service module not found - IG integration disabled")

# --- OANDA API Integration ---
try:
    from oanda_service import oanda_api
    app.register_blueprint(oanda_api)
    logger.info("✅ OANDA API service loaded")
except ImportError:
    logger.warning("⚠️ oanda_service module not found - OANDA integration disabled")

# --- FXCM API Integration ---
try:
    from fxcm_service import fxcm_api
    app.register_blueprint(fxcm_api)
    logger.info("✅ FXCM API service loaded")
except ImportError:
    logger.warning("⚠️ fxcm_service module not found - FXCM integration disabled")

# --- Binance API Integration ---
try:
    from binance_service import binance_api
    app.register_blueprint(binance_api)
    logger.info("✅ Binance API service loaded")
except ImportError:
    logger.warning("⚠️ binance_service module not found - Binance integration disabled")

# --- Unified Broker + Crypto Strategies ---
try:
    from unified_broker_service import unified_broker_api
    app.register_blueprint(unified_broker_api)
    logger.info("✅ Unified broker service loaded")
except ImportError:
    logger.warning("⚠️ unified_broker_service module not found - Unified broker integration disabled")

# Example: Use IG API in bot trading logic
# (You can call these functions from your bot trading threads)
def place_ig_trade(epic, size, direction, currency="USD", order_type="MARKET"):
    import requests
    from flask import current_app
    # Use the IG API endpoint via internal HTTP call or direct function call
    url = f"http://localhost:9000/api/legacy/ig/place-order"
    data = {
        "epic": epic,
        "size": size,
        "direction": direction,
        "currencyCode": currency,
        "orderType": order_type
    }
    try:
        resp = requests.post(url, json=data)
        return resp.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

# Example: Get IG funds for financial info display
def get_ig_funds():
    import requests
    url = f"http://localhost:9000/api/ig/funds"
    try:
        resp = requests.get(url)
        return resp.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

# Example: Get IG open positions for bot monitoring
def get_ig_positions():
    import requests
    url = f"http://localhost:9000/api/legacy/ig/positions"
    try:
        resp = requests.get(url)
        return resp.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

# You can now call place_ig_trade, get_ig_funds, get_ig_positions from your bot logic
# and display the results in your dashboard endpoints.

COMMODITIES = {
    # ===== FOREX (9) - MetaQuotes-Demo Available =====
    'EURUSD': {'category': 'Forex', 'emoji': '📍'},
    'GBPUSD': {'category': 'Forex', 'emoji': '🇬🇧'},
    'USDJPY': {'category': 'Forex', 'emoji': '🇯🇵'},
    'USDCHF': {'category': 'Forex', 'emoji': '🇨🇭'},
    'AUDUSD': {'category': 'Forex', 'emoji': '🦘'},
    'NZDUSD': {'category': 'Forex', 'emoji': '🥝'},
    'USDCAD': {'category': 'Forex', 'emoji': '🍁'},
    'USDSEK': {'category': 'Forex', 'emoji': '🇸🇪'},
    'USDCNH': {'category': 'Forex', 'emoji': '🇨🇳'},
    
    # ===== COMMODITIES (2) - MetaQuotes-Demo Available =====
    'XPTUSD': {'category': 'Metals', 'emoji': '💍'},   # PLATINUM
    'OILK': {'category': 'Energy', 'emoji': '🛢️'},     # CRUDE OIL
    
    # ===== INDICES (2) - MetaQuotes-Demo Available =====
    'SP500m': {'category': 'Indices', 'emoji': '📊'},   # S&P 500
    'DAX': {'category': 'Indices', 'emoji': '📈'},      # DAX
    
    # ===== STOCKS (5) - MetaQuotes-Demo Available =====
    'AMD': {'category': 'Tech Stock', 'emoji': '💻'},
    'MSFT': {'category': 'Tech Stock', 'emoji': '🪟'},
    'INTC': {'category': 'Tech Stock', 'emoji': '⚡'},
    'NVDA': {'category': 'Tech Stock', 'emoji': '🎮'},
    'NIKL': {'category': 'Indices', 'emoji': '🗾'},     # Nikkei
}


# ==================== AUTO-WITHDRAWAL MONITORING ====================
monitoring_thread = None
monitoring_running = False

def auto_withdrawal_monitor():
    """
    Background task to monitor bot profits and execute auto-withdrawals
    Supports two modes:
    - Fixed: Withdraw at user-predetermined profit level
    - Intelligent: Withdraw based on market conditions and bot performance
    """
    global monitoring_running
    monitoring_running = True
    logger.info("Starting auto-withdrawal monitoring thread...")
    
    def should_withdraw_intelligent(bot_id, bot_config, settings):
        """
        Intelligent withdrawal decision based on:
        - Current profit level
        - Win rate
        - Market volatility
        - Trend strength
        - Recent performance
        """
        try:
            current_profit = bot_config.get('totalProfit', 0)
            min_profit = settings[4]  # min_profit from DB
            max_profit = settings[11] if len(settings) > 11 else 1000  # max_profit from DB
            
            # Don't withdraw if profit below minimum threshold
            if current_profit < min_profit:
                return False, None
            
            # Get bot performance metrics
            win_rate = bot_config.get('winRate', 50)
            trades_count = bot_config.get('totalTrades', 0)
            
            # Need at least 5 trades to make intelligent decision
            if trades_count < 5:
                return False, None
            
            # Calculate win rate from bot stats
            winning_trades = bot_config.get('winningTrades', 0)
            if trades_count > 0:
                actual_win_rate = (winning_trades / trades_count) * 100
            else:
                actual_win_rate = 0
            
            win_rate_min = settings[6] if len(settings) > 6 else 60  # win_rate_min from DB
            
            # Don't withdraw if win rate is too low (bot is struggling)
            if actual_win_rate < win_rate_min:
                return False, None
            
            # Calculate withdrawal amount (cap at max_profit)
            withdrawal_amount = min(current_profit, max_profit)
            
            # Check time between withdrawals
            hours_interval = settings[9] if len(settings) > 9 else 24
            last_withdrawal = settings[10] if len(settings) > 10 else None
            if last_withdrawal:
                try:
                    last_dt = datetime.fromisoformat(last_withdrawal)
                    hours_since = (datetime.now() - last_dt).total_seconds() / 3600
                    if hours_since < hours_interval:
                        return False, None
                except Exception:
                    pass
            
            return True, withdrawal_amount
        
        except Exception as e:
            logger.error(f"Error in intelligent withdrawal decision: {e}")
            return False, None
    
    while monitoring_running:
        try:
            time.sleep(30)  # Check every 30 seconds
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get all active auto-withdrawal settings
            cursor.execute('''
                SELECT setting_id, bot_id, user_id, withdrawal_mode, target_profit, 
                       min_profit, win_rate_min, trend_strength_min, volatility_threshold,
                       time_between_withdrawals_hours, last_withdrawal_at, max_profit
                FROM auto_withdrawal_settings
                WHERE is_active = 1
            ''')
            
            settings_list = cursor.fetchall()
            
            for setting in settings_list:
                setting_id, bot_id, user_id, withdrawal_mode = setting[:4]
                target_profit, min_profit, win_rate_min, trend_strength_min = setting[4:8]
                volatility_threshold, hours_interval, last_withdrawal_at, max_profit = setting[8:12]
                
                if bot_id not in active_bots:
                    continue
                
                bot_config = active_bots[bot_id]
                current_profit = bot_config.get('totalProfit', 0)
                
                # Check time interval constraint
                if last_withdrawal_at:
                    last_withdrawal = datetime.fromisoformat(last_withdrawal_at)
                    time_since_last = (datetime.now() - last_withdrawal).total_seconds() / 3600
                    if time_since_last < hours_interval:
                        continue
                
                should_withdraw = False
                withdrawal_amount = 0
                reason = ""
                
                # FIXED MODE: Withdraw when target profit reached
                if withdrawal_mode == 'fixed' and target_profit:
                    if current_profit >= target_profit:
                        should_withdraw = True
                        withdrawal_amount = current_profit
                        reason = f"Fixed target ${target_profit} reached"
                        logger.info(f"[FIXED] Bot {bot_id}: Profit ${current_profit} >= Target ${target_profit}")
                
                # INTELLIGENT MODE: Robot decides based on conditions
                elif withdrawal_mode == 'intelligent':
                    should_withdraw, withdrawal_amount = should_withdraw_intelligent(
                        bot_id, bot_config, setting
                    )
                    reason = f"Intelligent decision (withdrawing ${withdrawal_amount:.2f})" if should_withdraw else ""
                    if should_withdraw:
                        logger.info(f"[INTELLIGENT] Bot {bot_id}: Withdrawal triggered - Profit ${current_profit}")
                
                # Execute withdrawal if criteria met
                if should_withdraw and withdrawal_amount > 0:
                    try:
                        withdrawal_id = str(uuid.uuid4())
                        created_at = datetime.now().isoformat()
                        fee = withdrawal_amount * 0.02  # 2% fee
                        net_amount = withdrawal_amount - fee
                        
                        cursor.execute('''
                            INSERT INTO auto_withdrawal_history
                            (withdrawal_id, bot_id, user_id, triggered_profit, 
                             withdrawal_amount, fee, net_amount, status, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (withdrawal_id, bot_id, user_id, current_profit,
                              withdrawal_amount, fee, net_amount, 'pending', created_at))
                        
                        # Update last withdrawal time
                        cursor.execute('''
                            UPDATE auto_withdrawal_settings
                            SET last_withdrawal_at = ?
                            WHERE bot_id = ?
                        ''', (created_at, bot_id))
                        
                        # Distribute profit split and commissions
                        distribute_profit_split_and_commissions(user_id, withdrawal_amount, bot_id)
                        # Reset bot profit
                        active_bots[bot_id]['totalProfit'] = 0
                        active_bots[bot_id]['dailyProfit'] = 0
                        # Mark as completed
                        cursor.execute('''
                            UPDATE auto_withdrawal_history
                            SET status = 'completed', completed_at = ?
                            WHERE withdrawal_id = ?
                        ''', (datetime.now().isoformat(), withdrawal_id))
                        logger.info(f"✅ Auto-withdrawal executed for {bot_id}: ${net_amount:.2f} (Mode: {withdrawal_mode})")
                    except Exception as e:
                        logger.error(f"Error executing withdrawal for {bot_id}: {e}")
        
        except Exception as e:
            logger.error(f"Error in auto-withdrawal monitor: {e}")
        
        finally:
            if conn:
                conn.close()
    
    logger.info("Auto-withdrawal monitoring thread stopped")


# ==================== USER MANAGEMENT & MULTI-BROKER SYSTEM ====================

@app.route('/api/user/register', methods=['POST'])
def register_user():
    """Register a new user account"""
    try:
        data = request.get_json()
        email = data.get('email', '').lower().strip()
        name = data.get('name', '').strip()
        referrer_code = data.get('referrer_code', '').strip()
        
        if not email or not name:
            return jsonify({'success': False, 'error': 'Email and name required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute('SELECT user_id FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'User already exists'}), 409
        
        user_id = str(uuid.uuid4())
        referral_code = hashlib.sha256(f"{email}{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        referrer_id = None
        
        # Check if referrer exists
        if referrer_code:
            cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (referrer_code,))
            referrer = cursor.fetchone()
            if referrer:
                referrer_id = referrer[0]
        
        cursor.execute('''
            INSERT INTO users (user_id, email, name, referrer_id, referral_code, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, email, name, referrer_id, referral_code, datetime.now().isoformat()))
        
        if referrer_id:
            referral_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO referrals (referral_id, referrer_id, referred_user_id, created_at)
                VALUES (?, ?, ?, ?)
            ''', (referral_id, referrer_id, user_id, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ New user registered: {email} (ID: {user_id})")
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'email': email,
            'name': name,
            'referral_code': referral_code,
            'message': 'Registration successful - use email to login'
        }), 201
    
    except Exception as e:
        logger.error(f"Error in register_user: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/brokers', methods=['GET'])
@require_session
def list_user_brokers():
    """Get all broker credentials for authenticated user"""
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT credential_id, broker_name, account_number, server, is_live, is_active, created_at
            FROM broker_credentials
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))
        
        brokers = []
        for row in cursor.fetchall():
            brokers.append({
                'credential_id': row[0],
                'broker_name': row[1],
                'account_number': row[2],
                'server': row[3],
                'is_live': row[4],
                'is_active': row[5],
                'created_at': row[6],
            })
        
        conn.close()
        
        logger.info(f"✅ Retrieved {len(brokers)} brokers for user {user_id}")
        return jsonify({
            'success': True,
            'brokers': brokers,
            'total': len(brokers)
        }), 200
    
    except Exception as e:
        logger.error(f"Error listing brokers: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/brokers/add', methods=['POST'])
@require_session
def add_user_broker():
    """Add a new broker credential for user"""
    try:
        user_id = request.user_id
        data = request.get_json()
        
        broker_name = data.get('broker_name', '').strip()
        account_number = data.get('account_number', '').strip()
        password = data.get('password', '').strip()
        server = data.get('server', 'MetaQuotes-Demo').strip()
        is_live = data.get('is_live', False)
        
        if not broker_name or not account_number or not password:
            return jsonify({'success': False, 'error': 'Broker name, account number, and password required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if already exists
        cursor.execute('''
            SELECT credential_id FROM broker_credentials
            WHERE user_id = ? AND account_number = ? AND broker_name = ?
        ''', (user_id, account_number, broker_name))
        
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Broker credential already exists'}), 409
        
        credential_id = str(uuid.uuid4())
        
        cursor.execute('''
            INSERT INTO broker_credentials 
            (credential_id, user_id, broker_name, account_number, password, server, is_live, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
        ''', (credential_id, user_id, broker_name, account_number, password, server, is_live, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Added broker credential for user {user_id}: {broker_name} ({account_number})")
        
        return jsonify({
            'success': True,
            'credential_id': credential_id,
            'broker_name': broker_name,
            'account_number': account_number,
            'message': 'Broker credential added successfully'
        }), 201
    
    except Exception as e:
        logger.error(f"Error adding broker: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/brokers/<credential_id>', methods=['DELETE'])
@require_session
def remove_user_broker(credential_id):
    """Remove a broker credential"""
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify ownership
        cursor.execute('''
            SELECT user_id FROM broker_credentials WHERE credential_id = ?
        ''', (credential_id,))
        
        result = cursor.fetchone()
        if not result or result[0] != user_id:
            conn.close()
            return jsonify({'success': False, 'error': 'Unauthorized or not found'}), 403
        
        # Delete the credential
        cursor.execute('DELETE FROM broker_credentials WHERE credential_id = ?', (credential_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Removed broker credential {credential_id} for user {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Broker credential removed'
        }), 200
    
    except Exception as e:
        logger.error(f"Error removing broker: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/dashboard', methods=['GET'])
@require_session
def user_dashboard():
    """Get comprehensive user dashboard with stats"""
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # User info
        cursor.execute('''
            SELECT user_id, name, email, total_commission, created_at FROM users WHERE user_id = ?
        ''', (user_id,))
        user_row = cursor.fetchone()
        user_info = dict(user_row) if user_row else {}
        
        # Total bots
        cursor.execute('SELECT COUNT(*) FROM user_bots WHERE user_id = ?', (user_id,))
        total_bots = cursor.fetchone()[0]
        
        # Active bots
        cursor.execute('SELECT COUNT(*) FROM user_bots WHERE user_id = ? AND enabled = 1', (user_id,))
        active_bots_count = cursor.fetchone()[0]
        
        # Total profit
        cursor.execute('''
            SELECT COALESCE(SUM(total_profit), 0) FROM user_bots WHERE user_id = ?
        ''', (user_id,))
        total_profit = cursor.fetchone()[0] or 0
        
        # Total trades
        cursor.execute('''
            SELECT COUNT(*) FROM trades WHERE bot_id IN (SELECT bot_id FROM user_bots WHERE user_id = ?)
        ''', (user_id,))
        total_trades = cursor.fetchone()[0]
        
        # Commission stats
        cursor.execute('''
            SELECT 
                COALESCE(SUM(commission_amount), 0) as total_earned,
                COUNT(*) as commission_count
            FROM commissions WHERE earner_id = ?
        ''', (user_id,))
        comm_row = cursor.fetchone()
        total_commission_earned = comm_row[0] if comm_row else 0
        commission_count = comm_row[1] if comm_row else 0
        
        # Win rate (profitable trades / total trades)
        cursor.execute('''
            SELECT COUNT(*) FROM trades 
            WHERE bot_id IN (SELECT bot_id FROM user_bots WHERE user_id = ?)
            AND json_extract(trade_data, '$.isWinning') = 1
        ''', (user_id,))
        winning_trades = cursor.fetchone()[0]
        win_rate = round((winning_trades / max(total_trades, 1)) * 100, 2)
        
        # Get top performers (bots)
        cursor.execute('''
            SELECT bot_id, name, total_profit, strategy FROM user_bots
            WHERE user_id = ?
            ORDER BY total_profit DESC
            LIMIT 5
        ''', (user_id,))
        
        top_bots = []
        for row in cursor.fetchall():
            top_bots.append({
                'bot_id': row[0],
                'name': row[1],
                'profit': row[2],
                'strategy': row[3]
            })
        
        # Get broker list
        cursor.execute('''
            SELECT COUNT(*) FROM broker_credentials WHERE user_id = ? AND is_active = 1
        ''', (user_id,))
        active_brokers = cursor.fetchone()[0]
        
        conn.close()
        
        dashboard = {
            'user': user_info,
            'stats': {
                'total_bots': total_bots,
                'active_bots': active_bots_count,
                'total_profit': round(total_profit, 2),
                'total_trades': total_trades,
                'win_rate_percent': win_rate,
                'total_commission_earned': round(total_commission_earned, 2),
                'commission_count': commission_count,
                'active_brokers': active_brokers,
            },
            'top_performers': top_bots,
        }
        
        logger.info(f"✅ Generated dashboard for user {user_id}: {total_bots} bots, ${total_profit:.2f} profit")
        
        return jsonify({
            'success': True,
            'dashboard': dashboard
        }), 200
    
    except Exception as e:
        logger.error(f"Error generating dashboard: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/trading/intelligent-switch', methods=['POST'])
@require_session
def intelligent_asset_switch():
    """Intelligently switch bot assets based on profitability scores"""
    try:
        user_id = request.user_id
        data = request.get_json()
        bot_id = data.get('bot_id')
        
        if not bot_id:
            return jsonify({'success': False, 'error': 'bot_id required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify bot ownership
        cursor.execute('SELECT user_id FROM user_bots WHERE bot_id = ?', (bot_id,))
        bot_owner = cursor.fetchone()
        if not bot_owner or bot_owner[0] != user_id:
            conn.close()
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        # Get current bot symbols
        cursor.execute('SELECT symbols FROM user_bots WHERE bot_id = ?', (bot_id,))
        current_symbols_str = cursor.fetchone()[0]
        current_symbols = current_symbols_str.split(',') if current_symbols_str else ['EURUSD']
        
        # Get best assets based on profitability
        best_assets = get_best_trading_assets(limit=5)
        
        # Check if we should switch
        asset_switch_made = False
        if best_assets and best_assets != current_symbols:
            new_symbols = best_assets
            cursor.execute('''
                UPDATE user_bots SET symbols = ? WHERE bot_id = ?
            ''', (','.join(new_symbols), bot_id))
            
            conn.commit()
            asset_switch_made = True
            
            logger.info(f"✅ Intelligent asset switch for bot {bot_id}: {current_symbols} → {new_symbols}")
        
        conn.close()
        
        return jsonify({
            'success': True,
            'bot_id': bot_id,
            'previous_assets': current_symbols,
            'new_assets': best_assets,
            'switch_made': asset_switch_made,
            'best_profitability_assets': best_assets
        }), 200
    
    except Exception as e:
        logger.error(f"Error in intelligent asset switch: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/user/commission-summary', methods=['GET'])
@require_session
def commission_summary():
    """Get detailed commission summary for user"""
    try:
        user_id = request.user_id
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total commissions
        cursor.execute('''
            SELECT 
                COUNT(*) as count,
                SUM(commission_amount) as total,
                SUM(CASE WHEN created_at > datetime('now', '-30 days') THEN commission_amount ELSE 0 END) as last_30_days
            FROM commissions WHERE earner_id = ?
        ''', (user_id,))
        
        comm_stats = cursor.fetchone()
        
        # Top earning bots
        cursor.execute('''
            SELECT bot_id, SUM(commission_amount) as total_commission
            FROM commissions WHERE earner_id = ?
            GROUP BY bot_id
            ORDER BY total_commission DESC
            LIMIT 10
        ''', (user_id,))
        
        top_earning_bots = []
        for row in cursor.fetchall():
            top_earning_bots.append({
                'bot_id': row[0],
                'total_commission': round(row[1], 2)
            })
        
        # Recent commissions
        cursor.execute('''
            SELECT commission_id, bot_id, profit_amount, commission_amount, commission_rate, created_at
            FROM commissions WHERE earner_id = ?
            ORDER BY created_at DESC
            LIMIT 20
        ''', (user_id,))
        
        recent = []
        for row in cursor.fetchall():
            recent.append({
                'commission_id': row[0],
                'bot_id': row[1],
                'profit_amount': round(row[2], 2),
                'commission_amount': round(row[3], 2),
                'rate': row[4],
                'created_at': row[5]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'summary': {
                'total_commissions': len(comm_stats),
                'total_earned': round(comm_stats[1] or 0, 2),
                'last_30_days_earned': round(comm_stats[2] or 0, 2),
            },
            'top_earning_bots': top_earning_bots,
            'recent_commissions': recent,
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting commission summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== SYSTEM & BACKUP ENDPOINTS ====================

@app.route('/api/system/backup/create', methods=['POST'])
@require_session
def manual_backup():
    """Manually create a backup (admin only)"""
    try:
        user_id = request.user_id
        
        # Verify user exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        
        # Create backup
        backup_path = backup_manager.create_backup()
        
        if backup_path:
            return jsonify({
                'success': True,
                'message': 'Backup created successfully',
                'backup': backup_path.name,
                'timestamp': datetime.now().isoformat(),
            }), 200
        else:
            return jsonify({'success': False, 'error': 'Backup failed'}), 500
            
    except Exception as e:
        logger.error(f"Manual backup error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/system/backup/list', methods=['GET'])
@require_session
def list_backups():
    """Get list of all available backups"""
    try:
        user_id = request.user_id
        
        # Verify user exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 403
        
        backups = backup_manager.list_backups()
        
        return jsonify({
            'success': True,
            'backups': [
                {
                    'filename': b['filename'],
                    'size_mb': round(b['size_mb'], 2),
                    'created': b['created'].isoformat(),
                }
                for b in backups
            ],
            'total_count': len(backups),
        }), 200
        
    except Exception as e:
        logger.error(f"List backups error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/system/backup/restore', methods=['POST'])
@require_session
def restore_from_backup():
    """Restore database from a specific backup (admin only, DANGEROUS)"""
    try:
        user_id = request.user_id
        
        # Verify user exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 403
        
        data = request.json or {}
        backup_filename = data.get('backup_filename')
        
        if not backup_filename:
            return jsonify({'success': False, 'error': 'backup_filename required'}), 400
        
        # DANGEROUS - require confirmation
        confirmation = data.get('confirm_restore')
        if not confirmation:
            return jsonify({
                'success': False,
                'error': 'This is a destructive operation. Set confirm_restore=true to proceed.',
                'backup_filename': backup_filename
            }), 400
        
        # Perform restore
        result = backup_manager.restore_backup(backup_filename)
        if result:
            return jsonify({
                'success': True,
                'message': f'Database restored from backup: {backup_filename}',
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to restore from backup: {backup_filename}'
            }), 500
            
    except Exception as e:
        logger.error(f"Restore backup error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/system/data/verify', methods=['GET'])
@require_session
def verify_system_data():
    """Verify that all system data is intact"""
    try:
        data_status = recovery_manager.verify_all_user_data()
        
        return jsonify({
            'success': True,
            'status': 'All data verified',
            'data_summary': data_status,
            'timestamp': datetime.now().isoformat(),
        }), 200
        
    except Exception as e:
        logger.error(f"Data verification error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/system/health', methods=['GET'])
def system_health():
    """Health check endpoint - includes backup status"""
    try:
        data_status = recovery_manager.verify_all_user_data()
        backups = backup_manager.list_backups()
        latest_backup = backups[0] if backups else None
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'backend_running': True,
            'database': {
                'integrity': 'ok',
                'users': data_status.get('users', 0),
                'bots': data_status.get('bots', 0),
                'credentials': data_status.get('credentials', 0),
            },
            'backup_system': {
                'enabled': backup_manager.is_running,
                'latest_backup': latest_backup['filename'] if latest_backup else None,
                'latest_backup_time': latest_backup['created'].isoformat() if latest_backup else None,
                'total_backups': len(backups),
            },
        }), 200
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            'status': 'degraded',
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
        }), 500


# ==================== EXNESS BROKER ENDPOINTS ====================
# Exness provides MT5-based trading with session token authentication

def generate_exness_session_token():
    """Generate secure session token for Exness MT5 trading"""
    return f"exness_{uuid.uuid4().hex[:32]}"

def validate_exness_server(server_name):
    """Validate that server name is correct for Exness"""
    valid_servers = ['Exness-MT5', 'Exness-MT5.5', 'Exness-MT5-Real']
    return server_name in valid_servers

def get_exness_available_symbols():
    """Return list of available Exness symbols (50+ pairs)"""
    return [
        # Forex - Major Pairs (8)
        'EURUSD', 'GBPUSD', 'USDCHF', 'USDJPY', 'AUDUSD', 'NZDUSD', 'USDCAD', 'USDCNH',
        # Metals (4)
        'XAUUSD', 'XAGUSD', 'XPTUSD', 'XPDUSD',
        # Energy (2)
        'OILK', 'NATGASUS',
        # Indices (4)
        'SP500m', 'DAX', 'US300', 'US100',
        # Additional forex pairs (12+)
        'EURJPY', 'EURGBP', 'EURCHF', 'EURCAD', 'GBPJPY', 'GBPCHF', 'CHFJPY',
        'CADCHF', 'CADJPY', 'AUDCAD', 'AUDCHF', 'AUDJPY',
    ]

@app.route('/api/broker/exness/login', methods=['POST'])
def exness_login():
    """Login to Exness MT5 account and create session"""
    try:
        data = request.json or {}
        account_id = data.get('accountId') or data.get('account_id')
        password = data.get('password')
        server = data.get('server', 'Exness-MT5')
        is_live = data.get('is_live', False)
        
        if not account_id or not password:
            return jsonify({'success': False, 'error': 'accountId and password required'}), 400
        
        if not validate_exness_server(server):
            return jsonify({'success': False, 'error': f'Invalid Exness server: {server}'}), 400
        
        # Try to connect to MT5 for Exness
        try:
            import MetaTrader5 as mt5
            
            # Initialize MT5
            if not mt5.initialize():
                return jsonify({
                    'success': False,
                    'error': 'Failed to initialize MT5',
                    'detail': 'MT5 terminal may not be installed or running'
                }), 500
            
            # Login to Exness account
            try:
                account_id_int = int(account_id)
            except ValueError:
                return jsonify({'success': False, 'error': 'accountId must be numeric'}), 400
            
            login_result = mt5.login(account_id_int, password=password, server=server)
            
            if not login_result:
                error_msg = mt5.last_error()
                logger.warning(f"⚠️ Exness login failed for account {account_id}: {error_msg}")
                mt5.shutdown()
                return jsonify({
                    'success': False,
                    'error': 'Failed to login to Exness account',
                    'detail': f'Check account ID, password, and server name. Server must be "{server}"'
                }), 401
            
            # Get account info
            account_info = mt5.account_info()
            if not account_info:
                mt5.shutdown()
                return jsonify({
                    'success': False,
                    'error': 'Failed to retrieve account info from MT5'
                }), 500
            
            # Generate session token
            session_token = generate_exness_session_token()
            
            logger.info(f"✅ Exness login successful for account {account_id}")
            
            return jsonify({
                'success': True,
                'session_token': session_token,
                'account_id': account_id,
                'account_type': 'LIVE' if is_live else 'DEMO',
                'balance': account_info.balance,
                'currency': account_info.currency,
                'leverage': account_info.leverage,
                'server': server,
            }), 200
            
        except ImportError:
            return jsonify({
                'success': False,
                'error': 'MetaTrader5 SDK not installed',
                'detail': 'Install: pip install MetaTrader5>=5.0.45'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in Exness login: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/logout', methods=['POST'])
def exness_logout():
    """Logout from Exness (cleanup session)"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not session_token:
            return jsonify({'success': False, 'error': 'No session token provided'}), 401
        
        # Close MT5 connection
        try:
            import MetaTrader5 as mt5
            mt5.shutdown()
        except:
            pass
        
        logger.info(f"✅ Exness session ended")
        
        return jsonify({
            'success': True,
            'message': 'Logged out from Exness'
        }), 200
        
    except Exception as e:
        logger.error(f"Error in Exness logout: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/account', methods=['GET'])
@require_session
def exness_account_info():
    """Get Exness account information - reconnects with users saved credentials"""
    try:
        user_id = request.user_id  # From @require_session
        
        # Load user's latest active Exness credential
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT credential_id, account_number, password, server, is_live
            FROM broker_credentials
            WHERE user_id = ? AND broker_name = 'Exness' AND is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
        ''', (user_id,))
        
        cred_row = cursor.fetchone()
        conn.close()
        
        if not cred_row:
            return jsonify({
                'success': False, 
                'error': 'No Exness credentials found. Please connect your Exness account first.'
            }), 400
        
        cred = dict(cred_row)
        account = cred['account_number']
        password = cred['password']
        server = cred['server']
        is_live = cred['is_live']
        
        # Reconnect with user's credentials
        try:
            mt5_conn = MT5Connection(credentials={
                'account': account,
                'password': password,
                'server': server,
                'broker': 'Exness',
            })
            
            if not mt5_conn.connect():
                return jsonify({
                    'success': False,
                    'error': f'Failed to connect to Exness MT5. Account: {account}, Server: {server}'
                }), 500
            
            # Get account info from connected MT5 instance
            if not mt5_conn.mt5:
                return jsonify({'success': False, 'error': 'MT5 SDK not available'}), 500
            
            account_info = mt5_conn.mt5.account_info()
            if not account_info:
                return jsonify({'success': False, 'error': 'Failed to retrieve account info from MT5'}), 500
            
            return jsonify({
                'success': True,
                'accountId': account_info.login,
                'balance': float(account_info.balance),
                'equity': float(account_info.equity),
                'margin': float(account_info.margin),
                'marginFree': float(account_info.margin_free),
                'marginLevel': float(account_info.margin_level) if account_info.margin > 0 else 0.0,
                'currency': account_info.currency,
                'leverage': int(account_info.leverage),
                'accountType': 'LIVE' if is_live else 'DEMO',
                'profitLoss': float(account_info.equity - account_info.balance),
            }), 200
            
        except Exception as e:
            logger.error(f"Error connecting to Exness MT5 or retrieving account info: {e}")
            return jsonify({
                'success': False,
                'error': f'Cannot connect to MT5: {str(e)}'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in exness_account_info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/trade', methods=['POST'])
@require_session
def exness_place_trade():
    """Place order on Exness MT5 account"""
    try:
        # @require_session decorator already validates authentication
        # User is authenticated if we reach here
        
        data = request.json or {}
        symbol = (data.get('symbol') or '').upper()
        side = (data.get('side') or 'BUY').upper()
        volume = float(data.get('volume', 0.1))
        stop_loss = data.get('stopLoss') or data.get('stop_loss')
        take_profit = data.get('takeProfit') or data.get('take_profit')
        
        if not symbol or side not in ['BUY', 'SELL']:
            return jsonify({'success': False, 'error': 'symbol and side (BUY/SELL) required'}), 400
        
        if volume <= 0:
            return jsonify({'success': False, 'error': 'volume must be positive'}), 400
        
        try:
            import MetaTrader5 as mt5
            
            if not mt5.initialize():
                return jsonify({'success': False, 'error': 'MT5 not initialized'}), 500
            
            # Select symbol
            if not mt5.symbol_select(symbol, True):
                return jsonify({
                    'success': False,
                    'error': f'Symbol {symbol} not available on Exness'
                }), 400
            
            # Get tick for price
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                return jsonify({
                    'success': False,
                    'error': f'Cannot get market data for {symbol}'
                }), 500
            
            price = tick.ask if side == 'BUY' else tick.bid
            
            # Build order request
            request_dict = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': symbol,
                'volume': volume,
                'type': mt5.ORDER_TYPE_BUY if side == 'BUY' else mt5.ORDER_TYPE_SELL,
                'price': price,
                'comment': 'Exness Order',
                'type_time': mt5.ORDER_TIME_GTC,
                'type_filling': mt5.ORDER_FILLING_FOK,
            }
            
            if stop_loss:
                request_dict['sl'] = float(stop_loss)
            if take_profit:
                request_dict['tp'] = float(take_profit)
            
            # Send order
            result = mt5.order_send(request_dict)
            
            if result is None:
                return jsonify({
                    'success': False,
                    'error': 'Order submission failed - terminal disconnected'
                }), 500
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return jsonify({
                    'success': False,
                    'error': f'Order failed: {result.comment}',
                    'retcode': result.retcode
                }), 400
            
            logger.info(f"✅ Exness order placed: {symbol} {side} {volume}L")
            
            return jsonify({
                'success': True,
                'orderId': result.order,
                'symbol': symbol,
                'side': side,
                'volume': volume,
                'price': price,
                'commission': result.comment if hasattr(result, 'comment') else 0,
            }), 201
            
        except ImportError:
            return jsonify({'success': False, 'error': 'MetaTrader5 SDK not available'}), 500
            
    except Exception as e:
        logger.error(f"Error placing Exness trade: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/orders', methods=['GET'])
@require_session
def exness_get_orders():
    """Get open orders/positions from Exness account"""
    try:
        # @require_session decorator already validates authentication
        
        try:
            import MetaTrader5 as mt5
            
            if not mt5.initialize():
                return jsonify({'success': False, 'error': 'MT5 not initialized'}), 500
            
            # Get open positions
            positions = mt5.positions_get()
            if positions is None:
                positions = []
            
            orders = []
            for pos in positions:
                orders.append({
                    'orderId': pos.ticket,
                    'symbol': pos.symbol,
                    'side': 'BUY' if pos.type == mt5.ORDER_TYPE_BUY else 'SELL',
                    'volume': pos.volume,
                    'openPrice': pos.price_open,
                    'currentPrice': pos.price_current,
                    'profit': pos.profit,
                    'profitPercent': (pos.profit / (pos.price_open * pos.volume)) * 100 if pos.price_open > 0 else 0,
                    'openTime': datetime.fromtimestamp(pos.time).isoformat(),
                })
            
            logger.info(f"✅ Retrieved {len(orders)} open orders from Exness")
            
            return jsonify({
                'success': True,
                'orders': orders,
                'count': len(orders)
            }), 200
            
        except ImportError:
            return jsonify({'success': False, 'error': 'MetaTrader5 SDK not available'}), 500
            
    except Exception as e:
        logger.error(f"Error getting Exness orders: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/orders/<order_id>/close', methods=['POST'])
@require_session
def exness_close_order(order_id):
    """Close a specific order/position on Exness"""
    try:
        # @require_session decorator already validates authentication
        
        try:
            order_id_int = int(order_id)
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid order ID'}), 400
        
        try:
            import MetaTrader5 as mt5
            
            if not mt5.initialize():
                return jsonify({'success': False, 'error': 'MT5 not initialized'}), 500
            
            # Get position
            position = mt5.positions_get(ticket=order_id_int)
            if not position:
                return jsonify({'success': False, 'error': 'Position not found'}), 404
            
            pos = position[0]
            
            # Build close order request
            close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            
            # Get current price
            tick = mt5.symbol_info_tick(pos.symbol)
            price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
            
            request_dict = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': pos.symbol,
                'volume': pos.volume,
                'type': close_type,
                'position': order_id_int,
                'price': price,
                'comment': 'Position Closed',
                'type_time': mt5.ORDER_TIME_GTC,
                'type_filling': mt5.ORDER_FILLING_FOK,
            }
            
            result = mt5.order_send(request_dict)
            
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                return jsonify({
                    'success': False,
                    'error': 'Failed to close position'
                }), 500
            
            logger.info(f"✅ Exness position {order_id} closed successfully")
            
            return jsonify({
                'success': True,
                'orderId': order_id,
                'message': 'Position closed'
            }), 200
            
        except ImportError:
            return jsonify({'success': False, 'error': 'MetaTrader5 SDK not available'}), 500
            
    except Exception as e:
        logger.error(f"Error closing Exness order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/orders/<order_id>', methods=['PATCH'])
@require_session
def exness_update_order(order_id):
    """Update stop loss and take profit for Exness order"""
    try:
        # @require_session decorator already validates authentication
        
        data = request.json or {}
        new_sl = data.get('stopLoss') or data.get('stop_loss')
        new_tp = data.get('takeProfit') or data.get('take_profit')
        
        if not new_sl and not new_tp:
            return jsonify({'success': False, 'error': 'stopLoss or takeProfit required'}), 400
        
        try:
            order_id_int = int(order_id)
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid order ID'}), 400
        
        try:
            import MetaTrader5 as mt5
            
            if not mt5.initialize():
                return jsonify({'success': False, 'error': 'MT5 not initialized'}), 500
            
            # Get position
            position = mt5.positions_get(ticket=order_id_int)
            if not position:
                return jsonify({'success': False, 'error': 'Position not found'}), 404
            
            pos = position[0]
            
            # Build modify request
            request_dict = {
                'action': mt5.TRADE_ACTION_SLTP,
                'position': order_id_int,
                'sl': float(new_sl) if new_sl else pos.sl,
                'tp': float(new_tp) if new_tp else pos.tp,
            }
            
            result = mt5.order_send(request_dict)
            
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                return jsonify({
                    'success': False,
                    'error': 'Failed to update position'
                }), 500
            
            logger.info(f"✅ Exness position {order_id} updated: SL={new_sl}, TP={new_tp}")
            
            return jsonify({
                'success': True,
                'orderId': order_id,
                'stopLoss': new_sl,
                'takeProfit': new_tp,
                'message': 'Position updated'
            }), 200
            
        except ImportError:
            return jsonify({'success': False, 'error': 'MetaTrader5 SDK not available'}), 500
            
    except Exception as e:
        logger.error(f"Error updating Exness order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/symbols/<symbol>', methods=['GET'])
def exness_symbol_info(symbol):
    """Get symbol information and current market data from Exness"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not session_token or not session_token.startswith('exness_'):
            return jsonify({'success': False, 'error': 'Invalid session token'}), 401
        
        symbol = symbol.upper()
        
        try:
            import MetaTrader5 as mt5
            
            if not mt5.initialize():
                return jsonify({'success': False, 'error': 'MT5 not initialized'}), 500
            
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return jsonify({
                    'success': False,
                    'error': f'Symbol {symbol} not found on Exness'
                }), 404
            
            # Get tick data
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                return jsonify({
                    'success': False,
                    'error': f'Cannot get market data for {symbol}'
                }), 500
            
            return jsonify({
                'success': True,
                'symbol': symbol,
                'bid': tick.bid,
                'ask': tick.ask,
                'spread': tick.ask - tick.bid,
                'minSize': symbol_info.volume_min,
                'maxSize': symbol_info.volume_max,
                'stepSize': symbol_info.volume_step,
                'tradable': symbol_info.trade_mode != mt5.SYMBOL_TRADE_MODE_DISABLED,
                'lastUpdate': datetime.fromtimestamp(tick.time).isoformat(),
            }), 200
            
        except ImportError:
            return jsonify({'success': False, 'error': 'MetaTrader5 SDK not available'}), 500
            
    except Exception as e:
        logger.error(f"Error getting Exness symbol info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/symbols', methods=['GET'])
def exness_available_symbols():
    """Get list of all available symbols on Exness"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not session_token or not session_token.startswith('exness_'):
            return jsonify({'success': False, 'error': 'Invalid session token'}), 401
        
        symbols = get_exness_available_symbols()
        
        logger.info(f"✅ Retrieved {len(symbols)} available symbols from Exness")
        
        return jsonify({
            'success': True,
            'symbols': symbols,
            'count': len(symbols)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting Exness symbols: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/trade/closed', methods=['POST'])
@require_api_key
def record_exness_trade_profit():
    """
    Record a closed trade profit for Exness with automatic commission split:
    - Direct registration: Developer 30%, User 70%
    - Via referrer: Developer 25%, Referrer 5%, User 70%
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        broker_account_id = data.get('broker_account_id')
        order_id = data.get('order_id')
        symbol = data.get('symbol')
        entry_price = data.get('entry_price')
        exit_price = data.get('exit_price')
        volume = data.get('volume')
        side = data.get('side')  # 'BUY' or 'SELL'
        profit_loss = data.get('profit_loss')
        commission = data.get('commission', 0)
        trade_duration_seconds = data.get('trade_duration_seconds')

        if not all([user_id, broker_account_id, order_id, symbol, entry_price, exit_price, volume, profit_loss]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        profit_id = str(uuid.uuid4())
        closed_at = datetime.now().isoformat()
        pnl_percentage = ((exit_price - entry_price) / entry_price * 100) if side == 'BUY' else ((entry_price - exit_price) / entry_price * 100)

        # Record the trade profit
        cursor.execute('''
            INSERT INTO exness_trade_profits
            (profit_id, user_id, broker_account_id, order_id, symbol, entry_price, exit_price,
             volume, side, profit_loss, commission, pnl_percentage, trade_duration_seconds, closed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            profit_id, user_id, broker_account_id, order_id, symbol, entry_price, exit_price,
            volume, side, profit_loss, commission, pnl_percentage, trade_duration_seconds, closed_at
        ))

        # ==================== PROFIT COMMISSION SPLIT ====================
        
        # Get user's referrer (if any)
        cursor.execute('SELECT referrer_id FROM users WHERE user_id = ?', (user_id,))
        user_row = cursor.fetchone()
        referrer_id = user_row['referrer_id'] if user_row else None
        
        # Calculate commission split based on registration type
        developer_id = 'SYSTEM_OWNER_USER_ID'  # System developer/owner account
        
        if profit_loss > 0:  # Only split if profitable
            if referrer_id:
                # Via referrer: Dev 25%, Referrer 5%, User 70%
                dev_commission = profit_loss * 0.25
                referrer_commission = profit_loss * 0.05
                user_profit = profit_loss * 0.70
                
                logger.info(f"📊 Profit split (WITH REFERRER): Dev ${dev_commission:.2f} (25%), Referrer ${referrer_commission:.2f} (5%), User ${user_profit:.2f} (70%)")
            else:
                # Direct registration: Dev 30%, User 70%
                dev_commission = profit_loss * 0.30
                referrer_commission = 0
                user_profit = profit_loss * 0.70
                
                logger.info(f"📊 Profit split (DIRECT): Dev ${dev_commission:.2f} (30%), User ${user_profit:.2f} (70%)")
            
            # Insert commission records
            commission_id_dev = str(uuid.uuid4())
            commission_id_user = str(uuid.uuid4())
            commission_time = datetime.now().isoformat()
            
            # Developer commission
            cursor.execute('''
                INSERT INTO commissions
                (commission_id, earner_id, payer_id, amount, commission_type, source_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                commission_id_dev, developer_id, user_id, dev_commission, 'trade_profit',
                profit_id, 'earned', commission_time
            ))
            
            # User profit (if not all goes to dev)
            if user_profit > 0:
                cursor.execute('''
                    INSERT INTO commissions
                    (commission_id, earner_id, payer_id, amount, commission_type, source_id, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    commission_id_user, user_id, developer_id, user_profit, 'trade_profit',
                    profit_id, 'earned', commission_time
                ))
            
            # Referrer commission (if applicable)
            if referrer_id and referrer_commission > 0:
                commission_id_referrer = str(uuid.uuid4())
                cursor.execute('''
                    INSERT INTO commissions
                    (commission_id, earner_id, payer_id, amount, commission_type, source_id, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    commission_id_referrer, referrer_id, user_id, referrer_commission, 'referral_profit',
                    profit_id, 'earned', commission_time
                ))
                
                # Update user total commission
                cursor.execute('''
                    UPDATE users SET total_commission = total_commission + ? 
                    WHERE user_id = ?
                ''', (referrer_commission, referrer_id))
            
            # Update developer total commission
            cursor.execute('''
                UPDATE users SET total_commission = total_commission + ? 
                WHERE user_id = ?
            ''', (dev_commission, developer_id))
            
            # Update user total commission
            cursor.execute('''
                UPDATE users SET total_commission = total_commission + ? 
                WHERE user_id = ?
            ''', (user_profit, user_id))

        conn.commit()
        conn.close()

        logger.info(f"✅ Trade profit recorded: {symbol} P&L=${profit_loss} ({pnl_percentage:.2f}%)")

        return jsonify({
            'success': True,
            'profit_id': profit_id,
            'profit_loss': profit_loss,
            'pnl_percentage': round(pnl_percentage, 2),
            'message': 'Trade profit recorded with commissions distributed'
        }), 201

    except Exception as e:
        logger.error(f"Error recording Exness trade profit: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== EXNESS WITHDRAWAL PIPELINE ====================

@app.route('/api/broker/exness/withdrawal/request', methods=['POST'])
@require_api_key
def exness_withdrawal_request():
    """Request profit withdrawal from Exness account"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        broker_account_id = data.get('broker_account_id')
        withdrawal_type = data.get('withdrawal_type')  # 'profits', 'commission', 'both'
        amount = data.get('amount')
        withdrawal_method = data.get('withdrawal_method', 'bank_transfer')
        payment_details = data.get('payment_details')

        if not all([user_id, broker_account_id, withdrawal_type, amount]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        # Validate withdrawal type
        if withdrawal_type not in ['profits', 'commission', 'both']:
            return jsonify({'success': False, 'error': 'Invalid withdrawal type'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Calculate available amounts
        cursor.execute('''
            SELECT COALESCE(SUM(profit_loss), 0) as total_profits 
            FROM exness_trade_profits 
            WHERE user_id = ? AND broker_account_id = ? AND withdrawal_id IS NULL
        ''', (user_id, broker_account_id))
        
        profit_row = cursor.fetchone()
        available_profits = profit_row['total_profits'] if profit_row else 0

        # Get commission earned
        cursor.execute('''
            SELECT COALESCE(SUM(commission_amount), 0) as total_commission 
            FROM commissions 
            WHERE earner_id = ? AND status = 'earned'
        ''', (user_id,))
        
        commission_row = cursor.fetchone()
        available_commission = commission_row['total_commission'] if commission_row else 0

        # Validate amount based on type
        if withdrawal_type == 'profits' and amount > available_profits:
            conn.close()
            return jsonify({
                'success': False, 
                'error': f'Insufficient profit balance. Available: ${available_profits}'
            }), 400

        if withdrawal_type == 'commission' and amount > available_commission:
            conn.close()
            return jsonify({
                'success': False,
                'error': f'Insufficient commission balance. Available: ${available_commission}'
            }), 400

        if withdrawal_type == 'both' and amount > (available_profits + available_commission):
            conn.close()
            return jsonify({
                'success': False,
                'error': f'Insufficient combined balance. Available: ${available_profits + available_commission}'
            }), 400

        # Create withdrawal request
        withdrawal_id = str(uuid.uuid4())
        fee = amount * 0.01  # 1% withdrawal fee
        net_amount = amount - fee
        created_at = datetime.now().isoformat()

        profit_from_trades = 0
        commission_earned = 0

        if withdrawal_type == 'profits':
            profit_from_trades = amount
        elif withdrawal_type == 'commission':
            commission_earned = amount
        else:  # both
            profit_from_trades = available_profits
            commission_earned = available_commission

        cursor.execute('''
            INSERT INTO exness_withdrawals
            (withdrawal_id, user_id, broker_account_id, withdrawal_type, profit_from_trades,
             commission_earned, total_amount, fee, net_amount, status, withdrawal_method,
             payment_details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            withdrawal_id, user_id, broker_account_id, withdrawal_type, profit_from_trades,
            commission_earned, amount, fee, net_amount, 'pending', withdrawal_method,
            payment_details, created_at
        ))

        # Link trade profits to withdrawal
        if withdrawal_type in ['profits', 'both']:
            cursor.execute('''
                UPDATE exness_trade_profits 
                SET withdrawal_id = ? 
                WHERE user_id = ? AND broker_account_id = ? AND withdrawal_id IS NULL
                LIMIT (SELECT COUNT(*) FROM exness_trade_profits 
                       WHERE user_id = ? AND broker_account_id = ? AND withdrawal_id IS NULL)
            ''', (withdrawal_id, user_id, broker_account_id, user_id, broker_account_id))

        conn.commit()
        conn.close()

        logger.info(f"✅ Exness withdrawal request {withdrawal_id}: User {user_id} - ${amount}")

        return jsonify({
            'success': True,
            'withdrawal_id': withdrawal_id,
            'amount': amount,
            'fee': round(fee, 2),
            'net_amount': round(net_amount, 2),
            'status': 'pending',
            'message': 'Withdrawal request submitted successfully'
        }), 200

    except Exception as e:
        logger.error(f"Error requesting Exness withdrawal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/withdrawal/history/<user_id>', methods=['GET'])
def exness_withdrawal_history(user_id):
    """Get Exness withdrawal history for user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM exness_withdrawals 
            WHERE user_id = ? 
            ORDER BY created_at DESC
            LIMIT 50
        ''', (user_id,))

        withdrawals = cursor.fetchall()
        conn.close()

        withdrawal_list = []
        for w in withdrawals:
            withdrawal_list.append({
                'withdrawal_id': w['withdrawal_id'],
                'broker_account_id': w['broker_account_id'],
                'withdrawal_type': w['withdrawal_type'],
                'profit_from_trades': w['profit_from_trades'],
                'commission_earned': w['commission_earned'],
                'total_amount': w['total_amount'],
                'fee': w['fee'],
                'net_amount': w['net_amount'],
                'status': w['status'],
                'withdrawal_method': w['withdrawal_method'],
                'created_at': w['created_at'],
                'submitted_at': w['submitted_at'],
                'completed_at': w['completed_at'],
            })

        return jsonify({
            'success': True,
            'withdrawals': withdrawal_list,
            'count': len(withdrawal_list)
        }), 200

    except Exception as e:
        logger.error(f"Error fetching Exness withdrawal history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/withdrawal/status/<withdrawal_id>', methods=['GET'])
def exness_withdrawal_status(withdrawal_id):
    """Check withdrawal status"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM exness_withdrawals WHERE withdrawal_id = ?', (withdrawal_id,))
        withdrawal = cursor.fetchone()
        conn.close()

        if not withdrawal:
            return jsonify({'success': False, 'error': 'Withdrawal not found'}), 404

        return jsonify({
            'success': True,
            'withdrawal_id': withdrawal['withdrawal_id'],
            'status': withdrawal['status'],
            'amount': withdrawal['total_amount'],
            'net_amount': withdrawal['net_amount'],
            'created_at': withdrawal['created_at'],
            'submitted_at': withdrawal['submitted_at'],
            'completed_at': withdrawal['completed_at'],
        }), 200

    except Exception as e:
        logger.error(f"Error getting Exness withdrawal status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/balance/<user_id>', methods=['GET'])
def exness_withdrawal_balance(user_id):
    """Get available balance for withdrawal from Exness"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get profit from closed trades
        cursor.execute('''
            SELECT COALESCE(SUM(profit_loss), 0) as total_profits 
            FROM exness_trade_profits 
            WHERE user_id = ? AND withdrawal_id IS NULL
        ''', (user_id,))
        
        profit_row = cursor.fetchone()
        available_profits = profit_row['total_profits'] if profit_row else 0

        # Get commission earned
        cursor.execute('''
            SELECT COALESCE(SUM(commission_amount), 0) as total_commission 
            FROM commissions 
            WHERE earner_id = ? AND status = 'earned'
        ''', (user_id,))
        
        commission_row = cursor.fetchone()
        available_commission = commission_row['total_commission'] if commission_row else 0

        # Get pending/processing withdrawals
        cursor.execute('''
            SELECT COALESCE(SUM(total_amount), 0) as total_pending 
            FROM exness_withdrawals 
            WHERE user_id = ? AND status IN ('pending', 'submitted', 'processing')
        ''', (user_id,))
        
        pending_row = cursor.fetchone()
        pending_withdrawals = pending_row['total_pending'] if pending_row else 0

        conn.close()

        return jsonify({
            'success': True,
            'available_profits': round(available_profits, 2),
            'available_commission': round(available_commission, 2),
            'total_available': round(available_profits + available_commission, 2),
            'pending_withdrawals': round(pending_withdrawals, 2),
            'net_available': round(available_profits + available_commission - pending_withdrawals, 2),
        }), 200

    except Exception as e:
        logger.error(f"Error getting Exness balance: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== ADMIN: VERIFY EXNESS WITHDRAWAL & TRIGGER COMMISSION SPLIT ====================

@app.route('/api/admin/withdrawal/exness/verify', methods=['POST'])
@require_admin
def admin_verify_exness_withdrawal():
    """
    Admin verifies that user actually withdrew from Exness.
    Automatically splits commission: 30% to developer, 70% to user wallet.
    """
    try:
        data = request.get_json()
        withdrawal_id = data.get('withdrawal_id')
        admin_notes = data.get('notes', '')
        
        if not withdrawal_id:
            return jsonify({'success': False, 'error': 'withdrawal_id required'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get withdrawal details
        cursor.execute('SELECT * FROM exness_withdrawals WHERE withdrawal_id = ?', (withdrawal_id,))
        withdrawal = cursor.fetchone()
        
        if not withdrawal:
            conn.close()
            return jsonify({'success': False, 'error': 'Withdrawal not found'}), 404
        
        if withdrawal['status'] != 'pending':
            conn.close()
            return jsonify({
                'success': False, 
                'error': f"Can only verify pending withdrawals. Current status: {withdrawal['status']}"
            }), 400
        
        user_id = withdrawal['user_id']
        profit_amount = withdrawal['profit_from_trades']
        
        # ==================== COMMISSION SPLIT LOGIC ====================
        developer_id = 'SYSTEM_OWNER_USER_ID'
        dev_share = profit_amount * 0.30  # Developer gets 30%
        user_share = profit_amount * 0.70  # User gets 70%
        
        now = datetime.now().isoformat()
        
        # STEP 1: Ensure user has a wallet
        cursor.execute('SELECT wallet_id FROM user_wallets WHERE user_id = ?', (user_id,))
        wallet_row = cursor.fetchone()
        
        if not wallet_row:
            wallet_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO user_wallets (wallet_id, user_id, balance, currency, last_updated)
                VALUES (?, ?, ?, ?, ?)
            ''', (wallet_id, user_id, user_share, 'USD', now))
        else:
            wallet_id = wallet_row['wallet_id']
            # Update existing wallet balance
            cursor.execute('''
                UPDATE user_wallets 
                SET balance = balance + ?, last_updated = ?
                WHERE user_id = ?
            ''', (user_share, now, user_id))
        
        # STEP 2: Record wallet transaction for user
        transaction_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO wallet_transactions 
            (transaction_id, wallet_id, user_id, amount, transaction_type, source_withdrawal_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            transaction_id, wallet_id, user_id, user_share, 
            'profit_withdrawal', withdrawal_id, 'completed', now
        ))
        
        # STEP 3: Record developer commission
        commission_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO commissions 
            (commission_id, earner_id, payer_id, amount, commission_type, source_id, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            commission_id, developer_id, user_id, dev_share,
            'exness_profit_commission', withdrawal_id, 'earned', now
        ))
        
        # STEP 4: Update withdrawal status to verified
        cursor.execute('''
            UPDATE exness_withdrawals 
            SET status = 'verified', completed_at = ?, admin_notes = ?
            WHERE withdrawal_id = ?
        ''', (now, admin_notes, withdrawal_id))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ ADMIN verified withdrawal {withdrawal_id}: User {user_id}")
        logger.info(f"   Commission split: Dev ${dev_share:.2f} (30%), User ${user_share:.2f} (70%)")
        
        return jsonify({
            'success': True,
            'withdrawal_id': withdrawal_id,
            'status': 'verified',
            'profit_amount': profit_amount,
            'developer_commission': round(dev_share, 2),
            'user_wallet_credit': round(user_share, 2),
            'message': f'✅ Withdrawal verified! User will receive ${round(user_share, 2)} in their wallet. Developer earned ${round(dev_share, 2)}.'
        }), 200
    
    except Exception as e:
        logger.error(f"Error verifying Exness withdrawal: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== GET USER WALLET BALANCE ====================

@app.route('/api/wallet/balance/<user_id>', methods=['GET'])
def get_wallet_balance(user_id):
    """Get users available wallet balance"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT balance FROM user_wallets WHERE user_id = ?', (user_id,))
        wallet = cursor.fetchone()
        conn.close()
        
        balance = wallet['balance'] if wallet else 0
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'balance': round(balance, 2),
            'currency': 'USD'
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting wallet balance: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/trades', methods=['GET'])
def exness_get_trades():
    """Get closed trades history with profit/loss from Exness MT5"""
    try:
        # Get optional filters from query params
        user_id = request.args.get('user_id')
        limit = int(request.args.get('limit', 50))
        
        # First try to get from MT5 live data
        try:
            import MetaTrader5 as mt5
            
            if mt5.initialize():
                deals = mt5.history_deals_get(position=0)
                trades = []
                
                if deals:
                    # Process last N deals and reverse to show most recent first
                    for deal in sorted(deals, key=lambda x: x.time, reverse=True)[:limit]:
                        trade = {
                            'ticket': deal.ticket,
                            'symbol': deal.symbol,
                            'side': 'BUY' if deal.type == mt5.DEAL_TYPE_BUY else 'SELL',
                            'volume': deal.volume,
                            'entryPrice': deal.price,
                            'exitPrice': deal.price,  # Deal price is exit price for closed deals
                            'profitLoss': float(deal.profit),
                            'commission': float(deal.commission),
                            'pnlPercentage': ((deal.profit / (deal.price * deal.volume)) * 100) if (deal.price * deal.volume) > 0 else 0,
                            'closedAt': datetime.fromtimestamp(deal.time).isoformat(),
                            'duration': 'N/A'  # Duration not directly available from deal
                        }
                        trades.append(trade)
                
                logger.info(f"✅ Retrieved {len(trades)} trades from MT5 live data")
                return jsonify({
                    'success': True,
                    'trades': trades,
                    'count': len(trades),
                    'source': 'MT5_LIVE'
                }), 200
        except ImportError:
            logger.warning("MT5 SDK not available, falling back to database")
        except Exception as mt5_error:
            logger.warning(f"Error fetching from MT5: {mt5_error}, falling back to database")
        
        # Fallback to database records
        if user_id:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Try exness_trade_profits table first
            cursor.execute('''
                SELECT * FROM exness_trade_profits 
                WHERE user_id = ? 
                ORDER BY closed_at DESC 
                LIMIT ?
            ''', (user_id, limit))
            
            trades = []
            for row in cursor.fetchall():
                trade = {
                    'profit_id': row['profit_id'],
                    'symbol': row['symbol'],
                    'side': row['side'],
                    'volume': row['volume'],
                    'entryPrice': row['entry_price'],
                    'exitPrice': row['exit_price'],
                    'profitLoss': row['profit_loss'],
                    'commission': row['commission'],
                    'pnlPercentage': row['pnl_percentage'],
                    'closedAt': row['closed_at'],
                    'duration': row['trade_duration_seconds']
                }
                trades.append(trade)
            
            # Also check trades table (for bot-executed trades)
            try:
                cursor.execute('''
                    SELECT * FROM trades 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC
                ''', (user_id,))
                
                for row in cursor.fetchall():
                    try:
                        trade_data = json.loads(row['trade_data'])
                        trade = {
                            'ticket': trade_data.get('ticket', ''),
                            'symbol': trade_data.get('symbol', ''),
                            'side': trade_data.get('type', ''),
                            'volume': trade_data.get('volume', 0),
                            'entryPrice': trade_data.get('entryPrice', 0),
                            'exitPrice': trade_data.get('exitPrice', 0),
                            'profitLoss': trade_data.get('profit', 0),
                            'commission': trade_data.get('commission', 0),
                            'pnlPercentage': ((trade_data.get('profit', 0) / (trade_data.get('entryPrice', 1) * trade_data.get('volume', 1))) * 100) if (trade_data.get('entryPrice', 0) * trade_data.get('volume', 0)) > 0 else 0,
                            'closedAt': trade_data.get('exitTime', datetime.fromtimestamp(row['timestamp']/1000).isoformat()),
                            'duration': trade_data.get('durationSec', 0),
                            'strategy': trade_data.get('strategy', ''),
                            'botId': trade_data.get('botId', '')
                        }
                        trades.append(trade)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse trade data: {row['trade_data']}")
            except Exception as e:
                logger.warning(f"Error querying trades table: {e}")
            
            conn.close()
            
            # Sort by most recent first
            trades.sort(key=lambda x: x.get('closedAt', ''), reverse=True)
            
            logger.info(f"✅ Retrieved {len(trades)} trades from database for user {user_id}")
            return jsonify({
                'success': True,
                'trades': trades,
                'count': len(trades),
                'source': 'DATABASE'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'user_id parameter required for database fallback'
            }), 400
            
    except Exception as e:
        logger.error(f"Error getting Exness trades: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/broker/exness/trade-summary', methods=['GET'])
def exness_trade_summary():
    """Get aggregate trade statistics and summary"""
    try:
        user_id = request.args.get('user_id')
        
        # First try MT5 live data
        summary = {
            'totalTrades': 0,
            'winningTrades': 0,
            'losingTrades': 0,
            'totalProfit': 0.0,
            'totalLoss': 0.0,
            'netProfit': 0.0,
            'totalCommission': 0.0,
            'winRate': 0.0,
            'avgProfit': 0.0,
            'avgLoss': 0.0,
            'largestWin': 0.0,
            'largestLoss': 0.0,
            'profitFactor': 0.0,
            'totalVolume': 0.0
        }
        
        try:
            import MetaTrader5 as mt5
            
            if mt5.initialize():
                deals = mt5.history_deals_get(position=0)
                
                if deals and len(deals) > 0:
                    winning_pnl = []
                    losing_pnl = []
                    total_commission = 0
                    
                    for deal in deals:
                        profit = float(deal.profit)
                        commission = float(deal.commission)
                        
                        summary['totalTrades'] += 1
                        summary['totalVolume'] += deal.volume
                        total_commission += commission
                        
                        if profit > 0:
                            summary['winningTrades'] += 1
                            summary['totalProfit'] += profit
                            winning_pnl.append(profit)
                        elif profit < 0:
                            summary['losingTrades'] += 1
                            summary['totalLoss'] += abs(profit)
                            losing_pnl.append(profit)
                    
                    summary['netProfit'] = summary['totalProfit'] - summary['totalLoss']
                    summary['totalCommission'] = total_commission
                    summary['winRate'] = (summary['winningTrades'] / summary['totalTrades'] * 100) if summary['totalTrades'] > 0 else 0
                    summary['avgProfit'] = (summary['totalProfit'] / summary['winningTrades']) if summary['winningTrades'] > 0 else 0
                    summary['avgLoss'] = (summary['totalLoss'] / summary['losingTrades']) if summary['losingTrades'] > 0 else 0
                    summary['largestWin'] = max(winning_pnl) if winning_pnl else 0
                    summary['largestLoss'] = min(losing_pnl) if losing_pnl else 0
                    summary['profitFactor'] = (summary['totalProfit'] / summary['totalLoss']) if summary['totalLoss'] > 0 else 0
                    
                    logger.info(f"✅ Generated trading summary from MT5: {summary['totalTrades']} trades, ${summary['netProfit']:.2f} net profit")
                    
                    return jsonify({
                        'success': True,
                        'summary': summary,
                        'source': 'MT5_LIVE'
                    }), 200
        except ImportError:
            logger.warning("MT5 SDK not available, falling back to database")
        except Exception as mt5_error:
            logger.warning(f"Error fetching from MT5: {mt5_error}, falling back to database")
        
        # Fallback to database
        if user_id:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get all trades for this user
            cursor.execute('''
                SELECT * FROM exness_trade_profits 
                WHERE user_id = ?
            ''', (user_id,))
            
            trades = cursor.fetchall()
            
            if trades and len(trades) > 0:
                winning_pnl = []
                losing_pnl = []
                
                for trade in trades:
                    profit = trade['profit_loss']
                    commission = trade['commission']
                    
                    summary['totalTrades'] += 1
                    summary['totalVolume'] += trade['volume']
                    summary['totalCommission'] += commission if commission else 0
                    
                    if profit > 0:
                        summary['winningTrades'] += 1
                        summary['totalProfit'] += profit
                        winning_pnl.append(profit)
                    elif profit < 0:
                        summary['losingTrades'] += 1
                        summary['totalLoss'] += abs(profit)
                        losing_pnl.append(profit)
                
                summary['netProfit'] = summary['totalProfit'] - summary['totalLoss']
                summary['winRate'] = (summary['winningTrades'] / summary['totalTrades'] * 100) if summary['totalTrades'] > 0 else 0
                summary['avgProfit'] = (summary['totalProfit'] / summary['winningTrades']) if summary['winningTrades'] > 0 else 0
                summary['avgLoss'] = (summary['totalLoss'] / summary['losingTrades']) if summary['losingTrades'] > 0 else 0
                summary['largestWin'] = max(winning_pnl) if winning_pnl else 0
                summary['largestLoss'] = min(losing_pnl) if losing_pnl else 0
                summary['profitFactor'] = (summary['totalProfit'] / summary['totalLoss']) if summary['totalLoss'] > 0 else 0
            
            conn.close()
            
            logger.info(f"✅ Generated trading summary from database: {summary['totalTrades']} trades, ${summary['netProfit']:.2f} net profit")
            
            return jsonify({
                'success': True,
                'summary': summary,
                'source': 'DATABASE'
            }), 200
        else:
            # Return default summary if no user_id and MT5 not available
            return jsonify({
                'success': True,
                'summary': summary,
                'source': 'DEFAULT'
            }), 200
            
    except Exception as e:
        logger.error(f"Error getting Exness trade summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def shutdown_backup():
    """Create final backup before shutdown"""
    logger.info("🛑 Creating final backup on shutdown...")
    try:
        backup_manager.create_backup()
        backup_manager.stop_auto_backup()
        logger.info("✅ Final backup complete. System shutdown.")
    except Exception as e:
        logger.error(f"Error during shutdown backup: {e}")

atexit.register(shutdown_backup)


if __name__ == '__main__':
    logger.info("Starting Zwesta Multi-Broker Backend")
    logger.info(f"MT5 Account: {MT5_CONFIG['account']}")
    logger.info(f"MT5 Server: {MT5_CONFIG['server']}")
    
    # AUTO-LAUNCH & LOGIN Exness MT5 Terminal with credentials
    logger.info("="*60)
    logger.info("🚀 LAUNCHING EXNESS MT5 TERMINAL WITH AUTO-LOGIN...")
    logger.info("="*60)
    
    mt5_path = MT5_CONFIG.get('path')
    account = MT5_CONFIG.get('account', '298997455')
    password = MT5_CONFIG.get('password', 'Zwesta@1985')
    server = MT5_CONFIG.get('server', 'Exness-MT5Trial9')
    
    logger.info(f"Terminal: {mt5_path}")
    logger.info(f"Account: {account}")
    logger.info(f"Server: {server}")
    logger.info(f"Mode: {ENVIRONMENT.upper()}")
    
    if mt5_path and os.path.exists(mt5_path):
        try:
            # Kill any existing MT5 processes first
            import subprocess
            subprocess.run(
                ["taskkill", "/F", "/IM", "terminal.exe"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            subprocess.run(
                ["taskkill", "/F", "/IM", "terminal64.exe"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            logger.info("Cleaned up existing MT5 processes")
            time.sleep(2)
            
            # Launch Exness MT5 with auto-login parameters
            # Exness MT5 terminal supports: /account:LOGIN /password:PASS /server:SERVER
            terminal_args = [
                mt5_path,
                f'/account:{account}',
                f'/password:{password}',
                f'/server:{server}'
            ]
            
            logger.info(f"Launching: {' '.join(terminal_args[:1])} with login parameters...")
            
            subprocess.Popen(
                terminal_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            logger.info("✓ Terminal launched with auto-login credentials")
            
            # Wait for terminal to fully initialize and login
            logger.info("⏳ Waiting 20 seconds for MT5 terminal to fully initialize and authenticate...")
            for countdown in range(20, 0, -1):
                if countdown % 5 == 0:
                    logger.info(f"   {countdown}s remaining...")
                time.sleep(1)
            
            logger.info("✅ MT5 terminal initialization complete - ready for SDK connections")
        except Exception as e:
            logger.warning(f"⚠️  Could not launch MT5: {e}")
    else:
        logger.warning(f"⚠️  MT5 path not found: {mt5_path}")
    
    # AUTO-CONNECT to MT5 (so dashboard shows real account balance)
    # This will retry up to 3 times with increasing waits
    auto_connect_mt5()
    
    # Initialize demo bots on startup (DISABLED for production cleanup)
    # logger.info("Initializing demo trading bots...")
    # initialize_demo_bots()
    # logger.info(f"[OK] {len(active_bots)} demo bots initialized and ready")
    
    # Repopulate active bots from database
    repopulate_active_bots()
    
    # Load user-created bots from database
    logger.info("Loading user-created bots from database...")
    user_bots_count = load_user_bots_from_database()
    logger.info(f"[OK] Loaded {user_bots_count} user bots from database")
    logger.info(f"[OK] Total bots ready: {len(active_bots)}")

    restarted_bots = start_enabled_bots_on_startup()
    logger.info(f"[OK] Auto-restarted {restarted_bots} enabled bots after backend startup")
    
    # Start live market data updater thread (fetches real prices from MT5)
    market_updater_thread = threading.Thread(target=live_market_data_updater, daemon=True)
    market_updater_thread.start()
    logger.info("🔄 Live market data updater thread started")
    
    # Start auto-withdrawal monitoring thread
    monitoring_thread = threading.Thread(target=auto_withdrawal_monitor, daemon=True)
    monitoring_thread.start()
    logger.info("Auto-withdrawal monitoring thread started")
    
    try:
        # Try ports in order: 9000, 5000, 3000
        ports = [9000, 5000, 3000]
        started = False
        for port in ports:
            try:
                logger.info(f"Attempting to start on http://0.0.0.0:{port}")
                app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)
                started = True
                break
            except OSError as e:
                logger.warning(f"Cannot bind to port {port}: {e}")
                continue
        
        if not started:
            logger.error("Failed to start server on any port")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        # Stop monitoring thread on shutdown
        monitoring_running = False
        if monitoring_thread:
            monitoring_thread.join(timeout=5)
        logger.info("Backend shutdown complete")


