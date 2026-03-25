import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/store';
import { LogOut } from 'lucide-react';

export default function ReportsPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', minHeight: '100vh' }}>
      <div style={{ background: 'white', padding: '15px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontSize: '24px', fontWeight: 'bold', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', backgroundClip: 'text', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          📊 Reports
        </div>
        <button
          onClick={handleLogout}
          style={{
            padding: '8px 16px',
            background: '#ff6b6b',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontWeight: '600',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <LogOut size={16} /> Logout
        </button>
      </div>

      <div style={{ maxWidth: '1200px', margin: '40px auto', padding: '0 20px' }}>
        <div style={{ background: 'white', borderRadius: '12px', padding: '40px', textAlign: 'center' }}>
          <div style={{ fontSize: '32px', marginBottom: '20px' }}>📋 Trading Reports</div>
          <p style={{ color: '#666', marginBottom: '30px' }}>
            Generate detailed trading reports, performance analysis, and statistics. Download as PDF.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px', marginTop: '30px' }}>
            <div style={{ padding: '20px', border: '1px solid #eee', borderRadius: '8px', transition: 'all 0.3s ease' }} onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)')} onMouseLeave={(e) => (e.currentTarget.style.boxShadow = 'none')}>
              <div style={{ fontSize: '24px', marginBottom: '10px' }}>📈 Monthly Report</div>
              <p style={{ color: '#666', fontSize: '13px', marginBottom: '15px' }}>Summary of trading activity, P&L, and performance metrics</p>
              <button style={{ padding: '8px 16px', background: '#667eea', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '600' }}>
                Generate PDF
              </button>
            </div>

            <div style={{ padding: '20px', border: '1px solid #eee', borderRadius: '8px', transition: 'all 0.3s ease' }} onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)')} onMouseLeave={(e) => (e.currentTarget.style.boxShadow = 'none')}>
              <div style={{ fontSize: '24px', marginBottom: '10px' }}>📊 Performance Analysis</div>
              <p style={{ color: '#666', fontSize: '13px', marginBottom: '15px' }}>Detailed analysis of wins, losses, profit factor, and statistics</p>
              <button style={{ padding: '8px 16px', background: '#667eea', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '600' }}>
                Generate PDF
              </button>
            </div>

            <div style={{ padding: '20px', border: '1px solid #eee', borderRadius: '8px', transition: 'all 0.3s ease' }} onMouseEnter={(e) => (e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)')} onMouseLeave={(e) => (e.currentTarget.style.boxShadow = 'none')}>
              <div style={{ fontSize: '24px', marginBottom: '10px' }}>💼 Custom Report</div>
              <p style={{ color: '#666', fontSize: '13px', marginBottom: '15px' }}>Create custom reports with date ranges and specific metrics</p>
              <button style={{ padding: '8px 16px', background: '#667eea', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '600' }}>
                Generate PDF
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
