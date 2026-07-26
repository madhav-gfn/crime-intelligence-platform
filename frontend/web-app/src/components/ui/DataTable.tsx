import type { ReactNode } from 'react';

interface DataTableProps<T> {
  columns: {
    key: string;
    label: string;
    render?: (item: T) => ReactNode;
  }[];
  data: T[];
  onRowClick?: (item: T) => void;
}

export default function DataTable<T>({ columns, data, onRowClick }: DataTableProps<T>) {
  if (!data || data.length === 0) {
    return (
      <div className="table-wrap">
        <div className="empty-state">No data available</div>
      </div>
    );
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key}>{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} onClick={() => onRowClick?.(row)} style={{ cursor: onRowClick ? 'pointer' : 'default' }}>
              {columns.map((col) => (
                <td key={col.key}>
                  {col.render ? col.render(row) : (row as any)[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
