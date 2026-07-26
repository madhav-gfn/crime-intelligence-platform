import { Loader2 } from 'lucide-react';

export default function LoadingSpinner() {
  return (
    <div className="flex justify-center items-center p-8 w-full">
      <Loader2 className="animate-spin text-cyan" size={32} />
    </div>
  );
}
