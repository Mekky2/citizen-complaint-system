import { cn } from '../../utils/cn';

// columns: [{ key, header, render?(row), className? }]
export default function Table({ columns, rows, rowKey = 'id', onRowClick, selectedKey }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700 bg-slate-900/60 text-start text-xs font-bold text-slate-400">
            {columns.map((c) => (
              <th key={c.key} scope="col" className={cn('px-4 py-2.5 text-start', c.className)}>{c.header}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-700/70">
          {rows.map((row) => {
            const k = row[rowKey];
            return (
              <tr
                key={k}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={cn(
                  onRowClick && 'cursor-pointer hover:bg-slate-700/40',
                  selectedKey != null && selectedKey === k && 'bg-blue-500/10',
                )}
              >
                {columns.map((c) => (
                  <td key={c.key} className={cn('px-4 py-3 align-middle text-slate-200', c.className)}>
                    {c.render ? c.render(row) : row[c.key]}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
