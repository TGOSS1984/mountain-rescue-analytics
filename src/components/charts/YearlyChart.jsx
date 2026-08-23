import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import "./YearlyChart.css";

const TEAM_LABELS = {
  edale: "Peak District",
  buxton: "Peak District",
  wasdale: "Lake District",
  ovmro: "Snowdonia",
};

/**
 * Years where teams_reporting is a subset of the fullest coverage seen
 * anywhere in the series get marked as "partial coverage" — a plain
 * combined line would otherwise show what looks like a real surge in
 * incidents in the most recent year, when it's actually just Wasdale
 * and OVMRO's scrapers only having current-year data (their sites
 * don't publish a full history the way Edale's REST API does). See
 * api/main.py's yearly_stats endpoint for the full reasoning.
 */
function annotateCoverage(data) {
  if (!data || data.length === 0) return { rows: [], partialYears: [] };

  const maxTeamCount = Math.max(...data.map((d) => d.teams_reporting.length));
  const rows = data.map((d) => ({
    ...d,
    fullCoverage: d.teams_reporting.length >= maxTeamCount,
  }));
  const partialYears = rows.filter((r) => !r.fullCoverage);

  return { rows, partialYears };
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const teams = d.teams_reporting.map((t) => TEAM_LABELS[t] || t);
  return (
    <div className="yearly-chart__tooltip">
      <strong>{label}</strong>
      <div>{d.incident_count} incident{d.incident_count === 1 ? "" : "s"}</div>
      <div className="yearly-chart__tooltip-meta">
        Reporting: {teams.join(", ")}
        {!d.fullCoverage && " (partial coverage)"}
      </div>
    </div>
  );
}

export default function YearlyChart({ data, loading, activeTeam }) {
  const { rows, partialYears } = annotateCoverage(data);

  return (
    <div className="yearly-chart">
      <p className="eyebrow yearly-chart__eyebrow">Long-term trend</p>
      <h2 className="yearly-chart__title">Incidents by year</h2>

      {!activeTeam && partialYears.length > 0 && (
        <p className="yearly-chart__note">
          Some regions' scrapers only pulled current-year data — years marked with a
          hollow point had fewer teams reporting, so the apparent rise isn't necessarily
          a real increase. Filter to a single region above for a cleaner long-term
          trend (Peak District has the deepest history).
        </p>
      )}

      {loading && <p className="yearly-chart__status">Loading…</p>}
      {!loading && rows.length === 0 && (
        <p className="yearly-chart__status">No dated incidents match the current filters.</p>
      )}

      {!loading && rows.length > 0 && (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <XAxis
              dataKey="year"
              stroke="var(--color-slate)"
              fontSize={11}
              fontFamily="JetBrains Mono, monospace"
              tickLine={false}
              axisLine={{ stroke: "var(--color-border)" }}
            />
            <YAxis hide />
            <Tooltip content={<CustomTooltip />} />
            <Line
              type="monotone"
              dataKey="incident_count"
              stroke="var(--color-rescue-orange)"
              strokeWidth={2}
              dot={(props) => {
                const { cx, cy, payload, index } = props;
                return (
                  <circle
                    key={`dot-${payload.year}-${index}`}
                    cx={cx}
                    cy={cy}
                    r={4}
                    fill={payload.fullCoverage ? "var(--color-rescue-orange)" : "#fff"}
                    stroke="var(--color-rescue-orange)"
                    strokeWidth={2}
                  />
                );
              }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}