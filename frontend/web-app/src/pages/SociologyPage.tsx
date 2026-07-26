import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, ScatterChart, Scatter, ZAxis } from 'recharts';
import PageHeader from '../components/ui/PageHeader';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import DataTable from '../components/ui/DataTable';
import { sociologyApi } from '../api/sociology';

export default function SociologyPage() {
  const [activeTab, setActiveTab] = useState<'RANKINGS' | 'CORRELATIONS' | 'SCATTER'>('RANKINGS');
  const [sortBy, setSortBy] = useState('literacy_rate');
  const [scatterIndicator, setScatterIndicator] = useState('literacy_rate');

  const { data: rankings, isLoading: loadRank } = useQuery({
    queryKey: ['socioRankings', sortBy],
    queryFn: () => sociologyApi.rankings({ sort_by: sortBy, order: 'desc', limit: 50 }),
    enabled: activeTab === 'RANKINGS'
  });

  const { data: correlations, isLoading: loadCorr } = useQuery({
    queryKey: ['socioCorrelations'],
    queryFn: () => sociologyApi.correlations(),
    enabled: activeTab === 'CORRELATIONS'
  });

  const { data: scatter, isLoading: loadScatter } = useQuery({
    queryKey: ['socioScatter', scatterIndicator],
    queryFn: () => sociologyApi.scatter(scatterIndicator),
    enabled: activeTab === 'SCATTER'
  });

  return (
    <div className="page-body flex flex-col h-screen" style={{ maxHeight: '100vh', paddingBottom: '20px' }}>
      <PageHeader 
        title="Sociological Insights" 
        eyebrow="Pillar 4"
        description="Correlation between census indicators and regional crime rates"
      />

      <div className="tabs">
        <button className={`tab-btn ${activeTab === 'RANKINGS' ? 'active' : ''}`} onClick={() => setActiveTab('RANKINGS')}>District Rankings</button>
        <button className={`tab-btn ${activeTab === 'CORRELATIONS' ? 'active' : ''}`} onClick={() => setActiveTab('CORRELATIONS')}>Correlations</button>
        <button className={`tab-btn ${activeTab === 'SCATTER' ? 'active' : ''}`} onClick={() => setActiveTab('SCATTER')}>Scatter Analysis</button>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto">
        {activeTab === 'RANKINGS' && (
          <div className="card h-full flex flex-col">
            <div className="flex justify-between items-center mb-4">
              <h3>Top Districts by Indicator</h3>
              <select className="select input" value={sortBy} onChange={e => setSortBy(e.target.value)}>
                <option value="literacy_rate">Literacy Rate</option>
                <option value="urbanization_rate">Urbanization Rate</option>
                <option value="unemployment_rate">Unemployment Rate</option>
                <option value="crime_rate_per_100k">Crime Rate (per 100k)</option>
              </select>
            </div>
            
            {loadRank ? <LoadingSpinner /> : (
              <div className="flex-1 min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={rankings?.districts || []} margin={{ bottom: 100 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                    <XAxis dataKey="district" stroke="var(--text-muted)" fontSize={11} angle={-45} textAnchor="end" interval={0} />
                    <YAxis stroke="var(--text-muted)" fontSize={12} />
                    <RechartsTooltip contentStyle={{ backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border)' }} cursor={{ fill: 'var(--bg-hover)' }} />
                    {/* Backend always returns the sorted indicator's value in a generic
                        "value" field, not a field literally named after sortBy. */}
                    <Bar dataKey="value" fill="var(--accent-cyan)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}

        {activeTab === 'CORRELATIONS' && (
          <div className="card">
            <h3 className="mb-4">Pearson Correlation with Crime Rate</h3>
            {loadCorr ? <LoadingSpinner /> : (
              <DataTable 
                columns={[
                  { key: 'indicator', label: 'Census Indicator', render: (c: any) => <span className="uppercase text-xs font-bold text-muted">{c.indicator.replace('_', ' ')}</span> },
                  { key: 'pearson_r', label: 'Pearson r', render: (c: any) => (
                    <span className={`font-mono ${c.pearson_r > 0 ? 'text-risk-high' : c.pearson_r < 0 ? 'text-risk-low' : ''}`}>
                      {c.pearson_r > 0 ? '+' : ''}{c.pearson_r.toFixed(3)}
                    </span>
                  )},
                  { key: 'p_value', label: 'P-Value', render: (c: any) => <span className="font-mono text-xs">{c.p_value.toExponential(2)}</span> },
                  { key: 'strength', label: 'Strength', render: (c: any) => {
                    const abs = Math.abs(c.pearson_r);
                    const label = abs > 0.5 ? 'Strong' : abs > 0.3 ? 'Moderate' : 'Weak';
                    return <span className="text-xs">{label}</span>;
                  }}
                ]}
                data={correlations?.results || []}
              />
            )}
          </div>
        )}

        {activeTab === 'SCATTER' && (
          <div className="card h-full flex flex-col">
            <div className="flex justify-between items-center mb-4">
              <h3>Indicator vs Crime Rate</h3>
              <select className="select input" value={scatterIndicator} onChange={e => setScatterIndicator(e.target.value)}>
                <option value="literacy_rate">Literacy Rate</option>
                <option value="urbanization_rate">Urbanization Rate</option>
                <option value="unemployment_rate">Unemployment Rate</option>
                <option value="sex_ratio">Sex Ratio</option>
              </select>
            </div>

            {loadScatter ? <LoadingSpinner /> : (
              <div className="flex-1 min-h-0 relative">
                {/* The scatter endpoint doesn't return a precomputed Pearson r - that
                    lives on /correlations instead. See the Correlations tab for it. */}
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis type="number" dataKey="x" name={scatterIndicator} stroke="var(--text-muted)" fontSize={12} domain={['auto', 'auto']} />
                    <YAxis type="number" dataKey="y" name="Crime Rate" stroke="var(--text-muted)" fontSize={12} domain={['auto', 'auto']} />
                    <ZAxis type="category" dataKey="district" name="District" />
                    <RechartsTooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border)' }} />
                    <Scatter name="Districts" data={scatter?.points || []} fill="var(--accent-cyan)" />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
