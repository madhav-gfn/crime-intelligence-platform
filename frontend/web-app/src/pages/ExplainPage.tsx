import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Brain, Search, Lock, Info } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Cell, ReferenceLine } from 'recharts';
import PageHeader from '../components/ui/PageHeader';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ErrorState from '../components/ui/ErrorState';
import RiskBadge from '../components/ui/RiskBadge';
import { explainApi } from '../api/explainability';
import { useAuthStore, ROLE_RANK } from '../store/authStore';

export default function ExplainPage() {
  const { role } = useAuthStore();
  const isInvestigator = role && ROLE_RANK[role] >= ROLE_RANK['INVESTIGATOR'];

  const [searchPerson, setSearchPerson] = useState('');
  const [queryPerson, setQueryPerson] = useState('');

  const { data: info } = useQuery({ queryKey: ['explainInfo'], queryFn: explainApi.methodology });

  const { data: explanation, isLoading, error } = useQuery({
    queryKey: ['explainPerson', queryPerson],
    queryFn: () => explainApi.personExplanation(queryPerson),
    enabled: !!queryPerson && !!isInvestigator
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchPerson) setQueryPerson(searchPerson);
  };

  return (
    <div className="page-body flex flex-col h-screen" style={{ maxHeight: '100vh', paddingBottom: '20px' }}>
      <PageHeader 
        title="Explainable AI (SHAP)" 
        eyebrow="Pillar 9"
        description="Transparent machine learning interpreting recidivism risk factors"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-0 overflow-y-auto">
        
        {/* Left Column: Context & Input */}
        <div className="flex flex-col gap-6 col-span-1">
          <div className="card">
            <h3 className="mb-4">Investigate Model Decision</h3>
            {!isInvestigator ? (
              <div className="role-gate">
                <Lock size={16} /> Requires INVESTIGATOR role
              </div>
            ) : (
              <form onSubmit={handleSearch} className="flex gap-2">
                <input 
                  type="text" 
                  className="input mono flex-1" 
                  placeholder="Person ID (ACC-000001)" 
                  value={searchPerson}
                  onChange={e => setSearchPerson(e.target.value)}
                />
                <button type="submit" className="btn btn-primary" disabled={!searchPerson}><Search size={16}/></button>
              </form>
            )}
          </div>

          <div className="card bg-[var(--accent-cyan-dim)] border-[rgba(0,212,255,0.3)]">
            <div className="flex items-center gap-2 text-cyan font-bold mb-2">
              <Info size={16} /> How to read this
            </div>
            <p className="text-xs text-primary leading-relaxed">
              SHAP (SHapley Additive exPlanations) values break down a prediction to show the impact of each feature. 
              <br/><br/>
              <span className="text-risk-high font-bold">Red bars (Positive SHAP)</span> push the recidivism risk higher. 
              <br/>
              <span className="text-risk-low font-bold">Green bars (Negative SHAP)</span> push the risk lower.
            </p>
            {info && (
              <div className="mt-4 pt-4 border-t border-[rgba(0,212,255,0.2)] text-[10px] text-cyan font-mono">
                Methodology: {info.method} <br/>
                Scope: {info.scope}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Output */}
        <div className="col-span-1 lg:col-span-2">
          <div className="card h-full flex flex-col min-h-[500px]">
            {isLoading ? <LoadingSpinner /> : error ? <ErrorState message="Person not found or model explanation failed." /> : explanation ? (
              <>
                <div className="flex justify-between items-start mb-6 pb-6 border-b border-[var(--border)]">
                  <div>
                    <div className="font-mono text-cyan text-sm mb-1">{explanation.person_id}</div>
                    <h2>{explanation.full_name}</h2>
                  </div>
                  <div className="text-right flex flex-col items-end gap-2">
                    <RiskBadge tier={explanation.risk_tier} />
                    <div className="font-mono text-xl mt-1">
                      Final Prob: <span className="text-high font-bold">{(explanation.predicted_reoffend_probability_365d * 100).toFixed(1)}%</span>
                    </div>
                    <div className="text-xs text-muted font-mono">
                      Base Prob: {(explanation.base_probability * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>

                <h3 className="mb-4 text-sm uppercase text-muted tracking-widest">SHAP Value Breakdown</h3>
                <div className="flex-1 min-h-0">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart 
                      data={explanation.top_drivers} 
                      layout="vertical" 
                      margin={{ left: 120, right: 30, top: 20, bottom: 20 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                      <XAxis type="number" stroke="var(--text-muted)" fontSize={11} />
                      <YAxis dataKey="feature" type="category" stroke="var(--text-muted)" fontSize={11} width={110} />
                      <RechartsTooltip 
                        contentStyle={{ backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
                        formatter={(val: number, _name: string, props: any) => [
                          `${val > 0 ? '+' : ''}${(val * 100).toFixed(2)}%`, 
                          `Impact (Value: ${props.payload.feature_value})`
                        ]}
                      />
                      <ReferenceLine x={0} stroke="var(--text-muted)" />
                      <Bar dataKey="shap_value" radius={4} barSize={24}>
                        {explanation.top_drivers.map((entry: any, index: number) => (
                          <Cell key={`cell-${index}`} fill={entry.shap_value > 0 ? 'var(--risk-high)' : 'var(--risk-low)'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-muted">
                <Brain size={48} className="opacity-20 mb-4" />
                <p>Search for an offender to interpret the model's decision logic.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
