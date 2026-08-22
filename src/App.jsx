import { useEffect, useState, useCallback } from "react";
import Header from "./components/layout/Header.jsx";
import Hero from "./components/layout/Hero.jsx";
import Filters from "./components/filters/Filters.jsx";
import MonthlyChart from "./components/charts/MonthlyChart.jsx";
import IncidentMap from "./components/map/IncidentMap.jsx";
import IncidentCard from "./components/incidents/IncidentCard.jsx";
import { getStats, getMonthlyStats, getIncidents } from "./api/client.js";
import "./App.css";

const DEFAULT_FILTERS = { team: "", activityType: "", geocodedOnly: false };
const PAGE_SIZE = 20;

export default function App() {
  const [filters, setFilters] = useState(DEFAULT_FILTERS);

  const [stats, setStats] = useState(null);
  const [statsError, setStatsError] = useState(null);
  const [statsLoading, setStatsLoading] = useState(true);

  const [monthly, setMonthly] = useState([]);
  const [monthlyLoading, setMonthlyLoading] = useState(true);

  const [incidents, setIncidents] = useState([]);
  const [incidentsTotal, setIncidentsTotal] = useState(0);
  const [incidentsLoading, setIncidentsLoading] = useState(true);
  const [incidentsError, setIncidentsError] = useState(null);
  const [offset, setOffset] = useState(0);

  // /stats is independent of the active filters — it's the overall
  // dataset summary shown in the hero, not a filtered view.
  useEffect(() => {
    getStats()
      .then(setStats)
      .catch((err) => setStatsError(err.message))
      .finally(() => setStatsLoading(false));
  }, []);

  useEffect(() => {
    setMonthlyLoading(true);
    getMonthlyStats(filters.team || undefined)
      .then(setMonthly)
      .catch(() => setMonthly([]))
      .finally(() => setMonthlyLoading(false));
  }, [filters.team]);

  const loadIncidents = useCallback(
    (currentOffset) => {
      setIncidentsLoading(true);
      setIncidentsError(null);
      getIncidents({
        team: filters.team || undefined,
        activityType: filters.activityType || undefined,
        geocodedOnly: filters.geocodedOnly,
        limit: PAGE_SIZE,
        offset: currentOffset,
      })
        .then((res) => {
          setIncidents(currentOffset === 0 ? res.incidents : (prev) => [...prev, ...res.incidents]);
          setIncidentsTotal(res.total);
        })
        .catch((err) => setIncidentsError(err.message))
        .finally(() => setIncidentsLoading(false));
    },
    [filters.team, filters.activityType, filters.geocodedOnly]
  );

  // Reset to the first page whenever filters change
  useEffect(() => {
    setOffset(0);
    loadIncidents(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.team, filters.activityType, filters.geocodedOnly]);

  // For the map: pull a larger, unpaginated-feeling set of geocoded
  // incidents matching the current filters, independent of the
  // paginated card list below it.
  const [mapIncidents, setMapIncidents] = useState([]);
  const [mapLoading, setMapLoading] = useState(true);
  useEffect(() => {
    setMapLoading(true);
    getIncidents({
      team: filters.team || undefined,
      activityType: filters.activityType || undefined,
      geocodedOnly: true,
      limit: 500,
      offset: 0,
    })
      .then((res) => setMapIncidents(res.incidents))
      .catch(() => setMapIncidents([]))
      .finally(() => setMapLoading(false));
  }, [filters.team, filters.activityType]);

  function handleLoadMore() {
    const nextOffset = offset + PAGE_SIZE;
    setOffset(nextOffset);
    loadIncidents(nextOffset);
  }

  return (
    <>
      <Header />
      <main id="overview">
        <Hero stats={stats} loading={statsLoading} error={statsError} />

        <div className="container app__section">
          <Filters value={filters} onChange={setFilters} />
        </div>

        <div className="container app__section">
          <MonthlyChart data={monthly} loading={monthlyLoading} />
        </div>

        <div className="container app__section" id="regions">
          <IncidentMap incidents={mapIncidents} loading={mapLoading} />
        </div>

        <div className="container app__section app__section--last" id="incidents">
          <p className="eyebrow app__list-eyebrow">Incident log</p>
          <h2 className="app__list-title">
            {incidentsLoading && offset === 0
              ? "Loading incidents…"
              : `${incidentsTotal.toLocaleString()} incident${incidentsTotal === 1 ? "" : "s"} match${
                  incidentsTotal === 1 ? "es" : ""
                } the current filters`}
          </h2>

          {incidentsError && (
            <p className="app__error" role="alert">
              Couldn't load incidents — is the API running? ({incidentsError})
            </p>
          )}

          <div className="app__incident-grid">
            {incidents.map((incident) => (
              <IncidentCard key={incident.id} incident={incident} />
            ))}
          </div>

          {!incidentsLoading && incidents.length < incidentsTotal && (
            <button className="app__load-more" onClick={handleLoadMore}>
              Load more
            </button>
          )}
          {incidentsLoading && offset > 0 && (
            <p className="app__list-status">Loading more…</p>
          )}
        </div>
      </main>
    </>
  );
}