#!/usr/bin/env python3
"""
Check MT5 positions directly
"""

import MetaTrader5 as mt5

mt5.initialize()
try:
    if mt5.login(298997455, password='Exness-MT5Trial9', server='Exness-MT5Trial9'):
        print('✅ MT5 Login Successful')
        acc = mt5.account_info()
        if acc:
            print(f'📍 Account: {acc.login}')
            print(f'💰 Balance: ${acc.balance:,.2f}')
            print(f'📊 Equity: ${acc.equity:,.2f}')
        
        positions = mt5.positions_get()
        print(f'\n📋 Open Positions: {len(positions)}\n')
        
        if positions:
            for pos in positions:
                pos_type = "BUY" if pos.type == 0 else "SELL"
                print(f'   {pos.symbol}: {pos_type} {pos.volume} lots | Open: ${pos.price_open:.5f} | Current: ${pos.price_current:.5f} | P&L: ${pos.profit:.2f}')
        else:
            print("   ⚠️  No positions open")
        
        mt5.shutdown()
    else:
        print('❌ MT5 Login Failed')
except Exception as e:
    print(f'❌ ERROR: {e}')
finally:
    try:
        mt5.shutdown()
    except:
        pass
