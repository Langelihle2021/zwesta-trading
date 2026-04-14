import argparse
import csv
import sys

from create_backend_test_user import register_user, login_user, test_binance_connection


def parse_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def main():
    parser = argparse.ArgumentParser(
        description='Bulk-register Zwesta users and optionally link each one to their own Binance API credentials.'
    )
    parser.add_argument('--backend-url', default='http://127.0.0.1:9000', help='Backend base URL')
    parser.add_argument('--csv-path', required=True, help='Path to CSV file with Binance user rows')
    parser.add_argument('--default-password', help='Fallback Zwesta app password if a row omits user_password')
    parser.add_argument('--skip-register', action='store_true', help='Skip registration and log in to existing users only')
    args = parser.parse_args()

    base_url = args.backend_url.rstrip('/')
    created_or_logged_in = 0
    linked = 0

    with open(args.csv_path, 'r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        required_columns = {'email', 'name'}
        if not required_columns.issubset(set(reader.fieldnames or [])):
            missing = ', '.join(sorted(required_columns - set(reader.fieldnames or [])))
            print(f'CSV is missing required columns: {missing}')
            return 1

        for index, row in enumerate(reader, start=2):
            email = str(row.get('email') or '').strip().lower()
            name = str(row.get('name') or '').strip()
            user_password = str(row.get('user_password') or args.default_password or '').strip()
            api_key = str(row.get('api_key') or '').strip()
            api_secret = str(row.get('api_secret') or '').strip()
            market = str(row.get('market') or 'spot').strip().lower() or 'spot'
            account_number = str(row.get('account_number') or market.upper()).strip()
            is_live = parse_bool(row.get('is_live'), default=True)

            if not email or not name:
                print(f'Row {index}: skipped because email or name is blank')
                continue

            if not user_password:
                print(f'Row {index}: skipped {email} because user_password is missing')
                continue

            if not args.skip_register:
                status_code, response = register_user(base_url, email, name, user_password)
                if status_code not in (200, 201, 409):
                    print(f'Row {index}: registration failed for {email} ({status_code}): {response}')
                    return 1

            status_code, login_response = login_user(base_url, email, user_password)
            if status_code != 200 or not login_response.get('success'):
                print(f'Row {index}: login failed for {email} ({status_code}): {login_response}')
                return 1

            created_or_logged_in += 1
            session_token = login_response.get('session_token')

            if api_key and api_secret:
                status_code, link_response = test_binance_connection(
                    base_url,
                    session_token,
                    api_key,
                    api_secret,
                    market,
                    is_live,
                    account_number,
                )
                if status_code != 200 or not link_response.get('success'):
                    print(f'Row {index}: Binance linking failed for {email} ({status_code}): {link_response}')
                    return 1
                linked += 1
                print(f'Row {index}: linked Binance for {email} ({account_number}, {"live" if is_live else "demo"})')
            else:
                print(f'Row {index}: created Zwesta user only for {email}; Binance API credentials not provided')

    print(f'Completed: {created_or_logged_in} users processed, {linked} Binance accounts linked.')
    return 0


if __name__ == '__main__':
    sys.exit(main())