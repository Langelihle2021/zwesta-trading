import os
import subprocess
import time

# Mapping of broker name to MT5 terminal path
MT5_TERMINALS = {
    'MetaQuotes': r'C:\MT5\MetaQuotes\terminal64.exe',
    'XM': r'C:\MT5\XMGlobal\terminal64.exe',
    'IG': r'C:\MT5\IG\terminal64.exe',
    'FXM': r'C:\MT5\FXM\terminal64.exe',
    'AvaTrade': r'C:\MT5\AvaTrade\terminal64.exe',
    'FP Markets': r'C:\MT5\FPMarkets\terminal64.exe',
    # Add more as needed
}

# Track running processes
running_terminals = {}

def launch_mt5_terminal(broker):
    path = MT5_TERMINALS.get(broker)
    if not path or not os.path.exists(path):
        print(f"[ERROR] Terminal for {broker} not found at {path}")
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
    # Example usage: launch all terminals
    for broker in MT5_TERMINALS:
        ensure_mt5_running(broker)
        time.sleep(2)  # Stagger launches
    # ...
    # To stop all terminals:
    # for broker in list(running_terminals.keys()):
    #     stop_mt5_terminal(broker)
