import "./DaylightChart.css";

export default function DaylightChart({ data, loading }) {
  if (loading) {
    return (
      <div className="daylight-chart">
        <p className="daylight-chart__status">Loading…</p>
      </div>
    );
  }

  if (!data || data.incidents_with_daylight_data === 0) {
    return (
      <div className="daylight-chart">
        <p className="eyebrow daylight-chart__eyebrow">Daylight</p>
        <h2 className="daylight-chart__title">Daylight vs. darkness</h2>
        <p className="daylight-chart__status">No daylight data available.</p>
      </div>
    );
  }

  const total = data.daylight_count + data.darkness_count;
  const darknessPct = total > 0 ? Math.round((data.darkness_count / total) * 100) : 0;
  const daylightPct = 100 - darknessPct;

  return (
    <div className="daylight-chart">
      <p className="eyebrow daylight-chart__eyebrow">Daylight</p>
      <h2 className="daylight-chart__title">Daylight vs. darkness</h2>
      <p className="daylight-chart__note">
        Wasdale's own incident log flags a rise in walkers becoming "benighted"
        without a head torch — this checks whether that shows up in the data itself.
        Based on {data.incidents_with_daylight_data.toLocaleString()} incidents with a
        recorded time ({data.teams_included.length === 1 ? "Peak District only" : "Peak District & Lake District"};
        Snowdonia's source doesn't record start times).
      </p>

      <div className="daylight-chart__bar" role="img" aria-label={`${daylightPct}% daylight, ${darknessPct}% darkness`}>
        <div className="daylight-chart__bar-segment daylight-chart__bar-segment--day" style={{ width: `${daylightPct}%` }} />
        <div className="daylight-chart__bar-segment daylight-chart__bar-segment--dark" style={{ width: `${darknessPct}%` }} />
      </div>

      <div className="daylight-chart__legend">
        <div className="daylight-chart__legend-item">
          <span className="daylight-chart__swatch daylight-chart__swatch--day" />
          <span>Daylight — {data.daylight_count.toLocaleString()} ({daylightPct}%)</span>
        </div>
        <div className="daylight-chart__legend-item">
          <span className="daylight-chart__swatch daylight-chart__swatch--dark" />
          <span>Darkness — {data.darkness_count.toLocaleString()} ({darknessPct}%)</span>
        </div>
      </div>
    </div>
  );
}