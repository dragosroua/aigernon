"use client";

interface RealmChartProps {
  assess: number;
  decide: number;
  do: number;
}

export function RealmChart({ assess, decide, do: doValue }: RealmChartProps) {
  const total = assess + decide + doValue;
  if (total === 0) return null;

  const assessPct = Math.round((assess / total) * 100);
  const decidePct = Math.round((decide / total) * 100);
  const doPct = Math.round((doValue / total) * 100);

  return (
    <div className="space-y-2">
      <div className="flex h-3 rounded-full overflow-hidden bg-muted">
        <div
          className="bg-realm-assess transition-all duration-500"
          style={{ width: `${assessPct}%` }}
        />
        <div
          className="bg-realm-decide transition-all duration-500"
          style={{ width: `${decidePct}%` }}
        />
        <div
          className="bg-realm-do transition-all duration-500"
          style={{ width: `${doPct}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>🔴 {assessPct}%</span>
        <span>🟠 {decidePct}%</span>
        <span>🟢 {doPct}%</span>
      </div>
    </div>
  );
}
