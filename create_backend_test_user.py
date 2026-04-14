import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def _request_json(url, method='GET', payload=None, headers=None):
    body = None
    request_headers = {'Content-Type': 'application/json'}
    if headers:
        request_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode('utf-8')

    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode('utf-8')
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='replace')
        try:
            return exc.code, json.loads(raw) if raw else {'success': False, 'error': raw}
        except json.JSONDecodeError:
            return exc.code, {'success': False, 'error': raw}


def register_user(base_url, email, name, password):
    return _request_json(
        f'{base_url}/api/user/register',
        method='POST',
        payload={
            'email': email,
            'name': name,
            'password': password,
        },
    )


def login_user(base_url, email, password):
    return _request_json(
        f'{base_url}/api/user/login',
        method='POST',
        payload={
            'email': email,
            'password': password,
        },
    )


def link_broker_credentials(base_url, user_id, session_token, broker_name, account_number, password, server, is_live, mt5_terminal_path=None):
    return _request_json(
        f'{base_url}/api/user/{urllib.parse.quote(user_id)}/broker-credentials',
        method='POST',
        payload={
            'broker_name': broker_name,
            'account_number': str(account_number),
            'password': password,
            'server': server,
            'is_live': bool(is_live),
            'mt5_terminal_path': mt5_terminal_path,
        },
        headers={
            'X-Session-Token': session_token,
        },
    )


def save_broker_credentials(base_url, session_token, payload):
    return _request_json(
        f'{base_url}/api/broker/credentials',
        method='POST',
        payload=payload,
        headers={
            'X-Session-Token': session_token,
        },
    )


def test_binance_connection(base_url, session_token, api_key, api_secret, market, is_live, account_number=None):
    payload = {
        'broker': 'Binance',
        'api_key': api_key,
        'api_secret': api_secret,
        'market': market,
        'server': market,
        'is_live': bool(is_live),
    }
    if account_number:
        payload['account_number'] = account_number

    return _request_json(
        f'{base_url}/api/broker/test-connection',
        method='POST',
        payload=payload,
        headers={
            'X-Session-Token': session_token,
        },
    )


def main():
    parser = argparse.ArgumentParser(
        description='Register a Zwesta user on the VPS backend and optionally link broker credentials.'
    )
    parser.add_argument('--backend-url', default='http://127.0.0.1:9000', help='Backend base URL')
    parser.add_argument('--email', required=True, help='User email address')
    parser.add_argument('--name', required=True, help='Display name for the user')
    parser.add_argument('--user-password', required=True, help='Zwesta login password for the user')
    parser.add_argument('--broker-name', default='Exness', help='Broker name to link')
    parser.add_argument('--mt5-account', help='MetaTrader account number to link')
    parser.add_argument('--mt5-password', help='MetaTrader account password to link')
    parser.add_argument('--server', help='MT5 server name, for example Exness-MT5Real27 or Exness-MT5Trial9')
    parser.add_argument('--mt5-terminal-path', help='Dedicated MT5 terminal64.exe path for this user/account')
    parser.add_argument('--api-key', help='API key for Binance, OANDA, FXCM or similar brokers')
    parser.add_argument('--api-secret', help='API secret for Binance or similar brokers')
    parser.add_argument('--market', default='spot', help='Broker market/server for Binance, for example spot or futures')
    parser.add_argument('--account-number', help='Optional account identifier override for Binance or other brokers')
    parser.add_argument('--live', action='store_true', help='Link the MT5 account as live')
    parser.add_argument('--skip-register', action='store_true', help='Skip register and log in with an existing user')
    args = parser.parse_args()

    base_url = args.backend_url.rstrip('/')

    if not args.skip_register:
        status_code, response = register_user(base_url, args.email, args.name, args.user_password)
        if status_code not in (200, 201, 409):
            print(f'Registration failed ({status_code}): {response}')
            return 1
        if status_code == 409:
            print(f'User already exists for {args.email}; continuing with login.')
        else:
            print(f"Registered user: {response.get('user_id')} ({response.get('email')})")

    status_code, login_response = login_user(base_url, args.email, args.user_password)
    if status_code != 200 or not login_response.get('success'):
        print(f'Login failed ({status_code}): {login_response}')
        return 1

    user_id = login_response.get('user_id')
    session_token = login_response.get('session_token')
    print(f'Logged in user_id={user_id}')

    broker_name = str(args.broker_name or '').strip()
    normalized_broker = broker_name.lower()

    if normalized_broker == 'binance' and (args.api_key or args.api_secret):
        if not all([args.api_key, args.api_secret]):
            print('To link Binance credentials you must pass --api-key and --api-secret together.')
            return 1

        status_code, link_response = test_binance_connection(
            base_url,
            session_token,
            args.api_key,
            args.api_secret,
            args.market,
            args.live,
            args.account_number,
        )
        if status_code != 200 or not link_response.get('success'):
            print(f'Binance credential linking failed ({status_code}): {link_response}')
            return 1
        print(
            f"Linked Binance account {link_response.get('account_number') or args.account_number or args.market.upper()}"
            f" to {args.email} in {'live' if args.live else 'demo'} mode"
        )
    elif args.api_key:
        payload = {
            'broker_name': broker_name,
            'api_key': args.api_key,
            'api_secret': args.api_secret,
            'account_number': args.account_number,
            'server': args.server or args.market,
            'is_live': bool(args.live),
        }
        status_code, link_response = save_broker_credentials(base_url, session_token, payload)
        if status_code not in (200, 201) or not link_response.get('success'):
            print(f'API credential linking failed ({status_code}): {link_response}')
            return 1
        print(f"Linked {broker_name} API credentials to {args.email}")
    elif args.mt5_account or args.mt5_password or args.server:
        if not all([args.mt5_account, args.mt5_password, args.server]):
            print('To link MT5 credentials you must pass --mt5-account, --mt5-password, and --server together.')
            return 1

        status_code, link_response = link_broker_credentials(
            base_url,
            user_id,
            session_token,
            broker_name,
            args.mt5_account,
            args.mt5_password,
            args.server,
            args.live,
            args.mt5_terminal_path,
        )
        if status_code != 200 or not link_response.get('success'):
            print(f'MT5 credential linking failed ({status_code}): {link_response}')
            return 1
        print(
            f"Linked {broker_name} account {args.mt5_account} to {args.email}"
            + (f" using {args.mt5_terminal_path}" if args.mt5_terminal_path else '')
        )
    else:
        print('User created and logged in. No MT5 account was linked because no MT5 credentials were provided.')

    print('Setup completed successfully.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
