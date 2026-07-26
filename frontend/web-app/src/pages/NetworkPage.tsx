import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Network as NetworkIcon, Search, Lock, Users, Target, Route } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ErrorState from '../components/ui/ErrorState';
import RiskBadge from '../components/ui/RiskBadge';
import NetworkGraph from '../components/charts/NetworkGraph';
import DataTable from '../components/ui/DataTable';
import { networkApi } from '../api/network';
import { useAuthStore, ROLE_RANK } from '../store/authStore';
import type { PersonNode, CommunityOut } from '../types/api';

export default function NetworkPage() {
  const { role } = useAuthStore();
  const isInvestigator = role && ROLE_RANK[role] >= ROLE_RANK['INVESTIGATOR'];

  const [activeTab, setActiveTab] = useState<'GRAPH' | 'COMMUNITIES' | 'HUBS' | 'OFFENDERS'>('GRAPH');
  const [selectedNode, setSelectedNode] = useState<PersonNode | null>(null);
  const [egoDepth, setEgoDepth] = useState(1);
  const [pathSource, setPathSource] = useState('');
  const [pathTarget, setPathTarget] = useState('');
  const [triggerPath, setTriggerPath] = useState(false);
  const [highlightedCommunity, setHighlightedCommunity] = useState<string[]>([]);

  // 1. Stats (ANALYST baseline)
  const { data: stats } = useQuery({ queryKey: ['networkStats'], queryFn: networkApi.stats });

  // 2. Base Graph
  const { data: graphData, isLoading: graphLoad, error: graphErr } = useQuery({
    queryKey: ['networkGraph'],
    queryFn: () => networkApi.graph({ limit_nodes: 250 }),
    enabled: !!isInvestigator,
  });

  // 3. Ego Graph override
  const { data: egoData, isLoading: egoLoad } = useQuery({
    queryKey: ['egoGraph', selectedNode?.person_id, egoDepth],
    queryFn: () => networkApi.egoNetwork(selectedNode!.person_id, egoDepth),
    enabled: !!selectedNode && !!isInvestigator,
  });

  // 4. Communities
  const { data: communities, isLoading: commLoad } = useQuery({
    queryKey: ['communities'],
    queryFn: () => networkApi.communities(3),
    enabled: !!isInvestigator && activeTab === 'COMMUNITIES',
  });

  // 5. Hubs
  const { data: hubs, isLoading: hubsLoad } = useQuery({
    queryKey: ['hubs'],
    queryFn: () => networkApi.hubs(20),
    enabled: !!isInvestigator && activeTab === 'HUBS',
  });

  // 6. Path finding
  const { data: pathData, isLoading: pathLoad } = useQuery({
    queryKey: ['networkPath', pathSource, pathTarget],
    queryFn: () => networkApi.path(pathSource, pathTarget),
    enabled: triggerPath && !!isInvestigator && !!pathSource && !!pathTarget,
  });

  const displayGraph = egoData || graphData;

  const handlePathSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setTriggerPath(true);
  };

  return (
    <div className="page-body flex flex-col h-screen" style={{ maxHeight: '100vh', paddingBottom: '20px' }}>
      <PageHeader 
        title="Network Analysis" 
        eyebrow="Pillar 2"
        description="Co-accused relationship graphs, community detection, and key actor identification"
      >
        <div className="flex gap-4 items-center">
          <div className="text-right">
            <div className="text-xs text-muted">Nodes in Network</div>
            <div className="font-mono">{stats?.total_persons_in_network.toLocaleString() || '--'}</div>
          </div>
          <div className="divider w-px h-8" />
          <div className="text-right">
            <div className="text-xs text-muted">Identified Communities</div>
            <div className="font-mono">{stats?.total_communities.toLocaleString() || '--'}</div>
          </div>
        </div>
      </PageHeader>

      <div className="tabs">
        <button className={`tab-btn ${activeTab === 'GRAPH' ? 'active' : ''}`} onClick={() => setActiveTab('GRAPH')}>
          Interactive Graph {isInvestigator ? '' : '🔒'}
        </button>
        <button className={`tab-btn ${activeTab === 'COMMUNITIES' ? 'active' : ''}`} onClick={() => setActiveTab('COMMUNITIES')}>
          Communities {isInvestigator ? '' : '🔒'}
        </button>
        <button className={`tab-btn ${activeTab === 'HUBS' ? 'active' : ''}`} onClick={() => setActiveTab('HUBS')}>
          Key Hubs {isInvestigator ? '' : '🔒'}
        </button>
      </div>

      {!isInvestigator ? (
        <div className="card empty-state">
          <Lock size={48} className="text-muted mb-4" />
          <h3>Access Denied</h3>
          <p>Person-level network analysis requires INVESTIGATOR role.</p>
        </div>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto">
          {activeTab === 'GRAPH' && (
            <div className="flex gap-4 h-full">
              <div className="flex-1 relative border border-[var(--border)] rounded-md bg-[var(--bg-surface)] overflow-hidden h-full min-h-[500px]">
                {graphLoad || egoLoad ? <LoadingSpinner /> : graphErr ? <ErrorState /> : displayGraph && (
                  <>
                    <NetworkGraph 
                      nodes={(displayGraph as any).nodes || []} 
                      edges={(displayGraph as any).edges || []}
                      onNodeClick={setSelectedNode}
                      highlightedNodes={highlightedCommunity}
                      pathHops={pathData?.found ? (pathData as any).hops : []}
                    />
                    
                    {/* Floating Controls */}
                    <div className="absolute top-4 left-4 bg-[var(--bg-elevated)] p-2 rounded-md border border-[var(--border)] shadow-lg flex flex-col gap-2">
                      <div className="text-xs font-bold text-muted uppercase">Legend</div>
                      <div className="flex items-center gap-2 text-xs"><div className="w-3 h-3 rounded-full bg-[var(--risk-high)]" /> High Risk</div>
                      <div className="flex items-center gap-2 text-xs"><div className="w-3 h-3 rounded-full bg-[var(--risk-medium)]" /> Medium Risk</div>
                      <div className="flex items-center gap-2 text-xs"><div className="w-3 h-3 rounded-full bg-[var(--risk-low)]" /> Low Risk</div>
                    </div>
                  </>
                )}
              </div>

              {/* Side Panel */}
              <div className="w-[320px] flex flex-col gap-4 overflow-y-auto h-full">
                {selectedNode ? (
                  <div className="card">
                    <div className="flex justify-between items-start mb-4">
                      <h3 className="text-sm">Node Details</h3>
                      <button className="text-xs text-muted hover:text-primary" onClick={() => { setSelectedNode(null); setEgoDepth(1); }}>Clear</button>
                    </div>
                    <div className="font-mono text-cyan mb-1">{selectedNode.person_id}</div>
                    <div className="font-bold mb-4">{selectedNode.full_name}</div>
                    
                    <div className="flex-col gap-2 mb-4 text-sm">
                      <div className="flex justify-between"><span className="text-muted">Degree</span><span className="font-mono">{selectedNode.degree}</span></div>
                      <div className="flex justify-between"><span className="text-muted">Cases</span><span className="font-mono">{selectedNode.prior_case_count}</span></div>
                      <div className="flex justify-between"><span className="text-muted">Risk</span><RiskBadge tier={selectedNode.risk_tier || ''} /></div>
                    </div>

                    <div className="divider mb-4" />
                    
                    <div className="text-xs text-muted mb-2">Ego Network Depth</div>
                    <div className="flex gap-2 mb-4">
                      {[1, 2, 3].map(d => (
                        <button 
                          key={d} 
                          onClick={() => setEgoDepth(d)}
                          className={`flex-1 py-1 text-xs border rounded ${egoDepth === d ? 'border-cyan text-cyan bg-[var(--accent-cyan-dim)]' : 'border-[var(--border)] text-muted hover:text-primary'}`}
                        >
                          {d}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="card text-center py-8 text-muted text-sm">
                    <Target size={24} className="mx-auto mb-2 opacity-50" />
                    Click any node in the graph to view details and expand ego network.
                  </div>
                )}

                <div className="card">
                  <h3 className="text-sm mb-4 flex items-center gap-2"><Route size={16}/> Path Finder</h3>
                  <form onSubmit={handlePathSearch} className="flex-col gap-3">
                    <input type="text" className="input mono text-xs" placeholder="Source (e.g. ACC-000001)" value={pathSource} onChange={e => {setPathSource(e.target.value); setTriggerPath(false);}} />
                    <input type="text" className="input mono text-xs" placeholder="Target (e.g. ACC-000002)" value={pathTarget} onChange={e => {setPathTarget(e.target.value); setTriggerPath(false);}} />
                    <button type="submit" className="btn btn-secondary btn-sm w-full" disabled={!pathSource || !pathTarget || pathLoad}>
                      {pathLoad ? 'Searching...' : 'Find Path'}
                    </button>
                  </form>
                  {pathData && (
                    <div className="mt-4 p-3 bg-[var(--bg-elevated)] rounded border border-[var(--border)] text-sm">
                      {(pathData as any).found ? (
                        <div>
                          <div className="text-xs text-cyan mb-2">Path found ({(pathData as any).hops.length} hops)</div>
                          <div className="font-mono text-[10px] break-all">{(pathData as any).path.join(' → ')}</div>
                        </div>
                      ) : (
                        <div className="text-muted text-xs">No path exists between these persons.</div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'COMMUNITIES' && (
            <div className="card">
              <h3 className="mb-4">Identified Organized Groups</h3>
              {commLoad ? <LoadingSpinner /> : (
                <DataTable 
                  columns={[
                    { key: 'community_id', label: 'ID', render: (c: CommunityOut) => <span className="font-mono text-cyan">GRP-{c.community_id}</span> },
                    { key: 'size', label: 'Members', render: (c: CommunityOut) => <span className="font-mono">{c.size}</span> },
                    { key: 'core_member_name', label: 'Core Node' },
                    { key: 'total_shared_cases', label: 'Shared Cases', render: (c: CommunityOut) => <span className="font-mono">{c.total_shared_cases}</span> },
                    { key: 'distinct_crime_types', label: 'Crime Types', render: (c: CommunityOut) => <span className="text-xs text-muted">{c.distinct_crime_types.join(', ')}</span> },
                  ]}
                  data={communities || []}
                  onRowClick={(c) => {
                    setHighlightedCommunity(c.member_ids);
                    setActiveTab('GRAPH');
                  }}
                />
              )}
            </div>
          )}

          {activeTab === 'HUBS' && (
            <div className="card">
              <h3 className="mb-4">Key Network Hubs (Betweenness Centrality)</h3>
              {hubsLoad ? <LoadingSpinner /> : (
                <DataTable 
                  columns={[
                    { key: 'person_id', label: 'Person ID', render: (h: any) => <span className="font-mono text-cyan">{h.person_id}</span> },
                    { key: 'full_name', label: 'Name' },
                    { key: 'degree', label: 'Degree (Direct Links)', render: (h: any) => <span className="font-mono">{h.degree}</span> },
                    { key: 'betweenness', label: 'Betweenness Score', render: (h: any) => <span className="font-mono">{(h.betweenness * 100).toFixed(2)}</span> },
                    { key: 'risk_tier', label: 'Risk', render: (h: any) => <RiskBadge tier={h.risk_tier} /> },
                  ]}
                  data={hubs || []}
                  onRowClick={(h) => {
                    setSelectedNode(h);
                    setActiveTab('GRAPH');
                  }}
                />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
