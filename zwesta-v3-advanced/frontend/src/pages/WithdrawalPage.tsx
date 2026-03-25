import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/store';
import { LogOut } from 'lucide-react';

export default function WithdrawalPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="withdrawal-page">
      <style>{`
        .withdrawal-page {
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

        .navbar-brand {
          font-size: 24px;
          font-weight: bold;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
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
        }

        .form-input:focus {
          outline: none;
          border-color: #667eea;
        }

        .submit-button {
          width: 100%;
          padding: 12px;
          background: linear-gradient(135deg, #ff6b6b 0%, #ff5252 100%);
          color: white;
          border: none;
          border-radius: 8px;
          font-weight: 600;
          font-size: 16px;
          cursor: pointer;
          transition: all 0.3s ease;
        }

        .submit-button:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 12px rgba(255, 107, 107, 0.4);
        }
      `}</style>

      <nav className="navbar">
        <div className="navbar-brand">🏦 Withdrawals</div>
        <div>
          <button className="logout-button" onClick={handleLogout}>
            <LogOut size={16} /> Logout
          </button>
        </div>
      </nav>

      <div className="container">
        <div className="form-card">
          <div className="form-header">
            <h1 className="form-title">Withdraw Funds</h1>
            <p className="form-subtitle">Request withdrawal to your bank account</p>
          </div>

          <form>
            <div className="form-group">
              <label className="form-label">Amount (USD)</label>
              <input type="number" className="form-input" placeholder="Enter withdrawal amount" required />
            </div>

            <div className="form-group">
              <label className="form-label">Bank Account</label>
              <input type="text" className="form-input" placeholder="Your bank account number" required />
            </div>

            <div className="form-group">
              <label className="form-label">Bank Name</label>
              <input type="text" className="form-input" placeholder="Your bank name" required />
            </div>

            <button type="submit" className="submit-button">
              Request Withdrawal
            </button>
          </form>

          <div style={{ marginTop: '20px', padding: '15px', background: '#fff3cd', borderRadius: '6px', fontSize: '13px', color: '#856404' }}>
            <strong>⚠️ Info:</strong> Withdrawals typically process within 3-5 business days. You'll receive email confirmation.
          </div>
        </div>
      </div>
    </div>
  );
}
