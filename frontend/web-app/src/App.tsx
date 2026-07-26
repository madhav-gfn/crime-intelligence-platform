import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import Sidebar from './components/ui/Sidebar';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import NetworkPage from './pages/NetworkPage';
import PatternPage from './pages/PatternPage';
import SociologyPage from './pages/SociologyPage';
import ProfilingPage from './pages/ProfilingPage';
import FinancialPage from './pages/FinancialPage';
import ForecastingPage from './pages/ForecastingPage';
import ExplainPage from './pages/ExplainPage';
import DecisionSupportPage from './pages/DecisionSupportPage';
import ChatPage from './pages/ChatPage';
import AdminPage from './pages/AdminPage';
import { type ReactNode } from 'react';

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main-content">
        {children}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <AppShell>
                <Routes>
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/chat" element={<ChatPage />} />
                  <Route path="/network" element={<NetworkPage />} />
                  <Route path="/patterns" element={<PatternPage />} />
                  <Route path="/sociology" element={<SociologyPage />} />
                  <Route path="/profiling" element={<ProfilingPage />} />
                  <Route path="/financial" element={<FinancialPage />} />
                  <Route path="/forecasting" element={<ForecastingPage />} />
                  <Route path="/explain" element={<ExplainPage />} />
                  <Route path="/decision-support" element={<DecisionSupportPage />} />
                  <Route path="/admin" element={<AdminPage />} />
                  <Route path="*" element={<Navigate to="/dashboard" replace />} />
                </Routes>
              </AppShell>
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
