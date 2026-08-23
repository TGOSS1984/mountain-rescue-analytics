import "./TopLocations.css";

const REGION_ABBREV = {
  "Peak District": "Peak District",
  "Lake District": "Lake District",
  "Snowdonia (Eryri)": "Snowdonia",
};

export default function TopLocations({ data, loading }) {
  const rows = data || [];
  const maxCount = rows.length > 0 ? Math.max(...rows.map((r) => r.incident_count)) : 1;

  return (
    <div className="top-locations">
      <p className="eyebrow top-locations__eyebrow">Busiest locations</p>
      <h2 className="top-locations__title">Most frequently reported locations</h2>
      <p className="top-locations__note">
        Raw name frequency, not merged across near-duplicate spellings — "Kinder Scout"
        and "Kinder" are the same hill but count separately here.
      </p>

      {loading && <p className="top-locations__status">Loading…</p>}
      {!loading && rows.length === 0 && (
        <p className="top-locations__status">No location data available.</p>
      )}

      {!loading && rows.length > 0 && (
        <ol className="top-locations__list">
          {rows.map((r, i) => (
            <li key={`${r.source_team_id}-${r.location_text}`} className="top-location">
              <span className="top-location__rank">{i + 1}</span>
              <div className="top-location__main">
                <div className="top-location__header">
                  <span className="top-location__name">{r.location_text}</span>
                  <span className="top-location__count">{r.incident_count}</span>
                </div>
                <div className="top-location__bar-track">
                  <div
                    className="top-location__bar-fill"
                    style={{ width: `${(r.incident_count / maxCount) * 100}%` }}
                  />
                </div>
                <span className="top-location__region">
                  {REGION_ABBREV[r.region] || r.region}
                </span>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}