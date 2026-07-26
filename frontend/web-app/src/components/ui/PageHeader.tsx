import { type ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  description?: string;
  eyebrow?: string;
  children?: ReactNode;
}

export default function PageHeader({ title, description, eyebrow, children }: PageHeaderProps) {
  return (
    <div className="page-header flex justify-between items-center">
      <div>
        {eyebrow && <div className="page-header-eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      <div className="flex gap-3">
        {children}
      </div>
    </div>
  );
}
