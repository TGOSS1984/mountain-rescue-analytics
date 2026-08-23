import "./RegionPanel.css";

const ACTIVITY_LABELS = {
  walking: "Walking",
  climbing: "Climbing",
  cycling: "Cycling",
  running: "Running",
  water: "Water",
  search_missing_person: "Search — missing person",
  unspecified: "Unspecified",
};

/**
 * outcome_data_source is shown as a plain disclosure line, not folded
 * into a number — Wasdale's severity data is real (team-stated),
 * Edale/OVMRO's is my own keyword guess. Presenting those as
 * comparable percentages would misrepresent genuinely uneven data
 * quality as if it were consistent. See api/main.py and
 * docs/data-dictionary.md for the reasoning.
 */
function outcomeDataNote(source) {
  if (source === "stated_by_team") return "Severity: reported directly by the team";
  if (source === "inferred_from_keywords") return "Severity: estimated from incident text";
  return "Severity: mixed data quality";
}

export default function RegionPanel({ regions, loading }) {
  return (
    <div className="region-panel">
      <p className="eyebrow region-panel__eyebrow">Region comparison</p>
      <h2 className="region-panel__title">Peak District · Lake District · Snowdonia</h2>

      {loading && <p className="region-panel__status">Loading…</p>}

      {!loading && (
        <div className="region-panel__grid">
          {regions.map((r) => (
            <article key={r.source_team_id} className="region-card">
              <h3 className="region-card__name">{r.region}</h3>

              <dl className="region-card__stats">
                <div className="region-card__stat">
                  <dt>Incidents</dt>
                  <dd>{r.incident_count.toLocaleString()}</dd>
                </div>
                <div className="region-card__stat">
                  <dt>Mapped</dt>
                  <dd>{Math.round(r.geocode_match_rate * 100)}%</dd>
                </div>
                <div className="region-card__stat">
                  <dt>Most common</dt>
                  <dd>{ACTIVITY_LABELS[r.top_activity_type] || r.top_activity_type || "—"}</dd>
                </div>
              </dl>

              <p className="region-card__note">{outcomeDataNote(r.outcome_data_source)}</p>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}