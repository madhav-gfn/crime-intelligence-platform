import { AlertTriangle } from 'lucide-react';

interface ErrorStateProps {
  message?: string;
}

export default function ErrorState({ message = 'An error occurred while fetching data.' }: ErrorStateProps) {
  return (
    <div className="error-state">
      <AlertTriangle size={32} className="error-icon" />
      <p>{message}</p>
    </div>
  );
}
