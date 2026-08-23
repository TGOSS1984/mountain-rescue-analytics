import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import "./WeatherChart.css";

const WEATHER_ORDER = ["clear", "cloudy", "rain", "snow", "storm", "other"];

const WEATHER_LABELS = {
  clear: "Clear",
  cloudy: "Cloudy",
  rain: "Rain",
  snow: "Snow",
  storm: "Storm",
  other: "Other",
};

const WEATHER_COLORS = {
  clear: "var(--color-chart-3)",
  cloudy: "var(--color-chart-6)",
  rain: "var(--color-chart-4)",
  snow: "var(--color-chart-7)",
  storm: "var(--color-chart-1)",
  other: "var(--color-chart-2)",
};

/**
 * Deliberately charts incidents PER DAY of each weather type, not raw
 * incident counts — a single dramatic storm day with 5 callouts would
 * otherwise make storms look far more dangerous than a single storm
 * really is. Dividing by the distinct-day count (from /stats/weather)
 * is what makes this an honest comparison rather than one that quietly
 * oversells the correlation. See api/main.py's weather_stats endpoint
 * for the reasoning in full.
 */
function computeRatios(data) {
  if (!data) return [];
  const dayMap = Object.fromEntries(
    data.days_by_weather.map((d) => [d.weather_summary, d.incident_count])
  );
  return data.incidents_by_weather
    .map((w) => {
      const days = dayMap[w.weather_summary] || 0;
      return {
        condition: w.weather_summary,
        label: WEATHER_LABELS[w.weather_summary] || w.weather_summary,
        incidentsPerDay: days > 0 ? +(w.incident_count / days).toFixed(2) : 0,
        totalIncidents: w.incident_count,
        totalDays: days,
      };
    })
    .sort(
      (a, b) => WEATHER_ORDER.indexOf(a.condition) - WEATHER_ORDER.indexOf(b.condition)
    );
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="weather-chart__tooltip">
      <strong>{d.label}</strong>
      <div>{d.incidentsPerDay} incidents per day of this weather, on average</div>
      <div className="weather-chart__tooltip-meta">
        {d.totalIncidents} incident{d.totalIncidents === 1 ? "" : "s"} across{" "}
        {d.totalDays} day{d.totalDays === 1 ? "" : "s"}
      </div>
    </div>
  );
}

export default function WeatherChart({ data, loading }) {
  const chartData = computeRatios(data);

  return (
    <div className="weather-chart">
      <p className="eyebrow weather-chart__eyebrow">Weather correlation</p>
      <h2 className="weather-chart__title">Average incidents per day, by weather</h2>
      <p className="weather-chart__note">
        Not raw incident counts — this shows how busy a typical day of each
        condition is, so one dramatic storm day with several callouts doesn't
        make storms look worse than they usually are.
      </p>

      {loading && <p className="weather-chart__status">Loading…</p>}
      {!loading && chartData.length === 0 && (
        <p className="weather-chart__status">
          No weather-matched incidents for the current filters.
        </p>
      )}

      {!loading && chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={chartData} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
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
            <Bar dataKey="incidentsPerDay" radius={[2, 2, 0, 0]}>
              {chartData.map((d) => (
                <Cell
                  key={d.condition}
                  fill={WEATHER_COLORS[d.condition] || WEATHER_COLORS.other}
                  stroke="var(--color-border)"
                  strokeWidth={1}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}