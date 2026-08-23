/**
 * client.js
 *
 * Thin fetch wrapper around the FastAPI service. Deliberately not
 * hiding fetch behind a heavier abstraction (React Query, SWR, etc.) —
 * for a dashboard this size, plain fetch + useState/useEffect is
 * enough, and adding a data-fetching library would be reaching for a
 * tool the project hasn't actually earned yet.
 */

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function request(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API request to ${path} failed (${res.status}): ${body}`);
  }
  return res.json();
}

export function getStats() {
  return request("/stats");
}

export function getMonthlyStats(team) {
  const query = team ? `?team=${encodeURIComponent(team)}` : "";
  return request(`/stats/monthly${query}`);
}

export function getWeatherStats(team) {
  const query = team ? `?team=${encodeURIComponent(team)}` : "";
  return request(`/stats/weather${query}`);
}

export function getYearlyStats(team) {
  const query = team ? `?team=${encodeURIComponent(team)}` : "";
  return request(`/stats/yearly${query}`);
}

export function getTimeOfDayStats(team) {
  const query = team ? `?team=${encodeURIComponent(team)}` : "";
  return request(`/stats/timeofday${query}`);
}

export function getActivityBreakdown() {
  return request("/stats/activity-breakdown");
}

export function getNotableStats() {
  return request("/stats/notable");
}

export function getTopLocations({ limit = 10, team } = {}) {
  const params = new URLSearchParams();
  params.set("limit", limit);
  if (team) params.set("team", team);
  return request(`/stats/top-locations?${params.toString()}`);
}

export function getElevationStats() {
  return request("/stats/elevation");
}

export function getDaylightStats() {
  return request("/stats/daylight");
}

export function getDayOfWeekStats() {
  return request("/stats/day-of-week");
}

export function getBankHolidayStats() {
  return request("/stats/bank-holidays");
}

export function getRegions() {
  return request("/regions");
}

export function getIncidents({
  team,
  activityType,
  outcome,
  dateFrom,
  dateTo,
  geocodedOnly,
  limit = 50,
  offset = 0,
} = {}) {
  const params = new URLSearchParams();
  if (team) params.set("team", team);
  if (activityType) params.set("activity_type", activityType);
  if (outcome) params.set("outcome", outcome);
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  if (geocodedOnly) params.set("geocoded_only", "true");
  params.set("limit", limit);
  params.set("offset", offset);
  return request(`/incidents?${params.toString()}`);
}

export function getIncident(id) {
  return request(`/incidents/${id}`);
}