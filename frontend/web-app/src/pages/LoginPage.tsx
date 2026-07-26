import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Lock, User, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { authApi } from '../api/auth';
import { useAuthStore } from '../store/authStore';
import toast from 'react-hot-toast';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    
    try {
      const res = await authApi.login({ username, password });
      login(res.access_token, res.role, res.full_name, username);
      toast.success(`Welcome, ${res.full_name}`);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-bg-glow cyan" />
      <div className="login-bg-glow violet" />
      
      <motion.div 
        className="login-card"
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.4 }}
      >
        <div className="login-logo">
          <div className="login-logo-icon">
            <Shield size={28} />
          </div>
          <div>
            <h1>CrimInt Platform</h1>
            <p>Intelligence Operations Center</p>
          </div>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          {error && (
            <motion.div 
              className="login-error"
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
            >
              {error}
            </motion.div>
          )}

          <div className="input-group">
            <label className="input-label">Username</label>
            <div className="relative flex items-center">
              <User size={16} className="absolute left-3 text-muted pointer-events-none" style={{ position: 'absolute', left: '12px', color: 'var(--text-muted)' }} />
              <input 
                type="text" 
                className="input mono" 
                style={{ paddingLeft: '36px' }}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. analyst_iyer"
                required
              />
            </div>
          </div>

          <div className="input-group">
            <label className="input-label">Password</label>
            <div className="relative flex items-center">
              <Lock size={16} className="absolute left-3 text-muted pointer-events-none" style={{ position: 'absolute', left: '12px', color: 'var(--text-muted)' }} />
              <input 
                type="password" 
                className="input" 
                style={{ paddingLeft: '36px' }}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>
          </div>

          <button 
            type="submit" 
            className="btn btn-primary login-submit"
            disabled={loading || !username || !password}
          >
            {loading ? <Loader2 className="animate-spin" size={18} /> : 'Secure Login'}
          </button>
        </form>
      </motion.div>
    </div>
  );
}
