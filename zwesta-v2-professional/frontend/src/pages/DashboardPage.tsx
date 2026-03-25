import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore, useTradingStore } from '../store/store'
import { tradingAPI, accountAPI } from '../api/client'
import { Line, Pie } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
} from 'chart.js'
import toast from 'react-hot-toast'
import { TrendingUp, TrendingDown, DollarSign, Activity } from 'lucide-react'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
)

export default function DashboardPage() {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()
  const { statistics, trades, setTrades, setStatistics } = useTradingStore()
  
  const [loading, setLoading] = useState(true)
  const [accounts, setAccounts] = useState<any[]>([])
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null)

  useEffect(() => {
    if (!user) {
      navigate('/login')
      return
    }
    
    loadDashboardData()
  }, [])

  const loadDashboardData = async () => {
    try {
      setLoading(true)
      
      // Load accounts
      const accountsRes = await accountAPI.getAccounts()
      setAccounts(accountsRes.data)
      if (accountsRes.data.length > 0) {
        setSelectedAccountId(accountsRes.data[0].id)
      }
      
      // Load trades
      const tradesRes = await tradingAPI.getTrades()
      setTrades(tradesRes.data)
      
      // Load statistics
      const statsRes = await tradingAPI.getStatistics()
      setStatistics(statsRes.data)
      
      toast.success('Dashboard loaded')
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to load dashboard'
      toast.error(message)
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
    toast.success('Logged out successfully')
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  const stats = statistics || {}
  const profitLoss = (stats.total_profit || 0) - (stats.total_loss || 0)
  const winRate = stats.win_rate || 0

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Zwesta Trading Dashboard</h1>
            <p className="text-gray-600 text-sm">Welcome, {user?.full_name}</p>
          </div>
          <button
            onClick={handleLogout}
            className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition"
          >
            Logout
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {/* Total Profit/Loss */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm mb-1">Total P&L</p>
                <p className="text-2xl font-bold text-gray-900">
                  ${profitLoss.toFixed(2)}
                </p>
              </div>
              <div className={`text-3xl ${profitLoss >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                {profitLoss >= 0 ? <TrendingUp /> : <TrendingDown />}
              </div>
            </div>
          </div>

          {/* Win Rate */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm mb-1">Win Rate</p>
                <p className="text-2xl font-bold text-gray-900">
                  {(winRate * 100).toFixed(1)}%
                </p>
              </div>
              <Activity className="text-blue-500" size={32} />
            </div>
          </div>

          {/* Total Trades */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm mb-1">Total Trades</p>
                <p className="text-2xl font-bold text-gray-900">
                  {stats.total_trades || 0}
                </p>
              </div>
              <DollarSign className="text-purple-500" size={32} />
            </div>
          </div>

          {/* Open Positions */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-600 text-sm mb-1">Open Positions</p>
                <p className="text-2xl font-bold text-gray-900">
                  {(stats.open_positions || 0)}
                </p>
              </div>
              <TrendingUp className="text-green-500" size={32} />
            </div>
          </div>
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
          {/* Profit/Loss Chart */}
          <div className="lg:col-span-2 bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">P&L Trend</h2>
            <Line
              data={{
                labels: ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5'],
                datasets: [
                  {
                    label: 'Cumulative P&L',
                    data: [0, 150, 250, 180, 350],
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    tension: 0.3
                  }
                ]
              }}
              options={{
                responsive: true,
                plugins: {
                  legend: { display: true }
                },
                scales: {
                  y: { beginAtZero: true }
                }
              }}
            />
          </div>

          {/* Win/Loss Pie Chart */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Win/Loss Ratio</h2>
            <Pie
              data={{
                labels: ['Wins', 'Losses'],
                datasets: [
                  {
                    data: [
                      stats.winning_trades || 0,
                      stats.losing_trades || 0
                    ],
                    backgroundColor: [
                      'rgba(34, 197, 94, 0.8)',
                      'rgba(239, 68, 68, 0.8)'
                    ]
                  }
                ]
              }}
            />
          </div>
        </div>

        {/* Recent Trades Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Recent Trades</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Symbol</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">P&L</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {(trades || []).slice(0, 5).map((trade, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm font-medium text-gray-900">{trade.symbol}</td>
                    <td className="px-6 py-4 text-sm text-gray-600">{trade.trade_type}</td>
                    <td className={`px-6 py-4 text-sm font-semibold ${trade.profit_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      ${trade.profit_loss?.toFixed(2) || '0.00'}
                    </td>
                    <td className="px-6 py-4 text-sm">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        trade.status === 'closed' ? 'bg-gray-100 text-gray-800' : 'bg-blue-100 text-blue-800'
                      }`}>
                        {trade.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  )
}
