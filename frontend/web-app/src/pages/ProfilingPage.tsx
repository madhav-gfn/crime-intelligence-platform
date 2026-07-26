import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, Lock, Activity } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ErrorState from '../components/ui/ErrorState';
import RiskBadge from '../components/ui/RiskBadge';
import DataTable from '../components/ui/DataTable';
import { profilingApi } from '../api/profiling';
import { useAuthStore, ROLE_RANK } from '../store/authStore';

export default function ProfilingPage() {
  const { role } = useAuthStore();
  const isInvestigator = role && ROLE_RANK[role] >= ROLE_RANK['INVESTIGATOR'];

  const [activeTab, setActiveTab] = useState<'RISK_LIST' | 'PERSON' | 'PREDICT'>('RISK_LIST');
  const [searchPerson, setSearchPerson] = useState('');
  const [queryPerson, setQueryPerson] = useState('');

  // Manual Prediction State
  const [predAge, setPredAge] = useState<number>(25);
  const [predGender, setPredGender] = useState<'M' | 'F'>('M');
  const [predPriorCases, setPredPriorCases] = useState<number>(0);
  const [predDistinctCrimes, setPredDistinctCrimes] = useState<number>(0);
  const [predDaysSinceFirst, setPredDaysSinceFirst] = useState<number>(100);

  const { data: modelInfo } = useQuery({ queryKey: ['profilingModel'], queryFn: profilingApi.modelInfo });

  const { data: riskList, isLoading: loadList } = useQuery({
    queryKey: ['riskList'],
    queryFn: () => profilingApi.riskList('HIGH', 50),
    enabled: !!isInvestigator && activeTab === 'RISK_LIST'
  });

  const { data: personRisk, isLoading: loadPerson, error: errPerson } = useQuery({
    queryKey: ['personRisk', queryPerson],
    queryFn: () => profilingApi.person(queryPerson),
    enabled: !!queryPerson && !!isInvestigator && activeTab === 'PERSON'
  });

  const { data: prediction, isLoading: loadPred, refetch: runPredict } = useQuery({
    queryKey: ['customPredict', predAge, predGender, predPriorCases, predDistinctCrimes, predDaysSinceFirst],
    queryFn: () => profilingApi.predict({
      age: predAge,
      gender: predGender,
      prior_case_count: predPriorCases,
      distinct_prior_crime_types: predDistinctCrimes,
      days_since_first_case: predDaysSinceFirst
    }),
    enabled: false
  });

  const handlePredict = (e: React.FormEvent) => {
    e.preventDefault();
    runPredict();
  };

  return (
    <div className="page-body flex flex-col h-screen" style={{ maxHeight: '100vh', paddingBottom: '20px' }}>
      <PageHeader 
        title="Offender Profiling" 
        eyebrow="Pillar 5"
        description="Recidivism risk prediction and psychological profiling using Random Forest"
      >
        {modelInfo && (
          <div className="text-xs text-muted text-right">
            <div>Model: {modelInfo.model_name} ({modelInfo.algorithm})</div>
            <div>Accuracy: {(modelInfo.accuracy * 100).toFixed(1)}% | F1: {(modelInfo.f1_score * 100).toFixed(1)}%</div>
          </div>
        )}
      </PageHeader>

      <div className="tabs">
        <button className={`tab-btn ${activeTab === 'RISK_LIST' ? 'active' : ''}`} onClick={() => setActiveTab('RISK_LIST')}>High Risk Watchlist {isInvestigator ? '' : '🔒'}</button>
        <button className={`tab-btn ${activeTab === 'PERSON' ? 'active' : ''}`} onClick={() => setActiveTab('PERSON')}>Person Lookup {isInvestigator ? '' : '🔒'}</button>
        <button className={`tab-btn ${activeTab === 'PREDICT' ? 'active' : ''}`} onClick={() => setActiveTab('PREDICT')}>Manual Prediction</button>
      </div>

      {!isInvestigator && activeTab !== 'PREDICT' ? (
        <div className="card empty-state">
          <Lock size={48} className="text-muted mb-4" />
          <h3>Access Denied</h3>
          <p>Person-level risk profiling requires INVESTIGATOR role.</p>
        </div>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto">
          {activeTab === 'RISK_LIST' && (
            <div className="card">
              <h3 className="mb-4 text-risk-high flex items-center gap-2"><AlertCircle size={18} /> High-Risk Recidivism Watchlist (365 Days)</h3>
              {loadList ? <LoadingSpinner /> : (
                <DataTable 
                  columns={[
                    { key: 'person_id', label: 'ID', render: (p: any) => <span className="font-mono text-cyan">{p.person_id}</span> },
                    { key: 'full_name', label: 'Name' },
                    { key: 'predicted_reoffend_probability_365d', label: 'Reoffend Prob', render: (p: any) => <span className="font-mono text-high font-bold">{(p.predicted_reoffend_probability_365d * 100).toFixed(1)}%</span> },
                    { key: 'prior_case_count', label: 'Prior Cases', render: (p: any) => <span className="font-mono">{p.prior_case_count}</span> },
                    { key: 'distinct_crime_types_count', label: 'Crime Variety', render: (p: any) => <span className="font-mono">{p.distinct_crime_types_count}</span> },
                    { key: 'risk_tier', label: 'Tier', render: (p: any) => <RiskBadge tier={p.risk_tier} /> },
                  ]}
                  data={riskList?.persons || []}
                />
              )}
            </div>
          )}

          {activeTab === 'PERSON' && (
            <div className="flex-col gap-4">
              <form onSubmit={e => { e.preventDefault(); setQueryPerson(searchPerson); }} className="flex gap-2 w-full max-w-md mb-4">
                <input type="text" className="input mono flex-1" placeholder="Enter Person ID (e.g. ACC-000001)" value={searchPerson} onChange={e => setSearchPerson(e.target.value)} />
                <button type="submit" className="btn btn-primary" disabled={!searchPerson}><Search size={16} /> Lookup</button>
              </form>

              {loadPerson ? <LoadingSpinner /> : errPerson ? <ErrorState message="Person not found." /> : personRisk && (
                <div className="card max-w-2xl">
                  <div className="flex justify-between items-start mb-6">
                    <div>
                      <div className="font-mono text-cyan mb-1">{personRisk.person_id}</div>
                      <h2>{personRisk.full_name}</h2>
                      <div className="text-sm text-muted">{personRisk.address_district}, {personRisk.address_state}</div>
                    </div>
                    <RiskBadge tier={personRisk.risk_tier} />
                  </div>

                  <div className="grid grid-cols-2 gap-4 mb-6">
                    <div className="p-4 bg-[var(--bg-elevated)] rounded border border-[var(--border)] text-center">
                      <div className="text-xs text-muted mb-2 uppercase">Reoffend Probability (365d)</div>
                      <div className="text-3xl font-mono font-bold text-high">{(personRisk.predicted_reoffend_probability_365d * 100).toFixed(1)}%</div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="p-2 bg-[var(--bg-elevated)] rounded border border-[var(--border)] text-center">
                        <div className="text-[10px] text-muted uppercase">Age / Gender</div>
                        <div className="font-mono">{personRisk.age} / {personRisk.gender}</div>
                      </div>
                      <div className="p-2 bg-[var(--bg-elevated)] rounded border border-[var(--border)] text-center">
                        <div className="text-[10px] text-muted uppercase">Prior Cases</div>
                        <div className="font-mono">{personRisk.prior_case_count}</div>
                      </div>
                      <div className="p-2 bg-[var(--bg-elevated)] rounded border border-[var(--border)] text-center col-span-2">
                        <div className="text-[10px] text-muted uppercase">Crime Variety</div>
                        <div className="font-mono">{personRisk.distinct_crime_types_count} distinct types</div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'PREDICT' && (
            <div className="grid grid-cols-2 gap-6 max-w-4xl">
              <div className="card">
                <h3 className="mb-4">Simulation Input</h3>
                <form onSubmit={handlePredict} className="flex-col gap-4">
                  <div className="input-group">
                    <label className="input-label">Age</label>
                    <input type="number" className="input mono" value={predAge} onChange={e => setPredAge(Number(e.target.value))} />
                  </div>
                  <div className="input-group">
                    <label className="input-label">Gender</label>
                    <select className="select input mono" value={predGender} onChange={e => setPredGender(e.target.value as 'M' | 'F')}>
                      <option value="M">Male (M)</option>
                      <option value="F">Female (F)</option>
                    </select>
                  </div>
                  <div className="input-group">
                    <label className="input-label">Prior Case Count</label>
                    <input type="number" className="input mono" value={predPriorCases} onChange={e => setPredPriorCases(Number(e.target.value))} />
                  </div>
                  <div className="input-group">
                    <label className="input-label">Distinct Crime Types</label>
                    <input type="number" className="input mono" value={predDistinctCrimes} onChange={e => setPredDistinctCrimes(Number(e.target.value))} />
                  </div>
                  <div className="input-group">
                    <label className="input-label">Days Since First Case</label>
                    <input type="number" className="input mono" value={predDaysSinceFirst} onChange={e => setPredDaysSinceFirst(Number(e.target.value))} />
                  </div>
                  <button type="submit" className="btn btn-primary w-full mt-2" disabled={loadPred}>
                    {loadPred ? 'Computing...' : 'Run Simulation'}
                  </button>
                </form>
              </div>

              <div className="card flex flex-col justify-center items-center text-center">
                {!prediction ? (
                  <div className="text-muted"><Activity size={48} className="mx-auto mb-4 opacity-20" /> Run simulation to see predicted outcome.</div>
                ) : (
                  <>
                    <h3 className="text-sm text-muted uppercase tracking-wider mb-2">Simulated Prediction</h3>
                    <div className="text-5xl font-mono font-bold mb-6" style={{ color: prediction.risk_tier === 'HIGH' ? 'var(--risk-high)' : prediction.risk_tier === 'MEDIUM' ? 'var(--risk-medium)' : 'var(--risk-low)' }}>
                      {(prediction.predicted_reoffend_probability_365d * 100).toFixed(1)}%
                    </div>
                    <RiskBadge tier={prediction.risk_tier} />
                    <div className="text-xs text-muted mt-6 max-w-xs">
                      Based on global historical data for subjects with similar feature sets.
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

import { AlertCircle } from 'lucide-react';
