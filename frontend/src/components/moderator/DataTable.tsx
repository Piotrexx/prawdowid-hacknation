import type { ReactNode } from "react";

interface DataTableProps {
  caption: string;
  columns: string[];
  rows: Array<{ key: string | number; cells: ReactNode[] }>;
  emptyText?: string;
}

/** Wide tables scroll inside their own focusable region, so the page itself never scrolls sideways. */
export function DataTable({
  caption,
  columns,
  rows,
  emptyText = "Brak danych.",
}: DataTableProps) {
  if (rows.length === 0) {
    return (
      <div>
        <p className="font-semibold">{caption}</p>
        <p className="mt-1 text-muted">{emptyText}</p>
      </div>
    );
  }

  return (
    <div
      role="region"
      aria-label={caption}
      tabIndex={0}
      className="overflow-x-auto rounded-xl border border-line bg-surface"
    >
      <table className="w-full border-collapse text-left">
        <caption className="px-4 pt-3 pb-2 text-left font-semibold">{caption}</caption>
        <thead>
          <tr className="border-b border-line-strong">
            {columns.map((column) => (
              <th key={column} scope="col" className="px-3 py-2 font-semibold whitespace-nowrap">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className="border-b border-line align-top last:border-b-0">
              {row.cells.map((cell, index) => (
                <td key={index} className="px-3 py-2">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface CountTableProps {
  caption: string;
  keyHeader: string;
  counts: Record<string, number>;
  label?: (key: string) => string;
}

export function CountTable({ caption, keyHeader, counts, label }: CountTableProps) {
  const rows = Object.entries(counts)
    .sort(([, a], [, b]) => b - a)
    .map(([key, count]) => ({
      key,
      cells: [label ? label(key) : key, <span key="count" className="tabular-nums">{count}</span>],
    }));
  return <DataTable caption={caption} columns={[keyHeader, "Liczba"]} rows={rows} />;
}
