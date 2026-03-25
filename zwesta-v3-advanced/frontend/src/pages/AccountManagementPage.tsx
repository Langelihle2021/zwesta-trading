import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore, useTradingStore } from '../store/store';
import { api } from '../api/client';
import { LogOut, Plus, LogIn } from 'lucide-react';

export default function AccountManagementPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const { accounts, setAccounts } = useTradingStore();
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [accountDetails, setAccountDetails] = useState<any>(null);
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    broker: '',
    account_number: '',
  });

  useEffect(() => {
    loadAccounts();
  }, []);

  useEffect(() => {
    if (selectedAccountId) {
      loadAccountDetails(selectedAccountId);
    }
  }, [selectedAccountId]);

  const loadAccounts = async () => {
    try {
      const response = await api.getAccounts();
      setAccounts(response.data);
    } catch (error) {
      console.error('Failed to load accounts:', error);
    }
  };

  const loadAccountDetails = async (accountId: number) => {
    try {
      const response = await api.getAccount(accountId);
      setAccountDetails(response.data);
    } catch (error) {
      console.error('Failed to load account details:', error);
    }
  };

  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      await api.createAccount(formData);
      setFormData({ name: '', broker: '', account_number: '' });
      setShowForm(false);
      loadAccounts();
    } catch (error) {
      console.error('Failed to create account:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="account-management-page">
      <style>{`
        .account-management-page {
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
          transition: all 0.3s ease;
          font-size: 14px;
        }

        .navbar-menu a:hover {
          background: #f0f0f0;
          color: #667eea;
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
          max-width: 1200px;
          margin: 20px auto;
          padding: 0 20px;
        }

        .section-header {
          background: white;
          padding: 20px;
          border-radius: 12px;
          margin-bottom: 20px;
          display: flex;
          justify-content: space-between;
          align-items: center;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        .section-title {
          font-size: 24px;
          font-weight: bold;
          color: #333;
        }

        .btn {
          padding: 10px 20px;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          border: none;
          border-radius: 6px;
          cursor: pointer;
          font-weight: 600;
          display: flex;
          align-items: center;
          gap: 6px;
          transition: all 0.3s ease;
        }

        .btn:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 12px rgba(102, 126, 234, 0.4);
        }

        .form-card {
          background: white;
          border-radius: 12px;
          padding: 30px;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
          margin-bottom: 30px;
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
          padding: 10px;
          border: 1px solid #ddd;
          border-radius: 6px;
          font-size: 14px;
          box-sizing: border-box;
        }

        .form-input:focus {
          outline: none;
          border-color: #667eea;
        }

        .grid-3 {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 20px;
          margin-bottom: 20px;
        }

        .account-card {
          background: white;
          border-radius: 12px;
          padding: 20px;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
          cursor: pointer;
          transition: all 0.3s ease;
          border: 2px solid transparent;
        }

        .account-card:hover {
          transform: translateY(-4px);
          border-color: #667eea;
        }

        .account-card.active {
          border-color: #667eea;
          background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
        }

        .account-name {
          font-size: 18px;
          font-weight: bold;
          color: #333;
          margin-bottom: 10px;
        }

        .account-broker {
          color: #666;
          font-size: 14px;
          margin-bottom: 10px;
        }

        .account-number {
          color: #999;
          font-size: 12px;
        }

        .details-card {
          background: white;
          border-radius: 12px;
          padding: 30px;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        .details-header {
          margin-bottom: 30px;
          border-bottom: 2px solid #eee;
          padding-bottom: 20px;
        }

        .details-title {
          font-size: 24px;
          font-weight: bold;
          color: #333;
          margin-bottom: 10px;
        }

        .details-subtitle {
          color: #666;
          font-size: 14px;
        }

        .details-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 20px;
        }

        .detail-item {
          padding: 15px;
          border: 1px solid #eee;
          border-radius: 8px;
          background: #f8f9fa;
        }

        .detail-label {
          color: #666;
          font-size: 12px;
          text-transform: uppercase;
          margin-bottom: 8px;
        }

        .detail-value {
          font-size: 18px;
          font-weight: bold;
          color: #333;
        }

        @media (max-width: 1024px) {
          .grid-3 {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        @media (max-width: 768px) {
          .grid-3 {
            grid-template-columns: 1fr;
          }
        }
      `}</style>

      <nav className="navbar">
        <div className="navbar-left">
          <div className="navbar-brand">💼 Account Management</div>
          <div className="navbar-menu">
            <a href="/dashboard">Dashboard</a>
            <a href="/bots">Trading Bots</a>
            <a href="/accounts">Accounts</a>
            <a href="/market">Market</a>
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
        <div className="section-header">
          <h1 className="section-title">My Trading Accounts</h1>
          <button className="btn" onClick={() => setShowForm(!showForm)}>
            <Plus size={18} /> Add Account
          </button>
        </div>

        {showForm && (
          <div className="form-card">
            <h2 style={{ marginBottom: '20px' }}>Connect Trading Account</h2>
            <form onSubmit={handleCreateAccount}>
              <div className="form-group">
                <label className="form-label">Account Name</label>
                <input type="text" className="form-input" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} placeholder="e.g., My XM Account" required />
              </div>

              <div className="form-group">
                <label className="form-label">Broker</label>
                <input type="text" className="form-input" value={formData.broker} onChange={(e) => setFormData({ ...formData, broker: e.target.value })} placeholder="e.g., XM, FXCM, Interactive Brokers" required />
              </div>

              <div className="form-group">
                <label className="form-label">Account Number</label>
                <input type="text" className="form-input" value={formData.account_number} onChange={(e) => setFormData({ ...formData, account_number: e.target.value })} placeholder="1234567" required />
              </div>

              <div style={{ display: 'flex', gap: '10px' }}>
                <button type="submit" className="btn" disabled={loading}>
                  {loading ? 'Adding...' : 'Add Account'}
                </button>
                <button type="button" className="btn" style={{ background: '#f0f0f0', color: '#333' }} onClick={() => setShowForm(false)}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        <div className="grid-3">
          {accounts.map((account) => (
            <div key={account.id} className={`account-card ${selectedAccountId === account.id ? 'active' : ''}`} onClick={() => setSelectedAccountId(account.id)}>
              <div className="account-name">{account.name}</div>
              <div className="account-broker">📊 {account.broker}</div>
              <div className="account-number">ID: {account.account_number || 'N/A'}</div>
              <div style={{ marginTop: '10px', fontSize: '12px', color: '#51cf66', fontWeight: 'bold' }}>💰 Balance: ${account.balance?.toFixed(2)}</div>
            </div>
          ))}
        </div>

        {selectedAccountId && accountDetails && (
          <div className="details-card" style={{ marginTop: '30px' }}>
            <div className="details-header">
              <div className="details-title">{accountDetails.name}</div>
              <div className="details-subtitle">{accountDetails.broker} • {accountDetails.account_number}</div>
            </div>

            <div className="details-grid">
              <div className="detail-item">
                <div className="detail-label">Balance</div>
                <div className="detail-value" style={{ color: '#51cf66' }}>${accountDetails.balance?.toFixed(2)}</div>
              </div>

              <div className="detail-item">
                <div className="detail-label">Equity</div>
                <div className="detail-value">${accountDetails.equity?.toFixed(2)}</div>
              </div>

              <div className="detail-item">
                <div className="detail-label">Used Margin</div>
                <div className="detail-value">${accountDetails.margin_used?.toFixed(2)}</div>
              </div>

              <div className="detail-item">
                <div className="detail-label">Margin Level</div>
                <div className="detail-value">{accountDetails.margin_level?.toFixed(0)}%</div>
              </div>

              <div className="detail-item">
                <div className="detail-label">Account Type</div>
                <div className="detail-value">{accountDetails.is_demo ? '📝 Demo' : '💎 Live'}</div>
              </div>

              <div className="detail-item">
                <div className="detail-label">Status</div>
                <div className="detail-value" style={{ color: accountDetails.is_active ? '#51cf66' : '#ff6b6b' }}>
                  {accountDetails.is_active ? '🟢 Active' : '🔴 Inactive'}
                </div>
              </div>
            </div>

            <div style={{ marginTop: '30px', display: 'flex', gap: '10px' }}>
              <button className="btn" onClick={() => navigate('/deposit')}>
                <LogIn size={16} /> Deposit
              </button>
              <button className="btn" onClick={() => navigate('/withdraw')} style={{ background: '#ff6b6b' }}>
                Log Out
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
