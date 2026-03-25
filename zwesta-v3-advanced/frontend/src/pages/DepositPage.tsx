import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore, useTradingStore } from '../store/store';
import { api } from '../api/client';
import { LogOut, CreditCard } from 'lucide-react';

export default function DepositPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const { selectedAccountId, accounts } = useTradingStore();
  const [amount, setAmount] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  const handleDeposit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      await api.deposit(selectedAccountId || 0, { amount: parseFloat(amount) });
      setSuccess(`Deposit of $${amount} processed successfully!`);
      setAmount('');
      setTimeout(() => navigate('/dashboard'), 2000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Deposit failed');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const quickAmounts = [100, 500, 1000, 5000];

  return (
    <div className="deposit-page">
      <style>{`
        .deposit-page {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          min-height: 100vh;
          padding-bottom: 50px;
        }

        .navbar {
          background: white;
          padding: 15px 20px;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .navbar-left {
          display: flex;
          align-items: center;
          gap: 30px;
        }

        .navbar-brand {
          font-size: 24px;
          font-weight: bold;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        .navbar-menu {
          display: flex;
          list-style: none;
          margin: 0;
          padding: 0;
          gap: 10px;
        }

        .navbar-menu a {
          text-decoration: none;
          color: #333;
          padding: 8px 16px;
          border-radius: 6px;
          font-size: 14px;
        }

        .navbar-menu a:hover {
          background: #f0f0f0;
        }

        .navbar-right {
          display: flex;
          align-items: center;
          gap: 20px;
        }

        .logout-button {
          padding: 8px 16px;
          background: #ff6b6b;
          color: white;
          border: none;
          border-radius: 6px;
          cursor: pointer;
          font-weight: 600;
          display: flex;
          align-items: center;
          gap: 6px;
        }

        .container {
          max-width: 600px;
          margin: 40px auto;
          padding: 0 20px;
        }

        .form-card {
          background: white;
          border-radius: 12px;
          padding: 40px;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        .form-header {
          text-align: center;
          margin-bottom: 30px;
        }

        .form-title {
          font-size: 28px;
          font-weight: bold;
          color: #333;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 10px;
        }

        .form-subtitle {
          color: #666;
          font-size: 14px;
          margin-top: 10px;
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
          font-size: 16px;
          box-sizing: border-box;
          transition: border-color 0.3s ease;
        }

        .form-input:focus {
          outline: none;
          border-color: #667eea;
        }

        .quick-amounts {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 10px;
          margin-bottom: 20px;
        }

        .quick-amount-btn {
          padding: 10px;
          border: 2px solid #ddd;
          background: white;
          border-radius: 6px;
          cursor: pointer;
          font-weight: 600;
          transition: all 0.3s ease;
        }

        .quick-amount-btn:hover {
          border-color: #667eea;
          background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
        }

        .submit-button {
          width: 100%;
          padding: 12px;
          background: linear-gradient(135deg, #51cf66 0%, #2e7d32 100%);
          color: white;
          border: none;
          border-radius: 8px;
          font-weight: 600;
          font-size: 16px;
          cursor: pointer;
          transition: all 0.3s ease;
        }

        .submit-button:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 6px 12px rgba(81, 207, 102, 0.4);
        }

        .submit-button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .message {
          padding: 12px;
          margin-bottom: 20px;
          border-radius: 6px;
          font-size: 14px;
        }

        .success-message {
          background: #e8f5e9;
          color: #2e7d32;
          border-left: 4px solid #51cf66;
        }

        .error-message {
          background: #ffebee;
          color: #c62828;
          border-left: 4px solid #ff6b6b;
        }

        @media (max-width: 640px) {
          .quick-amounts {
            grid-template-columns: repeat(2, 1fr);
          }
        }
      `}</style>

      <nav className="navbar">
        <div className="navbar-left">
          <div className="navbar-brand">💰 Deposit Funds</div>
          <div className="navbar-menu">
            <a href="/dashboard">Dashboard</a>
            <a href="/accounts">Accounts</a>
          </div>
        </div>

        <div className="navbar-right">
          <div style={{ fontSize: '14px', color: '#666' }}>{user?.username}</div>
          <button className="logout-button" onClick={handleLogout}>
            <LogOut size={16} /> Logout
          </button>
        </div>
      </nav>

      <div className="container">
        <div className="form-card">
          <div className="form-header">
            <div className="form-title">
              <CreditCard size={32} /> Add Funds
            </div>
            <p className="form-subtitle">Secure payment processing</p>
          </div>

          {success && <div className="message success-message">✅ {success}</div>}
          {error && <div className="message error-message">❌ {error}</div>}

          <form onSubmit={handleDeposit}>
            <div className="form-group">
              <label className="form-label">Select Account</label>
              <select style={{ ...require('./DepositPage').formInput }} disabled>
                <option>{accounts.find((a) => a.id === selectedAccountId)?.name || 'Select account'}</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Deposit Amount (USD)</label>
              <div style={{ fontSize: '12px', color: '#666', marginBottom: '8px' }}>Quick select:</div>
              <div className="quick-amounts">
                {quickAmounts.map((amt) => (
                  <button key={amt} type="button" className="quick-amount-btn" onClick={() => setAmount(amt.toString())}>
                    ${amt}
                  </button>
                ))}
              </div>
              <input
                type="number"
                className="form-input"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="Enter amount"
                min="1"
                step="0.01"
                required
              />
            </div>

            <button type="submit" className="submit-button" disabled={loading || !amount}>
              {loading ? '⏳ Processing...' : '✅ Confirm Deposit'}
            </button>
          </form>

          <div style={{ marginTop: '20px', padding: '15px', background: '#f8f9fa', borderRadius: '6px', fontSize: '13px', color: '#666' }}>
            <strong>💡 Note:</strong> This is a demo. Real deposits would require Stripe or payment processor integration. Enter amount and click deposit to proceed.
          </div>
        </div>
      </div>
    </div>
  );
}
