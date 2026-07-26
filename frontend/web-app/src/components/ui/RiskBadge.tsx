interface RiskBadgeProps {
  tier: string;
}

export default function RiskBadge({ tier }: RiskBadgeProps) {
  if (!tier) return <span className="text-muted">Unknown</span>;
  const upper = tier.toUpperCase();
  const valid = ['HIGH', 'MEDIUM', 'LOW'].includes(upper) ? upper : 'MEDIUM';
  
  return (
    <div className={`risk-badge ${valid}`}>
      <div className="risk-dot" />
      {valid}
    </div>
  );
}
