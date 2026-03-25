import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { LineChart, Line, PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useAuthStore, useTradingStore } from '../store/store';
import { api } from '../api/client';
import { LogOut, TrendingUp, PieChart as PieChartIcon, AlertCircle, DollarSign, Zap, TrendingDown, Eye } from 'lucide-react';

export default function DashboardPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const { accounts, setAccounts, selectedAccountId, setSelectedAccount } = useTradingStore();
  const [stats, setStats] = useState<any>(null);
  const [positions, setPositions] = useState<any[]>([]);
  const [trades, setTrades] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAccounts();
  }, []);

  useEffect(() => {
    if (selectedAccountId) {
      loadDashboardData();
    }
  }, [selectedAccountId]);

  const loadAccounts = async () => {
    try {
      const response = await api.getAccounts();
      setAccounts(response.data);
      if (response.data.length > 0) {
        setSelectedAccount(response.data[0].id);
      }
    } catch (error) {
      console.error('Failed to load accounts:', error);
    }
  };

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [statsRes, posRes, tradesRes, alertsRes] = await Promise.all([
        api.getStatistics(selectedAccountId!),
        api.getPositions(selectedAccountId!),
        api.getTrades(selectedAccountId!),
        api.getAlerts(selectedAccountId!),
      ]);

      setStats(statsRes.data);
      setPositions(posRes.data);
      setTrades(tradesRes.data.slice(0, 5));
      setAlerts(alertsRes.data.slice(0, 5));
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleDownloadReport = async () => {
    try {
      const response = await api.generateReport(selectedAccountId!);
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `report_${selectedAccountId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
    } catch (error) {
      console.error('Failed to download report:', error);
    }
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div> Loading dashboard...
      </div>
    );
  }

  const pnlTrendData = [
    { week: 'Week 1', pnl: 0 },
    { week: 'Week 2', pnl: 150 },
    { week: 'Week 3', pnl: 200 },
    { week: 'Week 4', pnl: 180 },
    { week: 'Week 5', pnl: 250 },
  ];

  const winLossData = [
    { name: 'Wins', value: stats?.winning_trades || 0 },
    { name: 'Losses', value: stats?.losing_trades || 0 },
  ];

  const COLORS = ['#51cf66', '#ff6b6b'];

  return (
    <div className="dashboard-page">
      <style>{`
        .dashboard-page {
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

        .account-selector {
          padding: 8px 12px;
          border: 1px solid #ddd;
          border-radius: 6px;
          font-size: 14px;
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

        .logout-button:hover {
          background: #ff5252;
          transform: translateY(-2px);
        }

        .container {
          max-width: 1400px;
          margin: 20px auto;
          padding: 0 20px;
        }

        .stat-cards {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 20px;
          margin-bottom: 30px;
        }

        .stat-card {
          background: white;
          border-radius: 12px;
          padding: 20px;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
          display: flex;
          justify-content: space-between;
          align-items: center;
          transition: all 0.3s ease;
        }

        .stat-card:hover {
          transform: translateY(-4px);
          box-shadow: 0 8px 12px rgba(0, 0, 0, 0.15);
        }

        .stat-content {
          flex: 1;
        }

        .stat-label {
          font-size: 12px;
          color: #999;
          text-transform: uppercase;
          margin-bottom: 8px;
          font-weight: 600;
        }

        .stat-value {
          font-size: 28px;
          font-weight: bold;
          color: #333;
        }

        .stat-change {
          font-size: 12px;
          margin-top: 8px;
          display: flex;
          align-items: center;
          gap: 4px;
        }

        .stat-change.positive {
          color: #51cf66;
        }

        .stat-change.negative {
          color: #ff6b6b;
        }

        .stat-icon {
          width: 60px;
          height: 60px;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          border-radius: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          flex-shrink: 0;
        }

        .charts-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
          gap: 20px;
          margin-bottom: 30px;
        }

        .chart-card {
          background: white;
          border-radius: 12px;
          padding: 20px;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        .chart-title {
          font-size: 16px;
          font-weight: bold;
          color: #333;
          margin-bottom: 15px;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .table-card {
          background: white;
          border-radius: 12px;
          padding: 20px;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
          margin-bottom: 30px;
          overflow-x: auto;
        }

        .table {
          width: 100%;
          border-collapse: collapse;
        }

        .table thead {
          background: #f8f9fa;
          border-bottom: 2px solid #ddd;
        }

        .table th,
        .table td {
          padding: 12px;
          text-align: left;
          border-bottom: 1px solid #eee;
          font-size: 14px;
        }

        .table th {
          font-weight: 600;
          color: #333;
        }

        .table tbody tr:hover {
          background: #f8f9fa;
        }

        .status-badge {
          padding: 4px 12px;
          border-radius: 20px;
          font-size: 12px;
          font-weight: 600;
        }

        .status-badge.positive {
          background: #e8f5e9;
          color: #2e7d32;
        }

        .status-badge.negative {
          background: #ffebee;
          color: #c62828;
        }

        .action-buttons {
          display: flex;
          gap: 10px;
        }

        .action-button {
          padding: 6px 12px;
          border: 1px solid #667eea;
          background: white;
          color: #667eea;
          border-radius: 6px;
          cursor: pointer;
          font-size: 12px;
          font-weight: 600;
          transition: all 0.3s ease;
        }

        .action-button:hover {
          background: #667eea;
          color: white;
        }
      `}</style>

      <nav className="navbar">
        <div className="navbar-left">
          <div className="navbar-brand">📊 Zwesta Trading</div>
          <div className="navbar-menu">
            <a href="/dashboard">Dashboard</a>
            <a href="/bots">Trading Bots</a>
            <a href="/accounts">Accounts</a>
            <a href="/market">Market</a>
            <a href="/deposit">Deposit</a>
            <a href="/withdraw">Withdraw</a>
            <a href="/reports">Reports</a>
          </div>
        </div>

        <div className="navbar-right">
          {accounts.length > 0 && (
            <select className="account-selector" value={selectedAccountId || ''} onChange={(e) => setSelectedAccount(Number(e.target.value))}>
              {accounts.map((acc) => (
                <option key={acc.id} value={acc.id}>
                  {acc.name}
                </option>
              ))}
            </select>
          )}
          <div style={{ fontSize: '14px', color: '#666' }}>Welcome, {user?.username}</div>
          <button className="logout-button" onClick={handleLogout}>
            <LogOut size={16} /> Logout
          </button>
        </div>
      </nav>

      <div className="container">
        {/* Stat Cards */}
        <div className="stat-cards">
          <div className="stat-card">
            <div className="stat-content">
              <div className="stat-label">Total P&L</div>
              <div className="stat-value">${stats?.total_pnl?.toFixed(2) || '0.00'}</div>
              <div className="stat-change positive">
                <TrendingUp size={14} /> +{Math.random() * 100}.00 today
              </div>
            </div>
            <div className="stat-icon">
              <DollarSign size={32} />
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-content">
              <div className="stat-label">Win Rate</div>
              <div className="stat-value">{stats?.win_rate?.toFixed(1) || '0'}%</div>
              <div className="stat-change positive">
                <TrendingUp size={14} /> {stats?.winning_trades || 0} wins
              </div>
            </div>
            <div className="stat-icon">
              <TrendingUp size={32} />
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-content">
              <div className="stat-label">Total Trades</div>
              <div className="stat-value">{stats?.total_trades || 0}</div>
              <div className="stat-change">
                <Zap size={14} /> {stats?.losing_trades || 0} losses
              </div>
            </div>
            <div className="stat-icon">
              <Eye size={32} />
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-content">
              <div className="stat-label">Open Positions</div>
              <div className="stat-value">{positions.length}</div>
              <div className="stat-change">
                <AlertCircle size={14} /> {positions.filter((p) => p.pnl > 0).length} profitable
              </div>
            </div>
            <div className="stat-icon">
              <PieChartIcon size={32} />
            </div>
          </div>
        </div>

        {/* Charts */}
        <div className="charts-grid">
          <div className="chart-card">
            <div className="chart-title">
              <TrendingUp size={18} /> P&L Trend
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={pnlTrendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="week" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="pnl" stroke="#667eea" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="chart-card">
            <div className="chart-title">
              <PieChartIcon size={18} /> Win/Loss Ratio
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie data={winLossData} cx="50%" cy="50%" labelLine={false} label={(entry) => `${entry.name}: ${entry.value}`} outerRadius={80} dataKey="value">
                  {COLORS.map((color, index) => (
                    <Cell key={`cell-${index}`} fill={color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recent Trades */}
        {trades.length > 0 && (
          <div className="table-card">
            <h3 className="chart-title">
              <TrendingUp size={18} /> Recent Trades
            </h3>
            <table className="table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Type</th>
                  <th>Entry Price</th>
                  <th>Exit Price</th>
                  <th>P&L</th>
                  <th>Return %</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((trade) => (
                  <tr key={trade.id}>
                    <td>
                      <strong>{trade.symbol}</strong>
                    </td>
                    <td>{trade.type}</td>
                    <td>${trade.entry_price?.toFixed(2)}</td>
                    <td>${trade.exit_price?.toFixed(2)}</td>
                    <td className={trade.pnl > 0 ? 'positive' : 'negative'}>
                      <strong>${trade.pnl?.toFixed(2)}</strong>
                    </td>
                    <td>
                      <span className={`status-badge ${trade.pnl > 0 ? 'positive' : 'negative'}`}>{trade.pnl_percent?.toFixed(2)}%</span>
                    </td>
                    <td>{new Date(trade.closed_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Alerts */}
        {alerts.length > 0 && (
          <div className="table-card">
            <h3 className="chart-title">
              <AlertCircle size={18} /> Recent Alerts
            </h3>
            <table className="table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Symbol</th>
                  <th>Message</th>
                  <th>Severity</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((alert) => (
                  <tr key={alert.id}>
                    <td>{alert.type}</td>
                    <td>{alert.symbol}</td>
                    <td>{alert.message}</td>
                    <td>
                      <span style={{ padding: '4px 8px', borderRadius: '4px', backgroundColor: alert.severity === 'critical' ? '#ffebee' : '#e8f5e9', color: alert.severity === 'critical' ? '#c62828' : '#2e7d32', fontSize: '12px' }}>
                        {alert.severity}
                      </span>
                    </td>
                    <td>{new Date(alert.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '10px ', marginTop: '30px' }}>
          <button className="action-button" onClick={handleDownloadReport}>
            📥 Download Report
          </button>
          <button className="action-button" onClick={() => navigate('/bots')}>
            🤖 Open Bot Manager
          </button>
          <button className="action-button" onClick={() => navigate('/deposit')}>
            💰 Make Deposit
          </button>
        </div>
      </div>
    </div>
  );
}
