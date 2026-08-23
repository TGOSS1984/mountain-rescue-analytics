import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import "./TimeOfDayChart.css";

function formatHour(h) {
  return `${String(h).padStart(2, "0")}:00`;
}

// Rough daylight/dusk framing, roughly matching a UK hillwalking day —
// not scientifically precise (daylight hours shift a lot across the
// year), but enough to give the bars some visual context: darker for
// the hours a walker is less likely to have set out.
function isLikelyDaylight(hour) {
  return hour >= 7 && hour <= 19;
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const count = payload[0].value;
  return (
    <div className="timeofday-chart__tooltip">
      <strong>{label}</strong>
      <div>{count} incident{count === 1 ? "" : "s"} started this hour</div>
    </div>
  );
}

export default function TimeOfDayChart({ data, loading, activeTeam }) {
  // OVMRO structurally never has a start time — filtering to just that
  // team means there is nothing this chart can show, not just "less
  // data." Handled as its own explicit state rather than rendering an
  // empty chart and letting someone wonder why.
  const noDataForRegion = activeTeam === "ovmro";

  const chartData = (data?.buckets || []).map((b) => ({
    hour: b.hour,
    label: formatHour(b.hour),
    incident_count: b.incident_count,
  }));

  return (
    <div className="timeofday-chart">
      <p className="eyebrow timeofday-chart__eyebrow">Time of day</p>
      <h2 className="timeofday-chart__title">When incidents start</h2>

      {!noDataForRegion && (
        <p className="timeofday-chart__note">
          Snowdonia isn't included here — OVMRO's incident log records how long each
          operation took, not what time it started, so there's genuinely no start-time
          data for that region rather than just less of it.
        </p>
      )}

      {noDataForRegion && (
        <p className="timeofday-chart__status">
          Snowdonia's incident data doesn't include a start time, so there's nothing to
          show here for this region specifically.
        </p>
      )}

      {!noDataForRegion && loading && <p className="timeofday-chart__status">Loading…</p>}

      {!noDataForRegion && !loading && chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
            <XAxis
              dataKey="label"
              stroke="var(--color-slate)"
              fontSize={10}
              fontFamily="JetBrains Mono, monospace"
              tickLine={false}
              axisLine={{ stroke: "var(--color-border)" }}
              interval={1}
            />
            <YAxis hide />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(0,0,0,0.04)" }} />
            <Bar dataKey="incident_count" radius={[2, 2, 0, 0]}>
              {chartData.map((d) => (
                <Cell
                  key={d.hour}
                  fill={isLikelyDaylight(d.hour) ? "var(--color-rescue-orange)" : "var(--color-ink)"}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}