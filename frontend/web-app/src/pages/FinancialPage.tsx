import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ShieldAlert, Navigation } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import DataTable from '../components/ui/DataTable';
import { financialApi } from '../api/financial';

export default function FinancialPage() {
  const [activeTab, setActiveTab] = useState<'ACCOUNTS' | 'PATTERNS' | 'PATH'>('ACCOUNTS');
  
  const [pathSource, setPathSource] = useState('');
  const [pathTarget, setPathTarget] = useState('');
  const [triggerPath, setTriggerPath] = useState(false);

  const { data: stats } = useQuery({ queryKey: ['finStats'], queryFn: financialApi.stats });

  const { data: accounts, isLoading: loadAccounts } = useQuery({
    queryKey: ['finAccounts'],
    queryFn: () => financialApi.suspiciousAccounts('HIGH', 50),
    enabled: activeTab === 'ACCOUNTS'
  });

  const { data: patterns, isLoading: loadPatterns } = useQuery({
    queryKey: ['finPatterns'],
    queryFn: () => financialApi.patterns(),
    enabled: activeTab === 'PATTERNS'
  });

  const { data: pathData, isLoading: loadPath } = useQuery({
    queryKey: ['finPath', pathSource, pathTarget],
    queryFn: () => financialApi.path(pathSource, pathTarget),
    enabled: triggerPath && !!pathSource && !!pathTarget
  });

  return (
    <div className="page-body flex flex-col h-screen" style={{ maxHeight: '100vh', paddingBottom: '20px' }}>
      <PageHeader 
        title="Financial Crime & AML" 
        eyebrow="Pillar 7"
        description="Transaction monitoring, typology detection, and fund tracing"
      >
        <div className="flex gap-4 items-center">
          <div className="text-right">
            <div className="text-xs text-muted">Analyzed Txns</div>
            <div className="font-mono">{stats?.total_transactions.toLocaleString() || '--'}</div>
          </div>
          <div className="divider w-px h-8" />
          <div className="text-right">
            <div className="text-xs text-muted">Flagged Accounts</div>
            <div className="font-mono text-high">{stats?.flagged_accounts.toLocaleString() || '--'}</div>
          </div>
        </div>
      </PageHeader>

      <div className="tabs">
        <button className={`tab-btn ${activeTab === 'ACCOUNTS' ? 'active' : ''}`} onClick={() => setActiveTab('ACCOUNTS')}>High Risk Accounts</button>
        <button className={`tab-btn ${activeTab === 'PATTERNS' ? 'active' : ''}`} onClick={() => setActiveTab('PATTERNS')}>AML Typologies</button>
        <button className={`tab-btn ${activeTab === 'PATH' ? 'active' : ''}`} onClick={() => setActiveTab('PATH')}>Fund Tracing</button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto">
        {activeTab === 'ACCOUNTS' && (
          <div className="card">
            <h3 className="mb-4">Suspicious Account Monitoring</h3>
            {loadAccounts ? <LoadingSpinner /> : (
              <DataTable 
                columns={[
                  { key: 'account_id', label: 'Account ID', render: a => <span className="font-mono text-cyan">{a.account_id}</span> },
                  { key: 'risk_score', label: 'Risk Score', render: a => <span className="font-mono text-high font-bold">{a.risk_score.toFixed(1)}</span> },
                  { key: 'total_transactions', label: 'Total Txns', render: a => <span className="font-mono">{a.total_transactions}</span> },
                  { key: 'flagged_transactions', label: 'Flagged Txns', render: a => <span className="font-mono text-gold">{a.flagged_transactions}</span> },
                  { key: 'typologies', label: 'Detected Typologies', render: a => (
                    <div className="flex flex-wrap gap-1">
                      {a.typologies.map((t: string) => <span key={t} className="px-1.5 py-0.5 bg-[var(--bg-elevated)] border border-[var(--border)] rounded text-[10px] uppercase">{t}</span>)}
                    </div>
                  ) },
                ]}
                data={accounts?.accounts || []}
              />
            )}
          </div>
        )}

        {activeTab === 'PATTERNS' && (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {loadPatterns ? <LoadingSpinner /> : patterns?.patterns.map((p) => (
              <div key={p.pattern_id} className="card relative overflow-hidden">
                <div className="absolute top-0 right-0 p-4 opacity-10">
                  <ShieldAlert size={64} />
                </div>
                <div className="text-xs text-muted font-mono mb-1">{p.pattern_id}</div>
                <h3 className="mb-4 text-risk-high">{p.typology.replace(/_/g, ' ')}</h3>
                <div className="flex-col gap-2 mb-2">
                  <div className="flex justify-between text-sm"><span className="text-muted">Accounts</span><span className="font-mono">{p.account_count}</span></div>
                  <div className="flex justify-between text-sm"><span className="text-muted">Transactions</span><span className="font-mono">{p.transaction_count}</span></div>
                </div>
                <div className="divider" />
                <div className="text-right">
                  <div className="text-[10px] uppercase text-muted">Total Exposure</div>
                  <div className="font-mono text-xl text-cyan">₹{(p.total_amount / 100000).toFixed(1)}L</div>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'PATH' && (
          <div className="grid grid-cols-2 gap-6 max-w-4xl">
            <div className="card">
              <h3 className="mb-4 flex items-center gap-2"><Navigation size={18}/> Fund Tracing (Graph Search)</h3>
              <form onSubmit={e => { e.preventDefault(); setTriggerPath(true); }} className="flex-col gap-4">
                <div className="input-group">
                  <label className="input-label">Source Account</label>
                  <input type="text" className="input mono" placeholder="ACC-XXX" value={pathSource} onChange={e => {setPathSource(e.target.value); setTriggerPath(false);}} />
                </div>
                <div className="input-group">
                  <label className="input-label">Target Account</label>
                  <input type="text" className="input mono" placeholder="ACC-YYY" value={pathTarget} onChange={e => {setPathTarget(e.target.value); setTriggerPath(false);}} />
                </div>
                <button type="submit" className="btn btn-primary w-full mt-2" disabled={!pathSource || !pathTarget || loadPath}>
                  {loadPath ? 'Tracing...' : 'Trace Funds'}
                </button>
              </form>
            </div>

            <div className="card h-[300px] overflow-y-auto">
              {triggerPath && !loadPath ? (
                pathData?.found ? (
                  <div>
                    <h3 className="text-sm text-cyan mb-4">Direct Path Found</h3>
                    <div className="flex-col gap-2">
                      {pathData.path.map((node, i) => (
                        <div key={node} className="flex items-center gap-3">
                          <div className="w-6 h-6 rounded-full bg-[var(--accent-cyan-dim)] text-cyan flex items-center justify-center text-xs font-bold border border-[rgba(0,212,255,0.3)]">
                            {i + 1}
                          </div>
                          <div className="font-mono text-sm">{node}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="h-full flex items-center justify-center text-muted">
                    No transaction path exists between these accounts.
                  </div>
                )
              ) : (
                <div className="h-full flex items-center justify-center text-muted text-center text-sm">
                  Enter source and target accounts to detect hidden money flows.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
