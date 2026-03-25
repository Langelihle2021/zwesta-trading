# Zwesta Trading System v2 - Web Dashboard

Modern React-based web dashboard for the Zwesta Trading System

## Features

- ✅ **Responsive Design** - Works on desktop, tablet, and mobile
- ✅ **Real-time Charts** - Profit/loss trends, win/loss ratios
- ✅ **Trading Dashboard** - View trades, positions, and statistics
- ✅ **Account Management** - Manage multiple trading accounts
- ✅ **Alert Configuration** - Set up trading alerts
- ✅ **Report Generation** - Download trading reports
- ✅ **Dark Mode Support** - Easy on the eyes

## Setup

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

## Technology Stack

- **React 18** - UI framework
- **Vite** - Fast build tool
- **Tailwind CSS** - Styling
- **Chart.js** - Data visualization
- **Zustand** - State management
- **Axios** - HTTP client
- **React Router** - Client-side routing
- **TypeScript** - Type safety

## Project Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts          # API integration
│   ├── pages/
│   │   ├── LoginPage.tsx      # Authentication
│   │   └── DashboardPage.tsx  # Main dashboard
│   ├── store/
│   │   └── store.ts           # Zustand state
│   ├── App.tsx                # Root component
│   ├── main.tsx               # Entry point
│   └── index.css              # Global styles
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

## API Connection

The frontend connects to the FastAPI backend at `http://localhost:8000/api`

To change the API endpoint, set the `VITE_API_URL` environment variable:

```bash
VITE_API_URL=https://api.example.com npm run dev
```

## Authentication

- Login credentials are stored in `localStorage`
- JWT tokens are automatically attached to API requests
- Expired tokens trigger automatic logout

## Development

```bash
# Run with hot reload
npm run dev

# Build optimized version
npm run build

# Preview production build
npm run preview
```

## Pages

### Login Page (`/login`)
- Username/password authentication
- Demo credentials available
- Signup link

### Dashboard (`/dashboard`)
- Account overview
- Profit/loss statistics
- Win rate visualization
- Recent trades table
- Market data charts
