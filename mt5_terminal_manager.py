import os
import subprocess
import time
import sys

# EXNESS MT5 ONLY - NO GENERIC/STANDALONE MT5 FALLBACK
# Mapping of broker name to MT5 terminal path (Exness primary)
MT5_TERMINALS = {
    'Exness': r'C:\Program Files\Exness MT5\terminal64.exe',
    'MetaQuotes': r'C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe',  # Exness-branded MetaQuotes
}

# Track running processes
running_terminals = {}


def detect_exness_mt5_terminal():
    """Detect Exness-specific MT5 terminal paths ONLY (no generic fallback)."""
    exness_candidates = [
        r'C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe',
        r'C:\Program Files\MetaTrader 5 EXNESS\terminal.exe',
        r'C:\Program Files\Exness MT5\terminal64.exe',
        r'C:\Program Files\Exness MT5\terminal.exe',
        r'C:\Program Files (x86)\Exness MT5\terminal64.exe',
        r'C:\Program Files (x86)\Exness MT5\terminal.exe',
        r'C:\MT5\Exness\terminal64.exe',
        r'C:\MT5\Exness\terminal.exe',
    ]
    for path in exness_candidates:
        if os.path.exists(path):
            return path
    return None


def detect_broker_mt5_terminal(broker):
    """Detect broker-specific MT5 terminal paths (Exness only, no generic MT5 fallback)."""
    # For now, only Exness is supported with broker-specific paths
    if broker and 'Exness' in broker:
        return detect_exness_mt5_terminal()
    
    # Default to Exness for any MT5 broker
    exness_path = detect_exness_mt5_terminal()
    if exness_path:
        return exness_path
    
    return None

def launch_mt5_terminal(broker):
    """Launch Exness MT5 terminal (broker-specific only, no generic MT5)."""
    path = MT5_TERMINALS.get(broker)
    if not path or not os.path.exists(path):
        fallback = detect_broker_mt5_terminal(broker)
        if fallback:
            path = fallback
            print(f"[INFO] Using Exness MT5 terminal for {broker}: {path}")
        else:
            print(f"[ERROR] ❌ Exness MT5 terminal not found for broker '{broker}'")
            print(f"        Please ensure Exness MT5 is installed at one of:")
            print(f"        - C:\\Program Files\\Exness MT5\\terminal64.exe")
            print(f"        - C:\\Program Files\\MetaTrader 5 EXNESS\\terminal64.exe")
            return None
    # Launch with /portable to keep data/config isolated
    proc = subprocess.Popen([path, '/portable'])
    running_terminals[broker] = proc
    print(f"[INFO] ✓ Launched Exness MT5 terminal for {broker} (PID: {proc.pid})")
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
