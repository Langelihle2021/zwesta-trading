import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/store';
import { LogOut } from 'lucide-react';

export default function ProfilePage() {
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
          👤 Profile
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

      <div style={{ maxWidth: '600px', margin: '40px auto', padding: '0 20px' }}>
        <div style={{ background: 'white', borderRadius: '12px', padding: '40px', boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)' }}>
          <div style={{ textAlign: 'center', marginBottom: '40px' }}>
            <div style={{ fontSize: '64px', marginBottom: '20px' }}>👤</div>
            <h1 style={{ margin: '0 0 10px 0', fontSize: '28px', fontWeight: 'bold', color: '#333' }}>{user?.full_name || user?.username}</h1>
            <p style={{ color: '#666', margin: '0' }}>{user?.email}</p>
          </div>

          <div style={{ borderTop: '1px solid #eee', paddingTop: '30px' }}>
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '12px', color: '#999', textTransform: 'uppercase', marginBottom: '8px', fontWeight: '600' }}>
                Username
              </label>
              <input type="text" value={user?.username} disabled style={{ width: '100%', padding: '10px', border: '1px solid #ddd', borderRadius: '6px', backgroundColor: '#f8f9fa' }} />
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '12px', color: '#999', textTransform: 'uppercase', marginBottom: '8px', fontWeight: '600' }}>
                Email
              </label>
              <input type="text" value={user?.email} disabled style={{ width: '100%', padding: '10px', border: '1px solid #ddd', borderRadius: '6px', backgroundColor: '#f8f9fa' }} />
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '12px', color: '#999', textTransform: 'uppercase', marginBottom: '8px', fontWeight: '600' }}>
                Full Name
              </label>
              <input type="text" value={user?.full_name} disabled style={{ width: '100%', padding: '10px', border: '1px solid #ddd', borderRadius: '6px', backgroundColor: '#f8f9fa' }} />
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '12px', color: '#999', textTransform: 'uppercase', marginBottom: '8px', fontWeight: '600' }}>
                Phone
              </label>
              <input type="text" value={user?.phone || 'Not provided'} disabled style={{ width: '100%', padding: '10px', border: '1px solid #ddd', borderRadius: '6px', backgroundColor: '#f8f9fa' }} />
            </div>
          </div>

          <button
            onClick={handleLogout}
            style={{
              width: '100%',
              padding: '12px',
              background: '#ff6b6b',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              fontWeight: '600',
              fontSize: '16px',
              cursor: 'pointer',
              marginTop: '30px',
              transition: 'all 0.3s ease',
            }}
          >
            Logout
          </button>
        </div>
      </div>
    </div>
  );
}
