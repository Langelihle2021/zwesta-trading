import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore, useTradingStore } from '../store/store';
import { api } from '../api/client';
import { LogOut } from 'lucide-react';

export default function MarketMonitorPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const { selectedAccountId } = useTradingStore();
  const [prices, setPrices] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPrices();
    const interval = setInterval(loadPrices, 5000); // Update every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const loadPrices = async () => {
    try {
      const symbols = 'BTC,ETH,EURUSD,GBPUSD,USDJPY';
      const response = await api.getPrices(symbols);
      setPrices(response.data);
    } catch (error) {
      console.error('Failed to load prices:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="market-monitor-page">
      <style>{`
        .market-monitor-page {
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
          max-width: 1200px;
          margin: 20px auto;
          padding: 0 20px;
        }

        .section-header {
          background: white;
          padding: 20px;
          border-radius: 12px;
          margin-bottom: 20px;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        .section-title {
          font-size: 24px;
          font-weight: bold;
          color: #333;
          margin: 0;
        }

        .prices-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
          gap: 20px;
        }

        .price-card {
          background: white;
          border-radius: 12px;
          padding: 25px;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
          transition: all 0.3s ease;
          border-left: 4px solid #667eea;
        }

        .price-card:hover {
          transform: translateY(-4px);
          box-shadow: 0 8px 12px rgba(0, 0, 0, 0.15);
        }

        .price-symbol {
          font-size: 16px;
          font-weight: bold;
          color: #333;
          margin-bottom: 10px;
        }

        .price-value {
          font-size: 28px;
          font-weight: bold;
          color: #667eea;
          margin-bottom: 10px;
        }

        .price-change {
          font-size: 14px;
          display: flex;
          align-items: center;
          gap: 4px;
        }

        .price-change.positive {
          color: #51cf66;
        }

        .price-change.negative {
          color: #ff6b6b;
        }

        .loading {
          display: flex;
          justify-content: center;
          align-items: center;
          min-height: 400px;
        }

        .spinner {
          border: 4px solid #f3f3f3;
          border-top: 4px solid #667eea;
          border-radius: 50%;
          width: 40px;
          height: 40px;
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>

      <nav className="navbar">
        <div className="navbar-left">
          <div className="navbar-brand">📈 Market Monitor</div>
          <div className="navbar-menu">
            <a href="/dashboard">Dashboard</a>
            <a href="/bots">Bots</a>
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
          <h1 className="section-title">Live Market Prices</h1>
          <p style={{ margin: '10px 0 0 0', color: '#666', fontSize: '14px' }}>Real-time crypto and forex prices</p>
        </div>

        {loading ? (
          <div className="loading">
            <div className="spinner"></div>
          </div>
        ) : (
          <div className="prices-grid">
            {prices.map((price, index) => (
              <div key={index} className="price-card">
                <div className="price-symbol">{price.symbol}</div>
                <div className="price-value">${price.price?.toFixed(2)}</div>
                <div className={`price-change ${price.change_24h >= 0 ? 'positive' : 'negative'}`}>
                  {price.change_24h >= 0 ? '📈' : '📉'} {Math.abs(price.change_24h)?.toFixed(2)}% (24h)
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
