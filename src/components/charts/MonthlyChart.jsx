import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import "./MonthlyChart.css";

const MONTH_LABELS = {
  "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
  "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
  "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec",
};

// Alternating orange/yellow bars, matching the palette mockup —
// distinguishes summer's much higher volume without needing a legend.
const BAR_COLORS = ["#E8541E", "#F2C14E"];

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="monthly-chart__tooltip">
      <strong>{label}</strong>
      <div>{payload[0].value} incident{payload[0].value === 1 ? "" : "s"}</div>
    </div>
  );
}

export default function MonthlyChart({ data, loading }) {
  const chartData = (data || []).map((d) => ({
    ...d,
    label: MONTH_LABELS[d.month.slice(5, 7)] || d.month,
  }));

  return (
    <div className="monthly-chart">
      <p className="eyebrow monthly-chart__eyebrow">Seasonal pattern</p>
      <h2 className="monthly-chart__title">Callouts by month</h2>

      {loading && <p className="monthly-chart__status">Loading…</p>}
      {!loading && chartData.length === 0 && (
        <p className="monthly-chart__status">
          No dated incidents match the current filters.
        </p>
      )}

      {!loading && chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={chartData} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
            <XAxis
              dataKey="label"
              stroke="#98A1A8"
              fontSize={11}
              fontFamily="JetBrains Mono, monospace"
              tickLine={false}
              axisLine={{ stroke: "rgba(255,255,255,0.15)" }}
            />
            <YAxis hide />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.05)" }} />
            <Bar dataKey="incident_count" radius={[2, 2, 0, 0]}>
              {chartData.map((_, i) => (
                <Cell key={i} fill={BAR_COLORS[i % 2]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}