import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Cell } from 'recharts';
import { Activity, Map as MapIcon, AlertTriangle } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ErrorState from '../components/ui/ErrorState';
import { patternsApi } from '../api/patterns';

// Helper component to recenter map when hotspots change
function MapRecenter({ center, zoom }: { center: [number, number], zoom: number }) {
  const map = useMap();
  map.setView(center, zoom);
  return null;
}

export default function PatternPage() {
  const [activeTab, setActiveTab] = useState<'HOTSPOTS' | 'TRENDS' | 'SEVERITY' | 'EMERGING'>('HOTSPOTS');
  
  // Filters
  const [filterCrimeType, setFilterCrimeType] = useState<string>('');
  const [filterDistrict, setFilterDistrict] = useState<string>('');

  // 1. Hotspots
  const { data: hotspotsData, isLoading: loadHot, error: errHot } = useQuery({
    queryKey: ['hotspots', filterCrimeType, filterDistrict],
    queryFn: () => patternsApi.hotspots({ crime_type: filterCrimeType || undefined, district: filterDistrict || undefined }),
    enabled: activeTab === 'HOTSPOTS'
  });

  // 2. Trends (Monthly)
  const { data: trendsData, isLoading: loadTrends } = useQuery({
    queryKey: ['trends', 'monthly', filterCrimeType, filterDistrict],
    queryFn: () => patternsApi.trends('monthly', { crime_type: filterCrimeType || undefined, district: filterDistrict || undefined }),
    enabled: activeTab === 'TRENDS'
  });

  // 3. District Severity
  const { data: severityData, isLoading: loadSev } = useQuery({
    queryKey: ['severity'],
    queryFn: () => patternsApi.districtSeverity(),
    enabled: activeTab === 'SEVERITY'
  });

  // 4. Emerging Spikes
  const { data: emergingData, isLoading: loadEmerg } = useQuery({
    queryKey: ['emerging'],
    queryFn: () => patternsApi.emerging(),
    enabled: activeTab === 'EMERGING'
  });

  // Map center logic
  const mapCenter = useMemo<[number, number]>(() => {
    if (hotspotsData?.clusters && hotspotsData.clusters.length > 0) {
      return [hotspotsData.clusters[0].centroid_lat, hotspotsData.clusters[0].centroid_lon];
    }
    return [22.0, 79.0]; // Default India center
  }, [hotspotsData]);

  const severityChartData = useMemo(() => {
    if (!severityData) return [];
    return Object.values(severityData.tiers).flat().sort((a, b) => b.crime_count - a.crime_count).slice(0, 50);
  }, [severityData]);

  const SEVERITY_COLORS: Record<string, string> = {
    'CRITICAL': 'var(--risk-high)',
    'HIGH': 'var(--risk-medium)',
    'MEDIUM': 'var(--accent-gold)',
    'LOW': 'var(--risk-low)'
  };

  return (
    <div className="page-body flex flex-col h-screen" style={{ maxHeight: '100vh', paddingBottom: '20px' }}>
      <PageHeader 
        title="Crime Pattern Analytics" 
        eyebrow="Pillar 3"
        description="Geospatial hotspot clustering and temporal trend detection"
      >
        <div className="flex gap-2">
          <input type="text" className="input input-sm text-xs w-32" placeholder="Filter Crime Type..." value={filterCrimeType} onChange={e => setFilterCrimeType(e.target.value)} />
          <input type="text" className="input input-sm text-xs w-32" placeholder="Filter District..." value={filterDistrict} onChange={e => setFilterDistrict(e.target.value)} />
        </div>
      </PageHeader>

      <div className="tabs">
        <button className={`tab-btn ${activeTab === 'HOTSPOTS' ? 'active' : ''}`} onClick={() => setActiveTab('HOTSPOTS')}>
          <MapIcon size={14} className="inline mr-1" /> Hotspots Map
        </button>
        <button className={`tab-btn ${activeTab === 'TRENDS' ? 'active' : ''}`} onClick={() => setActiveTab('TRENDS')}>
          <Activity size={14} className="inline mr-1" /> Temporal Trends
        </button>
        <button className={`tab-btn ${activeTab === 'SEVERITY' ? 'active' : ''}`} onClick={() => setActiveTab('SEVERITY')}>
          District Severity
        </button>
        <button className={`tab-btn ${activeTab === 'EMERGING' ? 'active' : ''}`} onClick={() => setActiveTab('EMERGING')}>
          <AlertTriangle size={14} className="inline mr-1 text-gold" /> Emerging Spikes
        </button>
      </div>

      <div className="flex-1 min-h-0 relative">
        {activeTab === 'HOTSPOTS' && (
          <div className="h-full card p-0 overflow-hidden relative">
            {loadHot && <div className="absolute inset-0 z-[1000] bg-[rgba(13,20,36,0.8)]"><LoadingSpinner /></div>}
            {errHot && <div className="absolute inset-0 z-[1000] bg-[rgba(13,20,36,0.9)]"><ErrorState /></div>}
            
            {/* @ts-ignore */}
            <MapContainer center={mapCenter} zoom={5} style={{ height: '100%', width: '100%', background: '#0a0f1c' }} zoomControl={false}>
              {/* @ts-ignore */}
              <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" attribution="&copy; OpenStreetMap & Carto" />
              <MapRecenter center={mapCenter} zoom={hotspotsData?.clusters.length ? 8 : 5} />
              
              {hotspotsData?.clusters.map((cluster) => (
                // @ts-ignore
                <CircleMarker
                  key={cluster.cluster_id}
                  center={[cluster.centroid_lat, cluster.centroid_lon]}
                  radius={Math.min(30, Math.max(10, cluster.point_count * 2))}
                  pathOptions={{
                    color: 'var(--risk-high)',
                    fillColor: 'var(--risk-high)',
                    fillOpacity: 0.4,
                    weight: 2
                  }}
                >
                  {/* @ts-ignore */}
                  <Popup className="dark-popup">
                    <div className="font-mono text-xs text-muted mb-1">Cluster #{cluster.cluster_id}</div>
                    <div className="font-bold text-sm mb-1">{cluster.top_district}</div>
                    <div className="text-xs text-high">{cluster.top_crime_type}</div>
                    <div className="divider" />
                    <div className="font-mono text-sm">{cluster.point_count} incidents</div>
                  </Popup>
                </CircleMarker>
              ))}
            </MapContainer>

            <div className="absolute bottom-4 right-4 z-[400] bg-[var(--bg-elevated)] p-3 rounded-md border border-[var(--border)] shadow-lg">
              <div className="text-xs text-muted font-mono mb-1">DBSCAN Clusters</div>
              <div className="text-xl font-mono">{hotspotsData?.cluster_count || 0}</div>
            </div>
          </div>
        )}

        {activeTab === 'TRENDS' && (
          <div className="card h-full flex flex-col">
            <h3 className="mb-4">Monthly Crime Volume</h3>
            {loadTrends ? <LoadingSpinner /> : (
              <div className="flex-1 min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trendsData?.series || []}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                    <XAxis dataKey="period" stroke="var(--text-muted)" fontSize={12} tickMargin={10} />
                    <YAxis stroke="var(--text-muted)" fontSize={12} tickFormatter={v => v.toLocaleString()} />
                    <RechartsTooltip 
                      contentStyle={{ backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '6px' }}
                      itemStyle={{ color: 'var(--accent-cyan)' }}
                    />
                    <Line type="monotone" dataKey="count" stroke="var(--accent-cyan)" strokeWidth={3} dot={{ r: 4, fill: 'var(--bg-surface)' }} activeDot={{ r: 6, fill: 'var(--accent-cyan)' }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}

        {activeTab === 'SEVERITY' && (
          <div className="card h-full flex flex-col">
            <h3 className="mb-4">District Severity Ranking (PCA)</h3>
            {loadSev ? <LoadingSpinner /> : (
              <div className="flex-1 min-h-0 overflow-y-auto pr-4">
                <ResponsiveContainer width="100%" height={severityChartData.length * 40}>
                  <BarChart data={severityChartData} layout="vertical" margin={{ left: 80 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                    <XAxis type="number" stroke="var(--text-muted)" fontSize={12} />
                    <YAxis dataKey="district" type="category" stroke="var(--text-muted)" fontSize={11} width={120} />
                    <RechartsTooltip 
                      contentStyle={{ backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
                      cursor={{ fill: 'var(--bg-hover)' }}
                    />
                    <Bar dataKey="crime_count" radius={[0, 4, 4, 0]}>
                      {severityChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={SEVERITY_COLORS[entry.severity_tier] || 'var(--text-dim)'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}

        {activeTab === 'EMERGING' && (
          <div className="card h-full overflow-y-auto">
            <h3 className="mb-4">Emerging Spikes (Last 90 vs Prior 180 Days)</h3>
            {loadEmerg ? <LoadingSpinner /> : !emergingData?.spikes.length ? (
              <div className="text-muted text-center py-10">No statistically significant spikes detected.</div>
            ) : (
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                {emergingData.spikes.map((spike, i) => (
                  <div key={i} className="p-4 bg-[var(--bg-elevated)] border border-[var(--border)] rounded-md relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-16 h-16 bg-[var(--risk-high)] opacity-10 blur-xl rounded-full" />
                    <div className="text-xs text-muted mb-1">{spike.district}, {spike.state}</div>
                    <div className="font-bold text-sm mb-3">{spike.crime_type}</div>
                    
                    <div className="flex items-end justify-between">
                      <div>
                        <div className="text-[10px] uppercase text-muted">Growth</div>
                        <div className="text-lg font-mono text-high">{(spike.growth_ratio * 100).toFixed(0)}%</div>
                      </div>
                      <div className="text-right">
                        <div className="text-[10px] uppercase text-muted">Recent Cases</div>
                        <div className="text-lg font-mono">{spike.recent_count}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Global CSS override for Leaflet dark mode popups */}
      <style>{`
        .leaflet-popup-content-wrapper { background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border); border-radius: 8px; }
        .leaflet-popup-tip { background: var(--bg-surface); border: 1px solid var(--border); }
        .leaflet-container a.leaflet-popup-close-button { color: var(--text-muted); }
      `}</style>
    </div>
  );
}
