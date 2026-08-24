import "./Filters.css";

const TEAM_OPTIONS = [
  { value: "", label: "All regions" },
  { value: "edale", label: "Peak District (Edale)" },
  { value: "wasdale", label: "Lake District (Wasdale)" },
  { value: "ovmro", label: "Snowdonia (OVMRO)" },
  { value: "uwfra", label: "Yorkshire Dales (UWFRA)" },
];

const ACTIVITY_OPTIONS = [
  { value: "", label: "All activities" },
  { value: "walking", label: "Walking" },
  { value: "climbing", label: "Climbing" },
  { value: "cycling", label: "Cycling" },
  { value: "running", label: "Running" },
  { value: "water", label: "Water" },
  { value: "search_missing_person", label: "Search — missing person" },
  { value: "animal_rescue", label: "Animal rescue" },
  { value: "unspecified", label: "Unspecified" },
];

export default function Filters({ value, onChange }) {
  function update(field, fieldValue) {
    onChange({ ...value, [field]: fieldValue });
  }

  return (
    <div className="filters" role="group" aria-label="Filter incidents">
      <label className="filters__field">
        <span className="filters__label">Region</span>
        <select
          value={value.team}
          onChange={(e) => update("team", e.target.value)}
        >
          {TEAM_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>

      <label className="filters__field">
        <span className="filters__label">Activity</span>
        <select
          value={value.activityType}
          onChange={(e) => update("activityType", e.target.value)}
        >
          {ACTIVITY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>

      <label className="filters__field filters__field--checkbox">
        <input
          type="checkbox"
          checked={value.geocodedOnly}
          onChange={(e) => update("geocodedOnly", e.target.checked)}
        />
        <span className="filters__label">Mapped locations only</span>
      </label>
    </div>
  );
}