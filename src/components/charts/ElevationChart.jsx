import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import "./ElevationChart.css";

const REGION_LABELS = {
  edale: "Peak District",
  buxton: "Peak District",
  wasdale: "Lake District",
  ovmro: "Snowdonia",
};

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const count = payload[0].value;
  return (
    <div className="elevation-chart__tooltip">
      <strong>{label}</strong>
      <div>{count} incident{count === 1 ? "" : "s"}</div>
    </div>
  );
}

export default function ElevationChart({ data, loading }) {
  const bands = data?.bands || [];
  const byRegion = data?.by_region || [];

  return (
    <div className="elevation-chart">
      <p className="eyebrow elevation-chart__eyebrow">Terrain</p>
      <h2 className="elevation-chart__title">Incidents by elevation</h2>

      {loading && <p className="elevation-chart__status">Loading…</p>}
      {!loading && bands.length === 0 && (
        <p className="elevation-chart__status">No elevation data available.</p>
      )}

      {!loading && bands.length > 0 && (
        <>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={bands} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
              <XAxis
                dataKey="band_label"
                stroke="var(--color-slate)"
                fontSize={11}
                fontFamily="JetBrains Mono, monospace"
                tickLine={false}
                axisLine={{ stroke: "var(--color-border)" }}
              />
              <YAxis hide />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(0,0,0,0.04)" }} />
              <Bar dataKey="incident_count" radius={[2, 2, 0, 0]}>
                {bands.map((b) => (
                  <Cell key={b.band_label} fill="var(--color-ordnance-green)" />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          <div className="elevation-chart__region-avgs">
            {byRegion
              .filter((r) => r.average_elevation_m != null)
              .map((r) => (
                <div key={r.source_team_id} className="elevation-chart__region-stat">
                  <span className="elevation-chart__region-name">
                    {REGION_LABELS[r.source_team_id] || r.region}
                  </span>
                  <span className="elevation-chart__region-value">
                    {Math.round(r.average_elevation_m)}m avg
                  </span>
                </div>
              ))}
          </div>
        </>
      )}
    </div>
  );
}