import { motion } from 'framer-motion';
import { type LucideIcon } from 'lucide-react';
import { useEffect, useState } from 'react';

interface StatCardProps {
  label: string;
  value: number | string;
  sub?: string;
  icon?: LucideIcon;
  color?: 'cyan' | 'violet' | 'gold' | 'red' | 'green';
}

export default function StatCard({ label, value, sub, icon: Icon, color = 'cyan' }: StatCardProps) {
  const [displayVal, setDisplayVal] = useState(typeof value === 'number' ? 0 : value);

  useEffect(() => {
    if (typeof value === 'number') {
      let start = 0;
      const end = value;
      if (start === end) {
        setDisplayVal(end);
        return;
      }
      
      const duration = 1000;
      const startTime = performance.now();
      
      const animate = (currTime: number) => {
        const elapsed = currTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // easeOutQuart
        const ease = 1 - Math.pow(1 - progress, 4);
        const current = Math.floor(start + (end - start) * ease);
        
        setDisplayVal(current);
        
        if (progress < 1) {
          requestAnimationFrame(animate);
        } else {
          setDisplayVal(end);
        }
      };
      
      requestAnimationFrame(animate);
    } else {
      setDisplayVal(value);
    }
  }, [value]);

  const formattedValue = typeof displayVal === 'number' 
    ? new Intl.NumberFormat('en-IN').format(displayVal) 
    : displayVal;

  return (
    <motion.div 
      className={`stat-card ${color}`}
      initial={{ scale: 0.95, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      <div className="stat-label">{label}</div>
      <div className="stat-value">{formattedValue}</div>
      {sub && <div className="stat-sub">{sub}</div>}
      {Icon && <Icon className="stat-icon" size={24} />}
    </motion.div>
  );
}
