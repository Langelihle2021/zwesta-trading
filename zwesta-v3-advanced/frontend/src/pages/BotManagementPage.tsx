import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore, useTradingStore } from '../store/store';
import { api } from '../api/client';
import { LogOut, Play, Pause, Plus, Trash2 } from 'lucide-react';

export default function BotManagementPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const { selectedAccountId, setSelectedAccount, accounts } = useTradingStore();
  const [bots, setBots] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    strategy: 'scalping',
    symbol: 'EURUSD',
    risk_percent: 2.0,
    tp_percent: 2.0,
    sl_percent: 1.0,
  });

  useEffect(() => {
    if (selectedAccountId) {
      loadBots();
    }
  }, [selectedAccountId]);

  const loadBots = async () => {
    try {
      const response = await api.getBots(selectedAccountId!);
      setBots(response.data);
    } catch (error) {
      console.error('Failed to load bots:', error);
    }
  };

  const handleCreateBot = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      await api.createBot(selectedAccountId!, formData);
      setFormData({
        name: '',
        strategy: 'scalping',
        symbol: 'EURUSD',
        risk_percent: 2.0,
        tp_percent: 2.0,
        sl_percent: 1.0,
      });
      setShowForm(false);
      loadBots();
    } catch (error) {
      console.error('Failed to create bot:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleStartBot = async (botId: number) => {
    try {
      await api.startBot(botId);
      loadBots();
    } catch (error) {
      console.error('Failed to start bot:', error);
    }
  };

  const handleStopBot = async (botId: number) => {
    try {
      await api.stopBot(botId);
      loadBots();
    } catch (error) {
      console.error('Failed to stop bot:', error);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="bot-management-page">
      <style>{`
        .bot-management-page {
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
          position: sticky;
          top: 0;
          z-index: 100;
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
          font-weight: 500;
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
          transition: all 0.3s ease;
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

        .create-bot-btn {
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

        .create-bot-btn:hover {
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

        .form-input,
        .form-select {
          width: 100%;
          padding: 10px;
          border: 1px solid #ddd;
          border-radius: 6px;
          font-size: 14px;
          box-sizing: border-box;
        }

        .form-input:focus,
        .form-select:focus {
          outline: none;
          border-color: #667eea;
          box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }

        .form-buttons {
          display: flex;
          gap: 10px;
          margin-top: 20px;
        }

        .btn {
          padding: 10px 20px;
          border: none;
          border-radius: 6px;
          cursor: pointer;
          font-weight: 600;
          transition: all 0.3s ease;
        }

        .btn-primary {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          flex: 1;
        }

        .btn-primary:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 12px rgba(102, 126, 234, 0.4);
        }

        .btn-secondary {
          background: #f0f0f0;
          color: #333;
        }

        .btn-secondary:hover {
          background: #e0e0e0;
        }

        .bot-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
          gap: 20px;
        }

        .bot-card {
          background: white;
          border-radius: 12px;
          padding: 20px;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
          transition: all 0.3s ease;
        }

        .bot-card:hover {
          transform: translateY(-4px);
          box-shadow: 0 8px 12px rgba(0, 0, 0, 0.15);
        }

        .bot-header {
          display: flex;
          justify-content: space-between;
          align-items: start;
          margin-bottom: 15px;
        }

        .bot-name {
          font-size: 18px;
          font-weight: bold;
          color: #333;
        }

        .bot-status {
          padding: 4px 12px;
          border-radius: 20px;
          font-size: 12px;
          font-weight: 600;
        }

        .bot-status.active {
          background: #e8f5e9;
          color: #2e7d32;
        }

        .bot-status.inactive {
          background: #f5f5f5;
          color: #666;
        }

        .bot-info {
          margin-bottom: 15px;
        }

        .bot-info-item {
          display: flex;
          justify-content: space-between;
          margin-bottom: 8px;
          font-size: 14px;
        }

        .bot-label {
          color: #666;
        }

        .bot-value {
          font-weight: 600;
          color: #333;
        }

        .bot-actions {
          display: flex;
          gap: 10px;
          margin-top: 15px;
          padding-top: 15px;
          border-top: 1px solid #eee;
        }

        .btn-small {
          flex: 1;
          padding: 8px 12px;
          border: none;
          border-radius: 6px;
          cursor: pointer;
          font-weight: 600;
          font-size: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 4px;
          transition: all 0.3s ease;
        }

        .btn-start {
          background: #e8f5e9;
          color: #2e7d32;
        }

        .btn-start:hover {
          background: #2e7d32;
          color: white;
        }

        .btn-stop {
          background: #ffebee;
          color: #c62828;
        }

        .btn-stop:hover {
          background: #c62828;
          color: white;
        }

        .btn-delete {
          background: #ffebee;
          color: #c62828;
        }

        .btn-delete:hover {
          background: #c62828;
          color: white;
        }

        .empty-state {
          background: white;
          border-radius: 12px;
          padding: 60px 20px;
          text-align: center;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        .empty-state-icon {
          font-size: 48px;
          margin-bottom: 20px;
        }

        .empty-state-title {
          font-size: 20px;
          font-weight: bold;
          color: #333;
          margin-bottom: 10px;
        }

        .empty-state-text {
          color: #666;
          margin-bottom: 20px;
        }

        .grid-2 {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 20px;
        }

        @media (max-width: 768px) {
          .grid-2 {
            grid-template-columns: 1fr;
          }

          .bot-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>

      <nav className="navbar">
        <div className="navbar-left">
          <div className="navbar-brand">🤖 Bot Manager</div>
          <div className="navbar-menu">
            <a href="/dashboard">Dashboard</a>
            <a href="/bots">Trading Bots</a>
            <a href="/accounts">Accounts</a>
            <a href="/market">Market</a>
            <a href="/reports">Reports</a>
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
          <h1 className="section-title">Trading Bots</h1>
          <button className="create-bot-btn" onClick={() => setShowForm(!showForm)}>
            <Plus size={18} /> Create New Bot
          </button>
        </div>

        {showForm && (
          <div className="form-card">
            <h2 style={{ marginBottom: '20px' }}>Create Trading Bot</h2>
            <form onSubmit={handleCreateBot}>
              <div className="grid-2">
                <div className="form-group">
                  <label className="form-label">Bot Name</label>
                  <input type="text" className="form-input" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} placeholder="My Trading Bot" required />
                </div>

                <div className="form-group">
                  <label className="form-label">Strategy</label>
                  <select className="form-select" value={formData.strategy} onChange={(e) => setFormData({ ...formData, strategy: e.target.value })}>
                    <option value="scalping">Scalping</option>
                    <option value="swing">Swing Trading</option>
                    <option value="trend">Trend Following</option>
                    <option value="mean_reversion">Mean Reversion</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Trading Symbol</label>
                  <select className="form-select" value={formData.symbol} onChange={(e) => setFormData({ ...formData, symbol: e.target.value })}>
                    <option value="EURUSD">EURUSD</option>
                    <option value="GBPUSD">GBPUSD</option>
                    <option value="USDJPY">USDJPY</option>
                    <option value="AUDUSD">AUDUSD</option>
                    <option value="BTC">BTC/USD</option>
                    <option value="ETH">ETH/USD</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Risk per Trade (%)</label>
                  <input type="number" className="form-input" step="0.1" value={formData.risk_percent} onChange={(e) => setFormData({ ...formData, risk_percent: parseFloat(e.target.value) })} />
                </div>

                <div className="form-group">
                  <label className="form-label">Take Profit (%)</label>
                  <input type="number" className="form-input" step="0.1" value={formData.tp_percent} onChange={(e) => setFormData({ ...formData, tp_percent: parseFloat(e.target.value) })} />
                </div>

                <div className="form-group">
                  <label className="form-label">Stop Loss (%)</label>
                  <input type="number" className="form-input" step="0.1" value={formData.sl_percent} onChange={(e) => setFormData({ ...formData, sl_percent: parseFloat(e.target.value) })} />
                </div>
              </div>

              <div className="form-buttons">
                <button type="submit" className="btn btn-primary" disabled={loading}>
                  {loading ? 'Creating...' : 'Create Bot'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setShowForm(false)}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {bots.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">🤖</div>
            <div className="empty-state-title">No bots yet</div>
            <p className="empty-state-text">Create your first trading bot to start automated trading</p>
            <button className="create-bot-btn" onClick={() => setShowForm(true)}>
              <Plus size={18} /> Create Bot
            </button>
          </div>
        ) : (
          <div className="bot-grid">
            {bots.map((bot) => (
              <div key={bot.id} className="bot-card">
                <div className="bot-header">
                  <div className="bot-name">{bot.name}</div>
                  <div className={`bot-status ${bot.is_active ? 'active' : 'inactive'}`}>{bot.is_active ? '🟢 Active' : '⚪ Inactive'}</div>
                </div>

                <div className="bot-info">
                  <div className="bot-info-item">
                    <span className="bot-label">Strategy:</span>
                    <span className="bot-value">{bot.strategy}</span>
                  </div>
                  <div className="bot-info-item">
                    <span className="bot-label">Symbol:</span>
                    <span className="bot-value">{bot.symbol}</span>
                  </div>
                  <div className="bot-info-item">
                    <span className="bot-label">Risk:</span>
                    <span className="bot-value">{bot.risk_percent}%</span>
                  </div>
                  <div className="bot-info-item">
                    <span className="bot-label">Take Profit:</span>
                    <span className="bot-value">{bot.tp_percent}%</span>
                  </div>
                  <div className="bot-info-item">
                    <span className="bot-label">Stop Loss:</span>
                    <span className="bot-value">{bot.sl_percent}%</span>
                  </div>
                </div>

                <div className="bot-actions">
                  {bot.is_active ? (
                    <button className="btn-small btn-stop" onClick={() => handleStopBot(bot.id)}>
                      <Pause size={14} /> Stop
                    </button>
                  ) : (
                    <button className="btn-small btn-start" onClick={() => handleStartBot(bot.id)}>
                      <Play size={14} /> Start
                    </button>
                  )}
                  <button className="btn-small btn-delete" onClick={() => console.log('Delete bot')}>
                    <Trash2 size={14} /> Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
