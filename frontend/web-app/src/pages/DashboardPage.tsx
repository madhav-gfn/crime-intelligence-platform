import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Network, Flame, DollarSign, Brain, Users, FileText, ClipboardList } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import StatCard from '../components/ui/StatCard';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ErrorState from '../components/ui/ErrorState';
import RiskBadge from '../components/ui/RiskBadge';
import { networkApi } from '../api/network';
import { patternsApi } from '../api/patterns';
import { financialApi } from '../api/financial';
import { decisionApi } from '../api/decision-support';
import { motion } from 'framer-motion';

export default function DashboardPage() {
  const { data: netStats, isLoading: netLoad, error: netErr } = useQuery({ queryKey: ['netStats'], queryFn: networkApi.stats });
  const { data: patStats, isLoading: patLoad, error: patErr } = useQuery({ queryKey: ['patStats'], queryFn: patternsApi.stats });
  const { data: finStats, isLoading: finLoad, error: finErr } = useQuery({ queryKey: ['finStats'], queryFn: financialApi.stats });
  const { data: decStats, isLoading: decLoad, error: decErr } = useQuery({ queryKey: ['decStats'], queryFn: decisionApi.stats });
  
  const { data: recentCases } = useQuery({
    queryKey: ['recentHighCases'],
    queryFn: () => decisionApi.casePriority({ priority_tier: 'HIGH', limit: 5 })
  });

  const isLoading = netLoad || patLoad || finLoad || decLoad;
  const isError = netErr || patErr || finErr || decErr;

  return (
    <div className="page-body">
      <PageHeader 
        title="Command Center" 
        eyebrow="CrimInt Platform"
        description="Global system overview and priority analytics"
      />

      {isLoading ? <LoadingSpinner /> : isError ? <ErrorState /> : (
        <>
          <div className="stat-grid">
            <StatCard 
              label="Network Persons" 
              value={netStats?.total_persons_in_network || 0} 
              icon={Users} 
              color="cyan"
            />
            <StatCard 
              label="Total FIRs" 
              value={netStats?.total_firs || 0} 
              icon={FileText} 
              color="violet"
            />
            <StatCard 
              label="Districts Tracked" 
              value={patStats?.total_districts_with_crimes || 0} 
              icon={Flame} 
              color="gold"
            />
            <StatCard 
              label="Analyzed AML Txns" 
              value={finStats?.total_transactions || 0} 
              icon={DollarSign} 
              color="green"
            />
            <StatCard 
              label="Unresolved Cases" 
              value={decStats?.total_unresolved_cases || 0} 
              icon={ClipboardList} 
              color="red"
            />
            <StatCard 
              label="Priority HIGH Cases" 
              value={decStats?.high_priority_cases || 0} 
              icon={Brain} 
              color="red"
            />
          </div>

          <div className="two-col mt-4">
            {/* Quick Actions */}
            <div>
              <h3 className="mb-4">Intelligence Pillars</h3>
              <div className="pillar-grid">
                <Link to="/decision-support" className="pillar-tile">
                  <div className="pillar-tile-icon" style={{ background: 'rgba(239, 68, 68, 0.15)', color: 'var(--risk-high)' }}>
                    <ClipboardList size={20} />
                  </div>
                  <div>
                    <div className="pillar-tile-name">Decision Support</div>
                    <div className="pillar-tile-desc">Case prioritization & dossiers</div>
                  </div>
                </Link>

                <Link to="/network" className="pillar-tile">
                  <div className="pillar-tile-icon" style={{ background: 'var(--accent-cyan-dim)', color: 'var(--accent-cyan)' }}>
                    <Network size={20} />
                  </div>
                  <div>
                    <div className="pillar-tile-name">Network Analysis</div>
                    <div className="pillar-tile-desc">Gangs, communities & hubs</div>
                  </div>
                </Link>

                <Link to="/patterns" className="pillar-tile">
                  <div className="pillar-tile-icon" style={{ background: 'var(--accent-gold-dim)', color: 'var(--accent-gold)' }}>
                    <Flame size={20} />
                  </div>
                  <div>
                    <div className="pillar-tile-name">Pattern Analytics</div>
                    <div className="pillar-tile-desc">Geospatial hotspots & trends</div>
                  </div>
                </Link>

                <Link to="/financial" className="pillar-tile">
                  <div className="pillar-tile-icon" style={{ background: 'var(--risk-low-dim)', color: 'var(--risk-low)' }}>
                    <DollarSign size={20} />
                  </div>
                  <div>
                    <div className="pillar-tile-name">Financial Crime</div>
                    <div className="pillar-tile-desc">AML typologies & tracing</div>
                  </div>
                </Link>
              </div>
            </div>

            {/* Recent High Priority Cases */}
            <div>
              <h3 className="mb-4">Active HIGH Priority Alerts</h3>
              <div className="card">
                <div className="flex-col gap-3">
                  {recentCases?.cases.length === 0 ? (
                    <div className="text-muted text-sm py-4">No active high priority cases.</div>
                  ) : (
                    recentCases?.cases.map((c, i) => (
                      <motion.div 
                        key={c.fir_id}
                        initial={{ x: -10, opacity: 0 }}
                        animate={{ x: 0, opacity: 1 }}
                        transition={{ delay: i * 0.1 }}
                        className="flex justify-between items-center p-3 rounded-md bg-[var(--bg-elevated)] border border-[var(--border)]"
                      >
                        <div>
                          <div className="font-mono text-sm text-cyan mb-1">{c.fir_id}</div>
                          <div className="text-xs text-muted">
                            {c.district}, {c.state} • {c.crime_type}
                          </div>
                        </div>
                        <div className="flex items-center gap-4">
                          <div className="text-xs text-muted flex flex-col items-end">
                            <span>Score</span>
                            <span className="font-mono text-primary font-bold">{c.priority_score.toFixed(2)}</span>
                          </div>
                          <RiskBadge tier={c.priority_tier} />
                        </div>
                      </motion.div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
