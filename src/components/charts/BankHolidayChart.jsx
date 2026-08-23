import "./BankHolidayChart.css";

export default function BankHolidayChart({ data, loading }) {
  if (loading) {
    return (
      <div className="bh-chart">
        <p className="bh-chart__status">Loading…</p>
      </div>
    );
  }

  if (!data || data.bank_holiday_days_observed === 0) {
    return (
      <div className="bh-chart">
        <p className="eyebrow bh-chart__eyebrow">Bank holidays</p>
        <h2 className="bh-chart__title">Bank holidays vs. ordinary days</h2>
        <p className="bh-chart__status">No bank holiday data available.</p>
      </div>
    );
  }

  const { avg_incidents_per_bank_holiday, avg_incidents_per_ordinary_day } = data;
  const multiplier = avg_incidents_per_ordinary_day > 0
    ? avg_incidents_per_bank_holiday / avg_incidents_per_ordinary_day
    : null;
  const maxVal = Math.max(avg_incidents_per_bank_holiday, avg_incidents_per_ordinary_day, 0.01);

  return (
    <div className="bh-chart">
      <p className="eyebrow bh-chart__eyebrow">Bank holidays</p>
      <h2 className="bh-chart__title">Bank holidays vs. ordinary days</h2>
      <p className="bh-chart__note">
        Average incidents per day, not raw totals — there are only a handful of bank
        holidays a year, so comparing totals would always favour ordinary days regardless
        of whether holidays are actually busier. Based on {data.bank_holiday_days_observed}{" "}
        bank holiday{data.bank_holiday_days_observed === 1 ? "" : "s"} and{" "}
        {data.ordinary_days_observed.toLocaleString()} ordinary days in range.
      </p>

      {multiplier != null && (
        <p className="bh-chart__headline">
          {multiplier.toFixed(1)}× {multiplier >= 1 ? "busier" : "quieter"} on bank holidays
        </p>
      )}

      <div className="bh-chart__bars">
        <div className="bh-chart__bar-row">
          <span className="bh-chart__bar-label">Bank holidays</span>
          <div className="bh-chart__bar-track">
            <div
              className="bh-chart__bar-fill bh-chart__bar-fill--holiday"
              style={{ width: `${(avg_incidents_per_bank_holiday / maxVal) * 100}%` }}
            />
          </div>
          <span className="bh-chart__bar-value">{avg_incidents_per_bank_holiday}</span>
        </div>
        <div className="bh-chart__bar-row">
          <span className="bh-chart__bar-label">Ordinary days</span>
          <div className="bh-chart__bar-track">
            <div
              className="bh-chart__bar-fill bh-chart__bar-fill--ordinary"
              style={{ width: `${(avg_incidents_per_ordinary_day / maxVal) * 100}%` }}
            />
          </div>
          <span className="bh-chart__bar-value">{avg_incidents_per_ordinary_day}</span>
        </div>
      </div>
    </div>
  );
}