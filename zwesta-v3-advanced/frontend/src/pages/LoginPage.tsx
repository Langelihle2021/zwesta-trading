import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/store';
import { api } from '../api/client';
import { Lock, Mail } from 'lucide-react';

export default function LoginPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((state) => state.setAuth);
  const [username, setUsername] = useState('demo');
  const [password, setPassword] = useState('demo123');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await api.login({ username, password });
      const { access_token, refresh_token, user } = response.data;

      setAuth(user, access_token, refresh_token);
      localStorage.setItem('access_token', access_token);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <style>{`
        .login-page {
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          padding: 20px;
        }

        .login-card {
          background: white;
          border-radius: 16px;
          padding: 40px;
          box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
          max-width: 400px;
          width: 100%;
        }

        .login-header {
          text-align: center;
          margin-bottom: 30px;
        }

        .login-title {
          font-size: 28px;
          font-weight: bold;
          color: #333;
          margin-bottom: 8px;
        }

        .login-subtitle {
          color: #999;
          font-size: 14px;
        }

        .form-group {
          margin-bottom: 20px;
        }

        .form-label {
          display: block;
          font-weight: 600;
          color: #333;
          margin-bottom: 8px;
        }

        .form-input {
          width: 100%;
          padding: 12px;
          border: 2px solid #e0e0e0;
          border-radius: 8px;
          font-size: 14px;
          box-sizing: border-box;
          transition: border-color 0.3s ease;
        }

        .form-input:focus {
          outline: none;
          border-color: #667eea;
          box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }

        .login-button {
          width: 100%;
          padding: 12px;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          border: none;
          border-radius: 8px;
          font-weight: 600;
          font-size: 16px;
          cursor: pointer;
          transition: all 0.3s ease;
          margin-top: 10px;
        }

        .login-button:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
        }

        .login-button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .error-message {
          color: #ff6b6b;
          font-size: 13px;
          margin-top: 8px;
          padding: 10px;
          background: #ffe0e0;
          border-radius: 6px;
          border-left: 4px solid #ff6b6b;
        }

        .login-footer {
          text-align: center;
          margin-top: 20px;
          color: #999;
          font-size: 13px;
        }

        .icon {
          display: inline-block;
          margin-right: 8px;
          vertical-align: middle;
        }
      `}</style>

      <div className="login-card">
        <div className="login-header">
          <h1 className="login-title">🚀 Zwesta Trading</h1>
          <p className="login-subtitle">Advanced Crypto & Forex Trading Platform v3</p>
        </div>

        <form onSubmit={handleLogin}>
          <div className="form-group">
            <label className="form-label">
              <span className="icon"><Mail size={16} /></span>
              Username
            </label>
            <input
              type="text"
              className="form-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter username"
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label className="form-label">
              <span className="icon"><Lock size={16} /></span>
              Password
            </label>
            <input
              type="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              disabled={loading}
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" className="login-button" disabled={loading}>
            {loading ? 'Logging in...' : 'Sign In'}
          </button>
        </form>

        <div className="login-footer">
          Demo credentials: demo / demo123
        </div>
      </div>
    </div>
  );
}
