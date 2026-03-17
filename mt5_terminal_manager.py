import os
import subprocess
import time
import sys

# Mapping of broker name to MT5 terminal path
MT5_TERMINALS = {
    'MetaQuotes': r'C:\MT5\MetaQuotes\terminal64.exe',
    'XM': r'C:\Program Files\XM Global MT5\terminal64.exe',
    'XM Global': r'C:\Program Files\XM Global MT5\terminal64.exe',
    'Exness': r'C:\Program Files\Exness MT5\terminal64.exe',
}

# Track running processes
running_terminals = {}


def detect_default_mt5_terminal():
    """Detect a standard local MT5 terminal path as fallback."""
    candidates = [
        r'C:\Program Files\MetaTrader 5\terminal64.exe',
        r'C:\Program Files\MetaTrader 5\terminal.exe',
        r'C:\Program Files (x86)\MetaTrader 5\terminal64.exe',
        r'C:\Program Files (x86)\MetaTrader 5\terminal.exe',
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def detect_broker_mt5_terminal(broker):
    """Detect broker-specific MT5 terminal paths before falling back to generic MT5."""
    broker_candidates = {
        'XM': [
            r'C:\Program Files\XM Global MT5\terminal64.exe',
            r'C:\Program Files\XM Global MT5\terminal.exe',
            r'C:\MT5\XMGlobal\terminal64.exe',
            r'C:\MT5\XMGlobal\terminal.exe',
        ],
        'XM Global': [
            r'C:\Program Files\XM Global MT5\terminal64.exe',
            r'C:\Program Files\XM Global MT5\terminal.exe',
            r'C:\MT5\XMGlobal\terminal64.exe',
            r'C:\MT5\XMGlobal\terminal.exe',
        ],
        'Exness': [
            r'C:\Program Files\Exness MT5\terminal64.exe',
            r'C:\Program Files\Exness MT5\terminal.exe',
            r'C:\Program Files (x86)\Exness MT5\terminal64.exe',
            r'C:\Program Files (x86)\Exness MT5\terminal.exe',
            r'C:\MT5\Exness\terminal64.exe',
            r'C:\MT5\Exness\terminal.exe',
        ],
        'MetaQuotes': [
            r'C:\Program Files\MetaTrader 5\terminal64.exe',
            r'C:\Program Files\MetaTrader 5\terminal.exe',
            r'C:\Program Files (x86)\MetaTrader 5\terminal64.exe',
            r'C:\Program Files (x86)\MetaTrader 5\terminal.exe',
            r'C:\MT5\MetaQuotes\terminal64.exe',
            r'C:\MT5\MetaQuotes\terminal.exe',
        ],
    }

    for path in broker_candidates.get(broker, []):
        if os.path.exists(path):
            return path

    return detect_default_mt5_terminal()

def launch_mt5_terminal(broker):
    path = MT5_TERMINALS.get(broker)
    if not path or not os.path.exists(path):
        fallback = detect_broker_mt5_terminal(broker)
        if fallback:
            path = fallback
            print(f"[INFO] Using fallback MT5 terminal for {broker or 'default'}: {path}")
        else:
            print(f"[WARN] Terminal for {broker} not found at {path}")
            return None
    # Launch with /portable to keep data/config isolated
    proc = subprocess.Popen([path, '/portable'])
    running_terminals[broker] = proc
    print(f"[INFO] Launched {broker} MT5 terminal (PID: {proc.pid})")
    return proc

def ensure_mt5_running(broker):
    if broker in running_terminals and running_terminals[broker].poll() is None:
        print(f"[INFO] {broker} MT5 terminal already running (PID: {running_terminals[broker].pid})")
        return running_terminals[broker]
    return launch_mt5_terminal(broker)

def stop_mt5_terminal(broker):
    proc = running_terminals.get(broker)
    if proc and proc.poll() is None:
        proc.terminate()
        print(f"[INFO] Stopped {broker} MT5 terminal (PID: {proc.pid})")
        running_terminals.pop(broker)
    else:
        print(f"[INFO] No running terminal for {broker}")

if __name__ == "__main__":
    # Launch only when an explicit broker name is provided.
    if len(sys.argv) > 1 and str(sys.argv[1]).strip():
        ensure_mt5_running(sys.argv[1].strip())
    else:
        print('[INFO] No broker specified for mt5_terminal_manager.py; skipping terminal launch.')
    # ...
    # To stop all terminals:
    # for broker in list(running_terminals.keys()):
    #     stop_mt5_terminal(broker)
