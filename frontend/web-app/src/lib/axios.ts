import axios from 'axios';
import { useAuthStore } from '../store/authStore';

// Factory: creates a pre-configured axios instance for a given backend service
function makeClient(baseURL: string) {
  const instance = axios.create({ baseURL, timeout: 15000 });

  // Inject Bearer token from Zustand store on every request
  instance.interceptors.request.use((config) => {
    const token = useAuthStore.getState().token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });

  // Global 401 handler — auto-logout if token is rejected
  instance.interceptors.response.use(
    (res) => res,
    (err) => {
      if (err.response?.status === 401) {
        useAuthStore.getState().logout();
      }
      return Promise.reject(err);
    }
  );

  return instance;
}

// One client per service — base URLs come from Vite env variables
// Change the .env.local values to point to deployed Zoho Catalyst URLs
export const authClient         = makeClient(import.meta.env.VITE_AUTH_URL            || 'http://localhost:8020');
export const chatClient         = makeClient(import.meta.env.VITE_CHAT_URL             || 'http://localhost:8022');
export const networkClient      = makeClient(import.meta.env.VITE_NETWORK_URL          || 'http://localhost:8010');
export const patternsClient     = makeClient(import.meta.env.VITE_PATTERNS_URL         || 'http://localhost:8011');
export const sociologyClient    = makeClient(import.meta.env.VITE_SOCIOLOGY_URL        || 'http://localhost:8012');
export const profilingClient    = makeClient(import.meta.env.VITE_PROFILING_URL        || 'http://localhost:8016');
export const decisionClient     = makeClient(import.meta.env.VITE_DECISION_SUPPORT_URL || 'http://localhost:8018');
export const financialClient    = makeClient(import.meta.env.VITE_FINANCIAL_URL        || 'http://localhost:8013');
export const forecastingClient  = makeClient(import.meta.env.VITE_FORECASTING_URL      || 'http://localhost:8014');
export const explainClient      = makeClient(import.meta.env.VITE_EXPLAINABILITY_URL   || 'http://localhost:8021');
