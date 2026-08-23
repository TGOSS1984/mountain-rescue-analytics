import "./NotableStats.css";

function formatDuration(minutes) {
  if (minutes == null) return "—";
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}

export default function NotableStats({ data, loading }) {
  if (loading) {
    return (
      <div className="notable-stats">
        <p className="notable-stats__status">Loading…</p>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="notable-stats">
      <p className="eyebrow notable-stats__eyebrow">Notable operations</p>
      <h2 className="notable-stats__title">Snowdonia, by the numbers</h2>
      <p className="notable-stats__note">
        OVMRO is currently the only team in this dataset whose incident log records
        operation duration and team size, so these figures are specific to Snowdonia,
        not the whole dataset — based on {data.based_on_incident_count.toLocaleString()}{" "}
        operations with duration data.
      </p>

      <div className="notable-stats__grid">
        {data.longest_operation && (
          <div className="notable-stat">
            <p className="notable-stat__value">{formatDuration(data.longest_operation.value)}</p>
            <p className="notable-stat__label">Longest single operation</p>
            <p className="notable-stat__detail">
              {data.longest_operation.location_text}
              {data.longest_operation.date && ` · ${data.longest_operation.date}`}
            </p>
          </div>
        )}

        {data.largest_deployment && (
          <div className="notable-stat">
            <p className="notable-stat__value">
              {Math.round(data.largest_deployment.value)}{" "}
              <span className="notable-stat__unit">people</span>
            </p>
            <p className="notable-stat__label">Largest team deployment</p>
            <p className="notable-stat__detail">
              {data.largest_deployment.location_text}
              {data.largest_deployment.date && ` · ${data.largest_deployment.date}`}
            </p>
          </div>
        )}

        <div className="notable-stat">
          <p className="notable-stat__value">
            {data.total_operation_hours.toLocaleString()}{" "}
            <span className="notable-stat__unit">hours</span>
          </p>
          <p className="notable-stat__label">Total recorded operation time</p>
          {data.average_team_size && (
            <p className="notable-stat__detail">
              Average {data.average_team_size} team members per operation
            </p>
          )}
        </div>
      </div>
    </div>
  );
}