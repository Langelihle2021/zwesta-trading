#!/usr/bin/env python3
"""
VPS Memory Monitoring System
- Real-time system memory usage
- Backend Flask process memory tracking  
- Alert thresholds for high memory
- Optimization recommendations
"""

import psutil
import os
import json
from datetime import datetime
from pathlib import Path

class MemoryMonitor:
    def __init__(self):
        self.alert_threshold = 80  # Alert if > 80% memory used
        self.warning_threshold = 70  # Warning if > 70%
        
    def get_system_memory(self):
        """Get overall system memory stats"""
        mem = psutil.virtual_memory()
        return {
            'total_gb': round(mem.total / (1024**3), 2),
            'used_gb': round(mem.used / (1024**3), 2),
            'available_gb': round(mem.available / (1024**3), 2),
            'percent_used': mem.percent,
            'status': self._get_status(mem.percent)
        }
    
    def get_process_memory(self, pid):
        """Get memory used by specific process"""
        try:
            p = psutil.Process(pid)
            mem_info = p.memory_info()
            return {
                'pid': pid,
                'name': p.name(),
                'memory_mb': round(mem_info.rss / (1024**2), 2),
                'percent_of_total': round(p.memory_percent(), 2),
                'status': self._get_process_status(round(p.memory_percent(), 2))
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_backend_processes(self):
        """Find and analyze Flask backend processes"""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info']):
            try:
                # Look for Python processes (Flask backend)
                if proc.info['name'].lower() in ['python.exe', 'python']:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'multi_broker' in cmdline or 'backend' in cmdline.lower():
                        mem_mb = round(proc.info['memory_info'].rss / (1024**2), 2)
                        mem_percent = proc.memory_percent()
                        processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'memory_mb': mem_mb,
                            'percent': round(mem_percent, 2),
                            'status': self._get_process_status(mem_percent),
                            'cmdline': cmdline[:80]  # First 80 chars of command
                        })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return processes
    
    def get_top_processes(self, limit=10):
        """Get top N memory-consuming processes"""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                mem_mb = round(proc.memory_info().rss / (1024**2), 2)
                mem_percent = proc.memory_percent()
                processes.append({
                    'pid': proc.pid,
                    'name': proc.name(),
                    'memory_mb': mem_mb,
                    'percent': round(mem_percent, 2)
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Sort by memory usage and return top N
        processes.sort(key=lambda x: x['memory_mb'], reverse=True)
        return processes[:limit]
    
    def _get_status(self, percent):
        """Return status emoji based on percentage"""
        if percent >= self.alert_threshold:
            return '🔴 CRITICAL'
        elif percent >= self.warning_threshold:
            return '🟠 WARNING'
        elif percent >= 50:
            return '🟡 MODERATE'
        else:
            return '🟢 HEALTHY'
    
    def _get_process_status(self, percent):
        """Determine process memory status"""
        if percent > 10:
            return '⚠️  HIGH'
        elif percent > 5:
            return '🟠 ELEVATED'
        else:
            return '✅ NORMAL'
    
    def get_recommendations(self, sys_mem):
        """Get optimization recommendations"""
        recommendations = []
        
        percent = sys_mem['percent_used']
        
        if percent >= self.alert_threshold:
            recommendations.append({
                'level': 'CRITICAL',
                'action': 'Restart backend or disable low-priority services',
                'reason': f'System memory at {percent}% - performance degradation risk'
            })
        elif percent >= self.warning_threshold:
            recommendations.append({
                'level': 'WARNING',
                'action': 'Monitor closely, consider clearing caches',
                'reason': f'System approaching capacity at {percent}%'
            })
        
        if sys_mem['available_gb'] < 1:
            recommendations.append({
                'level': 'WARNING',
                'action': 'Less than 1GB free - may cause slowdowns',
                'reason': 'Limited available memory for spikes'
            })
        
        return recommendations if recommendations else [{'level': 'INFO', 'message': 'System memory usage is healthy'}]

def main():
    monitor = MemoryMonitor()
    
    print("\n" + "="*80)
    print("VPS MEMORY MONITORING REPORT")
    print("="*80 + "\n")
    
    # System memory
    sys_mem = monitor.get_system_memory()
    print("📊 SYSTEM MEMORY")
    print(f"   Total:     {sys_mem['total_gb']} GB")
    print(f"   Used:      {sys_mem['used_gb']} GB")
    print(f"   Available: {sys_mem['available_gb']} GB")
    print(f"   Usage:     {sys_mem['percent_used']}% {sys_mem['status']}")
    print()
    
    # Backend processes
    backend = monitor.get_backend_processes()
    print("🐍 FLASK BACKEND PROCESSES")
    if backend:
        for proc in backend:
            print(f"   PID {proc['pid']}: {proc['name']}")
            print(f"     Memory: {proc['memory_mb']} MB ({proc['percent']}%) {proc['status']}")
            print(f"     Command: {proc['cmdline']}")
    else:
        print("   ℹ️  No Flask backend processes found currently running")
    print()
    
    # Top processes
    print("⬆️  TOP 10 MEMORY-CONSUMING PROCESSES")
    top = monitor.get_top_processes(10)
    for i, proc in enumerate(top, 1):
        print(f"   {i}. {proc['name']:<20} {proc['memory_mb']:>8} MB ({proc['percent']:>6.2f}%)")
    print()
    
    # Recommendations
    print("💡 RECOMMENDATIONS")
    recommendations = monitor.get_recommendations(sys_mem)
    for rec in recommendations:
        if 'action' in rec:
            print(f"   [{rec['level']}] {rec['action']}")
            print(f"            {rec['reason']}")
        else:
            print(f"   {rec['level']}: {rec['message']}")
    print()
    
    print("="*80 + "\n")

if __name__ == '__main__':
    main()
