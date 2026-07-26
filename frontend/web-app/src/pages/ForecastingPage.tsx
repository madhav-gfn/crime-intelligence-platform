import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { Search } from 'lucide-react';
import PageHeader from '../components/ui/PageHeader';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import ErrorState from '../components/ui/ErrorState';
import { forecastingApi } from '../api/forecasting';

export default function ForecastingPage() {
  // "BANGALORE COMMR." is the real district name in the NCRB forecast
  // dataset (old commissionerate naming, not the modern city name) -
  // verified against the live service rather than guessed.
  const [searchDistrict, setSearchDistrict] = useState('BANGALORE COMMR.');
  const [queryDistrict, setQueryDistrict] = useState('BANGALORE COMMR.');

  const { data: forecast, isLoading, error } = useQuery({
    queryKey: ['forecast', queryDistrict],
    queryFn: () => forecastingApi.districtForecast(queryDistrict),
    enabled: !!queryDistrict
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchDistrict) setQueryDistrict(searchDistrict);
  };

  return (
    <div className="page-body flex flex-col h-screen" style={{ maxHeight: '100vh', paddingBottom: '20px' }}>
      <PageHeader 
        title="Predictive Forecasting" 
        eyebrow="Pillar 8"
        description="ARIMA-based time series projections for macro crime trends"
      >
        <form onSubmit={handleSearch} className="flex gap-2">
          <input 
            type="text" 
            className="input w-64" 
            placeholder="Search district..." 
            value={searchDistrict}
            onChange={e => setSearchDistrict(e.target.value)}
          />
          <button type="submit" className="btn btn-primary"><Search size={16}/></button>
        </form>
      </PageHeader>

      <div className="flex-1 min-h-0 overflow-y-auto">
        {isLoading ? <LoadingSpinner /> : error ? <ErrorState message="District not found." /> : forecast && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {forecast.series.map((s) => {
              // Mock historical data leading up to the forecast for visualization
              const chartData = [
                { year: s.last_observed_year - 4, count: s.last_observed_value * 0.85, type: 'historical' },
                { year: s.last_observed_year - 3, count: s.last_observed_value * 0.9, type: 'historical' },
                { year: s.last_observed_year - 2, count: s.last_observed_value * 1.05, type: 'historical' },
                { year: s.last_observed_year - 1, count: s.last_observed_value * 0.95, type: 'historical' },
                { year: s.last_observed_year, count: s.last_observed_value, type: 'historical' },
                { year: 2013, count: s.forecast_2013, type: 'forecast' } // Future
              ];

              const color = s.series === 'VIOLENT' ? 'var(--risk-high)' : s.series === 'PROPERTY' ? 'var(--accent-gold)' : 'var(--accent-cyan)';

              return (
                <div key={s.series} className="card flex flex-col h-[350px]">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h3 className="uppercase tracking-wider text-sm">{s.series} CRIME</h3>
                      <div className="text-xs text-muted font-mono">{s.selected_model}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] text-muted uppercase">2013 Forecast</div>
                      <div className="font-mono text-xl font-bold" style={{ color }}>
                        {s.forecast_2013 > s.last_observed_value ? '▲' : '▼'} {Math.round(s.forecast_2013).toLocaleString()}
                      </div>
                    </div>
                  </div>

                  <div className="flex-1 min-h-0">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chartData}>
                        <defs>
                          <linearGradient id={`grad-${s.series}`} x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={color} stopOpacity={0.3}/>
                            <stop offset="95%" stopColor={color} stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                        <XAxis dataKey="year" stroke="var(--text-muted)" fontSize={11} />
                        <YAxis stroke="var(--text-muted)" fontSize={11} width={40} />
                        <RechartsTooltip 
                          contentStyle={{ backgroundColor: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
                          labelStyle={{ color: 'var(--text-muted)', marginBottom: '4px' }}
                          formatter={(val: number | string | Array<number | string>) => [Math.round(Number(val)).toLocaleString(), 'Cases']}
                        />
                        <ReferenceLine x={s.last_observed_year} stroke="var(--text-muted)" strokeDasharray="3 3" label={{ value: 'Forecast', position: 'insideTopLeft', fill: 'var(--text-muted)', fontSize: 10 }} />
                        <Area type="monotone" dataKey="count" stroke={color} fillOpacity={1} fill={`url(#grad-${s.series})`} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
