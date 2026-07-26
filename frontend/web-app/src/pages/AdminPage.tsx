import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Lock, Shield, RefreshCw } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ErrorState from '../components/ui/ErrorState';
import DataTable from '../components/ui/DataTable';
import { authApi } from '../api/auth';
import { useAuthStore, ROLE_RANK } from '../store/authStore';

export default function AdminPage() {
  const { role } = useAuthStore();
  const isAdmin = !!role && ROLE_RANK[role] >= ROLE_RANK['ADMIN'];
  const [limit, setLimit] = useState(100);

  const { data: auditLog, isLoading, error, refetch, isRefetching } = useQuery({
    queryKey: ['auditLog', limit],
    queryFn: () => authApi.auditLog(limit),
    enabled: isAdmin
  });

  if (!isAdmin) {
    return (
      <div className="page-body flex items-center justify-center h-full">
        <div className="card empty-state max-w-md w-full">
          <Lock size={48} className="text-risk-high mb-4" />
          <h2 className="text-risk-high mb-2">System Restricted</h2>
          <p>You must have the ADMIN role to access this area.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-body flex flex-col h-screen" style={{ maxHeight: '100vh', paddingBottom: '20px' }}>
      <PageHeader 
        title="Admin Audit Console" 
        eyebrow="System Security"
        description="Global authentication and authorization event stream"
      >
        <button 
          className="btn btn-secondary"
          onClick={() => refetch()}
          disabled={isRefetching}
        >
          <RefreshCw size={16} className={isRefetching ? 'animate-spin' : ''} /> Refresh
        </button>
      </PageHeader>

      <div className="card flex-1 min-h-0 flex flex-col">
        <div className="flex justify-between items-center mb-4">
          <h3 className="flex items-center gap-2"><Shield size={18}/> Access Logs</h3>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted">Show recent:</span>
            <select className="select input input-sm" value={limit} onChange={e => setLimit(Number(e.target.value))}>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={500}>500</option>
            </select>
          </div>
        </div>

        {isLoading ? <LoadingSpinner /> : error ? <ErrorState message="Failed to load audit logs" /> : (
          <div className="flex-1 min-h-0 overflow-y-auto border border-[var(--border)] rounded-md">
            <DataTable 
              columns={[
                { key: 'timestamp', label: 'Timestamp', render: l => <span className="font-mono text-xs text-muted">{new Date(l.timestamp).toLocaleString()}</span> },
                { key: 'username', label: 'User', render: l => <span className="font-mono text-cyan">{l.username}</span> },
                { key: 'event', label: 'Event Type', render: l => <span className="text-xs uppercase tracking-wider">{l.event}</span> },
                { key: 'success', label: 'Status', render: l => (
                  <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase ${l.success ? 'bg-[var(--risk-low-dim)] text-risk-low' : 'bg-[var(--risk-high-dim)] text-risk-high'}`}>
                    {l.success ? 'SUCCESS' : 'FAILURE'}
                  </span>
                )},
                { key: 'detail', label: 'Details', render: l => <span className="text-xs">{l.detail}</span> },
              ]}
              data={auditLog?.entries || []}
            />
          </div>
        )}
      </div>
    </div>
  );
}
