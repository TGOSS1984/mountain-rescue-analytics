import "./IncidentCard.css";

const REGION_LABELS = {
  edale: "Peak District",
  buxton: "Peak District",
  wasdale: "Lake District",
  ovmro: "Snowdonia",
};

// Rough severity read for the badge colour — Wasdale's stated outcome
// maps directly; everything else falls back to a neutral badge, since
// the keyword-inferred outcome isn't reliable enough to colour-code
// with the same confidence. See docs/data-dictionary.md.
function severityClass(outcome) {
  if (outcome === "Full Callout" || outcome === "fatality") return "is-high";
  if (outcome === "Limited Callout") return "is-medium";
  if (outcome === "Alert") return "is-low";
  return "is-neutral";
}

export default function IncidentCard({ incident }) {
  return (
    <article className="incident-card">
      <div className="incident-card__top">
        <h3 className="incident-card__title">{incident.location_text}</h3>
        <span className={`incident-card__badge ${severityClass(incident.outcome)}`}>
          {incident.outcome === "unrecorded" ? "Unrecorded" : incident.outcome}
        </span>
      </div>
      {incident.narrative_raw && (
        <p className="incident-card__narrative">
          {incident.narrative_raw.length > 220
            ? `${incident.narrative_raw.slice(0, 220)}…`
            : incident.narrative_raw}
        </p>
      )}
      <div className="incident-card__meta">
        <span>{incident.date || "Date unknown"}</span>
        <span>·</span>
        <span>{REGION_LABELS[incident.source_team_id] || incident.source_team_id}</span>
        <span>·</span>
        <span>{incident.activity_type.replace(/_/g, " ")}</span>
        {incident.geocode_status !== "matched" && (
          <>
            <span>·</span>
            <span className="incident-card__unmapped">not mapped</span>
          </>
        )}
      </div>
    </article>
  );
}