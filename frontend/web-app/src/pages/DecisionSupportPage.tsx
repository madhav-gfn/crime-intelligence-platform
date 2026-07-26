import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, Lock } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ErrorState from '../components/ui/ErrorState';
import RiskBadge from '../components/ui/RiskBadge';
import { decisionApi } from '../api/decision-support';
import { useAuthStore, ROLE_RANK } from '../store/authStore';

export default function DecisionSupportPage() {
  const { role } = useAuthStore();
  const isInvestigator = role && ROLE_RANK[role] >= ROLE_RANK['INVESTIGATOR'];
  const [activeTab, setActiveTab] = useState<'PRIORITY' | 'DOSSIER' | 'DISTRICT'>('PRIORITY');
  
  const [searchPersonId, setSearchPersonId] = useState('');
  const [searchDistrict, setSearchDistrict] = useState('');
  
  const [queryPersonId, setQueryPersonId] = useState('');
  const [queryDistrict, setQueryDistrict] = useState('');

  const { data: casesData, isLoading: casesLoad, error: casesErr } = useQuery({
    queryKey: ['casePriority'],
    queryFn: () => decisionApi.casePriority({ limit: 100 }),
    enabled: activeTab === 'PRIORITY',
  });

  const { data: dossier, isLoading: dossierLoad, error: dossierErr } = useQuery({
    queryKey: ['personDossier', queryPersonId],
    queryFn: () => decisionApi.personDossier(queryPersonId),
    enabled: !!queryPersonId && isInvestigator && activeTab === 'DOSSIER',
  });

  const { data: briefing, isLoading: briefLoad, error: briefErr } = useQuery({
    queryKey: ['districtBriefing', queryDistrict],
    queryFn: () => decisionApi.districtBriefing(queryDistrict),
    enabled: !!queryDistrict && activeTab === 'DISTRICT',
  });

  const handlePersonSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchPersonId) setQueryPersonId(searchPersonId);
  };

  const handleDistrictSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchDistrict) setQueryDistrict(searchDistrict);
  };

  return (
    <div className="page-body">
      <PageHeader 
        title="Decision Support" 
        eyebrow="Pillar 6"
        description="Aggregate synthesis of case priority, person dossiers, and district briefings"
      />

      <div className="tabs">
        <button className={`tab-btn ${activeTab === 'PRIORITY' ? 'active' : ''}`} onClick={() => setActiveTab('PRIORITY')}>
          Case Priority Queue
        </button>
        <button className={`tab-btn ${activeTab === 'DOSSIER' ? 'active' : ''}`} onClick={() => setActiveTab('DOSSIER')}>
          Person Dossier {isInvestigator ? '' : '🔒'}
        </button>
        <button className={`tab-btn ${activeTab === 'DISTRICT' ? 'active' : ''}`} onClick={() => setActiveTab('DISTRICT')}>
          District Briefing
        </button>
      </div>

      {activeTab === 'PRIORITY' && (
        <div className="card">
          <h3 className="mb-4">Unresolved Priority Cases</h3>
          {casesLoad ? <LoadingSpinner /> : casesErr ? <ErrorState /> : (
            <div className="three-col">
              {['HIGH', 'MEDIUM', 'LOW'].map((tier) => {
                const tierCases = casesData?.cases.filter(c => c.priority_tier === tier) || [];
                return (
                  <div key={tier} className="flex-col gap-3">
                    <div className="card-title flex justify-between items-center mb-2">
                      <span>{tier} PRIORITY</span>
                      <span className="risk-badge" style={{ padding: '2px 6px', fontSize: '10px' }}>{tierCases.length}</span>
                    </div>
                    {tierCases.slice(0, 10).map((c) => (
                      <div key={c.fir_id} className="p-4 bg-[var(--bg-elevated)] border border-[var(--border)] rounded-md hover:border-[var(--border-bright)] cursor-pointer transition-colors">
                        <div className="flex justify-between items-start mb-2">
                          <div className="font-mono text-cyan text-sm">{c.fir_id}</div>
                          <span className="font-mono font-bold">{c.priority_score.toFixed(1)}</span>
                        </div>
                        <div className="text-xs text-muted mb-2">{c.district}, {c.state} • {c.crime_type_code}</div>
                        {c.highest_accused_risk_tier && (
                          <div className="text-xs font-mono text-dim">Highest accused risk: {c.highest_accused_risk_tier}</div>
                        )}
                      </div>
                    ))}
                    {tierCases.length === 0 && (
                      <div className="text-center p-4 border border-dashed border-[var(--border)] rounded-md text-muted text-sm">Empty Queue</div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {activeTab === 'DOSSIER' && (
        <div className="flex-col gap-4">
          {!isInvestigator && (
            <div className="role-gate mb-4 w-full justify-center p-4">
              <Lock size={16} /> Requires INVESTIGATOR role to view person-level dossiers.
            </div>
          )}
          
          <form onSubmit={handlePersonSearch} className="flex gap-2 w-full max-w-md mb-4">
            <input 
              type="text" 
              className="input mono flex-1" 
              placeholder="Enter Person ID (e.g. ACC-000001)" 
              value={searchPersonId}
              onChange={(e) => setSearchPersonId(e.target.value)}
              disabled={!isInvestigator}
            />
            <button type="submit" className="btn btn-primary" disabled={!isInvestigator || !searchPersonId}>
              <Search size={16} /> Search
            </button>
          </form>

          {dossierLoad ? <LoadingSpinner /> : dossierErr ? <ErrorState message="Person not found or service error." /> : dossier && (
            <div className="grid grid-cols-3 gap-6">
              {/* Identity Card */}
              <div className="card col-span-1">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold">{dossier.full_name}</h3>
                  {dossier.offender_risk && <RiskBadge tier={dossier.offender_risk.risk_tier} />}
                </div>
                <div className="font-mono text-cyan mb-4">{dossier.person_id}</div>
                
                <div className="flex-col gap-2 mb-6">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted">Age / Gender</span>
                    <span>{dossier.age} / {dossier.gender}</span>
                  </div>
                  <div className="divider" />
                  <div className="flex justify-between text-sm">
                    <span className="text-muted">Location</span>
                    <span className="text-right">{dossier.address_district}<br/>{dossier.address_state}</span>
                  </div>
                  <div className="divider" />
                  <div className="flex justify-between text-sm">
                    <span className="text-muted">Network Degree</span>
                    <span className="font-mono">{dossier.network_degree} links</span>
                  </div>
                </div>

                {dossier.offender_risk && (
                  <div className="p-4 bg-[var(--bg-elevated)] rounded-md border border-[var(--border)] text-center">
                    <div className="text-xs text-muted uppercase tracking-wider mb-2">Reoffend Risk (365d)</div>
                    <div className="text-2xl font-mono font-bold">
                      {(dossier.offender_risk.predicted_reoffend_probability_365d * 100).toFixed(1)}%
                    </div>
                  </div>
                )}
              </div>

              {/* Cases Timeline */}
              <div className="card col-span-2">
                <h3 className="mb-4">Case History</h3>
                <div className="flex-col gap-3">
                  {dossier.cases.map((c) => (
                    <div key={c.fir_id} className="p-4 border border-[var(--border)] rounded-md flex justify-between items-center bg-[var(--bg-elevated)]">
                      <div>
                        <div className="font-mono text-cyan mb-1">{c.fir_id}</div>
                        <div className="text-sm">{c.crime_type_code}</div>
                        <div className="text-xs text-muted mt-1">{c.district} • {c.date_reported}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-xs uppercase text-muted">{c.role}</div>
                        <div className="text-xs text-muted mt-2 font-mono">{c.status}</div>
                      </div>
                    </div>
                  ))}
                  {dossier.cases.length === 0 && <div className="text-muted">No known cases.</div>}
                </div>

                {dossier.top_associates.length > 0 && (
                  <>
                    <h3 className="mb-4 mt-6">Top Associates</h3>
                    <div className="flex-col gap-2">
                      {dossier.top_associates.map((a) => (
                        <div key={a.person_id} className="flex justify-between text-sm p-2 bg-[var(--bg-elevated)] rounded border border-[var(--border)]">
                          <span className="font-mono text-cyan">{a.person_id}</span>
                          <span className="text-muted">{a.full_name ?? '—'}</span>
                          <span className="font-mono">{a.shared_fir_count} shared case(s)</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'DISTRICT' && (
        <div className="flex-col gap-4">
          <form onSubmit={handleDistrictSearch} className="flex gap-2 w-full max-w-md mb-4">
            <input 
              type="text" 
              className="input flex-1" 
              placeholder="Enter District Name (e.g. Mysuru)" 
              value={searchDistrict}
              onChange={(e) => setSearchDistrict(e.target.value)}
            />
            <button type="submit" className="btn btn-primary" disabled={!searchDistrict}>
              <Search size={16} /> Briefing
            </button>
          </form>

          {briefLoad ? <LoadingSpinner /> : briefErr ? <ErrorState message="District not found or service error." /> : briefing && (
            <div className="card">
              <div className="flex justify-between items-start mb-6">
                <div>
                  <div className="text-sm text-muted uppercase tracking-wider mb-1">District Briefing</div>
                  <h2>{briefing.district}, {briefing.state}</h2>
                </div>
                {briefing.is_hotspot && (
                  <div className="flex items-center gap-2 text-risk-high bg-[var(--risk-high-dim)] px-3 py-1 rounded-full text-xs font-bold border border-[rgba(239,68,68,0.3)]">
                    <div className="pulse-dot" /> ACTIVE HOTSPOT
                  </div>
                )}
              </div>

              <div className="grid grid-cols-4 gap-4 mb-6">
                <div className="p-4 bg-[var(--bg-elevated)] rounded-md border border-[var(--border)]">
                  <div className="text-xs text-muted mb-1">Total Cases</div>
                  <div className="text-xl font-mono">{briefing.total_cases.toLocaleString()}</div>
                </div>
                <div className="p-4 bg-[var(--bg-elevated)] rounded-md border border-[var(--border)]">
                  <div className="text-xs text-muted mb-1">Unresolved Cases</div>
                  <div className="text-xl font-mono text-gold">{briefing.unresolved_cases.toLocaleString()}</div>
                </div>
                <div className="p-4 bg-[var(--bg-elevated)] rounded-md border border-[var(--border)]">
                  <div className="text-xs text-muted mb-1">Volume Percentile</div>
                  <div className="text-xl font-mono">{(briefing.case_volume_percentile_rank * 100).toFixed(1)}%</div>
                </div>
                <div className="p-4 bg-[var(--bg-elevated)] rounded-md border border-[var(--border)]">
                  <div className="text-xs text-muted mb-1">Urbanization</div>
                  <div className="text-xl font-mono">{briefing.socioeconomic?.available ? `${(briefing.socioeconomic.urbanization_rate! * 100).toFixed(1)}%` : 'N/A'}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
