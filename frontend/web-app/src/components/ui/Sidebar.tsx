import { NavLink, useNavigate } from 'react-router-dom';
import { Shield, LayoutDashboard, MessageSquare, Network, Flame, BookOpen, UserSearch, DollarSign, TrendingUp, Brain, ClipboardList, Lock, LogOut } from 'lucide-react';
import { motion } from 'framer-motion';
import { useAuthStore, ROLE_RANK } from '../../store/authStore';
import toast from 'react-hot-toast';

const NAV_ITEMS = [
  { label: 'Core', items: [
    { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/chat', icon: MessageSquare, label: 'Chat Interface' },
    { to: '/decision-support', icon: ClipboardList, label: 'Decision Support' },
  ]},
  { label: 'Analytics', items: [
    { to: '/network', icon: Network, label: 'Network Analysis' },
    { to: '/patterns', icon: Flame, label: 'Crime Patterns' },
    { to: '/sociology', icon: BookOpen, label: 'Sociological Insights' },
    { to: '/profiling', icon: UserSearch, label: 'Offender Profiling' },
    { to: '/financial', icon: DollarSign, label: 'Financial Crime' },
    { to: '/forecasting', icon: TrendingUp, label: 'Forecasting' },
    { to: '/explain', icon: Brain, label: 'Explainable AI' },
  ]},
];

const ROLE_COLORS: Record<string, string> = {
  ADMIN: '#a78bfa',
  INVESTIGATOR: 'var(--accent-cyan)',
  ANALYST: 'var(--text-muted)',
};

export default function Sidebar() {
  const { full_name, role, username, logout } = useAuthStore();
  const navigate = useNavigate();

  const initials = full_name?.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase() || '??';

  function handleLogout() {
    logout();
    toast.success('Logged out');
    navigate('/login');
  }

  const isAdmin = role && ROLE_RANK[role] >= ROLE_RANK['ADMIN'];

  return (
    <motion.nav
      className="sidebar"
      initial={{ x: -20, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ duration: 0.25 }}
    >
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">
          <Shield size={18} />
        </div>
        <div>
          <div className="sidebar-logo-text">CrimInt</div>
          <div className="sidebar-logo-sub">Intelligence Platform</div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((section) => (
          <div key={section.label}>
            <div className="sidebar-section-label">{section.label}</div>
            {section.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
              >
                <item.icon className="icon" />
                {item.label}
              </NavLink>
            ))}
          </div>
        ))}

        {/* Admin — only visible to ADMIN role */}
        {isAdmin && (
          <div>
            <div className="sidebar-section-label">System</div>
            <NavLink
              to="/admin"
              className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}
            >
              <Lock className="icon" />
              Admin Audit Log
            </NavLink>
          </div>
        )}
      </nav>

      {/* Footer user badge */}
      <div className="sidebar-footer">
        <div className="user-badge">
          <div className="user-avatar">{initials}</div>
          <div className="user-info">
            <div className="user-name">{full_name || username}</div>
            <div className="user-role" style={{ color: role ? ROLE_COLORS[role] : undefined }}>
              {role}
            </div>
          </div>
          <button className="logout-btn" onClick={handleLogout} title="Logout">
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </motion.nav>
  );
}
