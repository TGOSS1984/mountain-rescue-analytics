import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import "./DayOfWeekChart.css";

const SHORT_LABELS = {
  Monday: "Mon", Tuesday: "Tue", Wednesday: "Wed", Thursday: "Thu",
  Friday: "Fri", Saturday: "Sat", Sunday: "Sun",
};
const WEEKEND_DAYS = new Set(["Saturday", "Sunday"]);

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const count = payload[0].value;
  return (
    <div className="dow-chart__tooltip">
      <strong>{label}</strong>
      <div>{count} incident{count === 1 ? "" : "s"}</div>
    </div>
  );
}

export default function DayOfWeekChart({ data, loading }) {
  const rows = (data?.by_day || []).map((d) => ({
    ...d,
    label: SHORT_LABELS[d.day_of_week] || d.day_of_week,
  }));

  return (
    <div className="dow-chart">
      <p className="eyebrow dow-chart__eyebrow">Weekly pattern</p>
      <h2 className="dow-chart__title">Incidents by day of week</h2>

      {loading && <p className="dow-chart__status">Loading…</p>}
      {!loading && rows.length === 0 && (
        <p className="dow-chart__status">No day-of-week data available.</p>
      )}

      {!loading && rows.length > 0 && (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={rows} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
            <XAxis
              dataKey="label"
              stroke="var(--color-slate)"
              fontSize={11}
              fontFamily="JetBrains Mono, monospace"
              tickLine={false}
              axisLine={{ stroke: "var(--color-border)" }}
            />
            <YAxis hide />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(0,0,0,0.04)" }} />
            <Bar dataKey="incident_count" radius={[2, 2, 0, 0]}>
              {rows.map((d) => (
                <Cell
                  key={d.day_of_week}
                  fill={WEEKEND_DAYS.has(d.day_of_week) ? "var(--color-rescue-orange)" : "var(--color-slate)"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}