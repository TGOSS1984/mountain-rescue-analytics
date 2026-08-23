import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";
import "./ActivityChart.css";

const ACTIVITY_LABELS = {
  walking: "Walking",
  climbing: "Climbing",
  cycling: "Cycling",
  running: "Running",
  water: "Water",
  search_missing_person: "Search",
  unspecified: "Unspecified",
};

const ACTIVITY_COLORS = {
  walking: "var(--color-chart-6)",
  climbing: "var(--color-chart-1)",
  cycling: "var(--color-chart-4)",
  running: "var(--color-chart-3)",
  water: "var(--color-chart-7)",
  search_missing_person: "var(--color-chart-2)",
  unspecified: "var(--color-chart-5)",
};

/**
 * Pivots the API's tidy (region, activity_type, count) rows into the
 * wide shape a stacked bar chart needs: one object per region with
 * one key per activity type. Done client-side rather than server-side
 * so the API can stay in the more normal tidy REST shape without
 * baking in an assumption about which activity types exist.
 */
function pivotToWide(rows) {
  const byRegion = {};
  const activityKeys = new Set();

  for (const row of rows || []) {
    if (!byRegion[row.region]) {
      byRegion[row.region] = { region: row.region, source_team_id: row.source_team_id };
    }
    byRegion[row.region][row.activity_type] = row.incident_count;
    activityKeys.add(row.activity_type);
  }

  return {
    data: Object.values(byRegion),
    activityKeys: [...activityKeys].sort(
      (a, b) => Object.keys(ACTIVITY_LABELS).indexOf(a) - Object.keys(ACTIVITY_LABELS).indexOf(b)
    ),
  };
}

export default function ActivityChart({ data, loading }) {
  const { data: chartData, activityKeys } = pivotToWide(data);

  return (
    <div className="activity-chart">
      <p className="eyebrow activity-chart__eyebrow">Activity mix</p>
      <h2 className="activity-chart__title">What people were doing, by region</h2>

      {loading && <p className="activity-chart__status">Loading…</p>}
      {!loading && chartData.length === 0 && (
        <p className="activity-chart__status">No activity data available.</p>
      )}

      {!loading && chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={chartData} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
            <XAxis
              dataKey="region"
              stroke="var(--color-slate)"
              fontSize={11}
              fontFamily="JetBrains Mono, monospace"
              tickLine={false}
              axisLine={{ stroke: "var(--color-border)" }}
            />
            <YAxis hide />
            <Tooltip
              contentStyle={{
                background: "var(--color-ink)",
                border: "none",
                borderRadius: "4px",
                fontFamily: "Inter, sans-serif",
                fontSize: "13px",
              }}
              labelStyle={{ color: "var(--color-mist-soft)" }}
              itemStyle={{ color: "var(--color-mist-soft)" }}
              formatter={(value, name) => [value, ACTIVITY_LABELS[name] || name]}
            />
            <Legend
              formatter={(value) => ACTIVITY_LABELS[value] || value}
              wrapperStyle={{ fontFamily: "Inter, sans-serif", fontSize: "12px" }}
            />
            {activityKeys.map((key) => (
              <Bar
                key={key}
                dataKey={key}
                stackId="activities"
                fill={ACTIVITY_COLORS[key] || "var(--color-slate)"}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}