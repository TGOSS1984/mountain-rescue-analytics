import { useEffect, useState, useCallback } from "react";
import Header from "./components/layout/Header.jsx";
import Hero from "./components/layout/Hero.jsx";
import Footer from "./components/layout/Footer.jsx";
import Filters from "./components/filters/Filters.jsx";
import MonthlyChart from "./components/charts/MonthlyChart.jsx";
import WeatherChart from "./components/charts/WeatherChart.jsx";
import YearlyChart from "./components/charts/YearlyChart.jsx";
import TimeOfDayChart from "./components/charts/TimeOfDayChart.jsx";
import ActivityChart from "./components/charts/ActivityChart.jsx";
import ElevationChart from "./components/charts/ElevationChart.jsx";
import DaylightChart from "./components/charts/DaylightChart.jsx";
import DayOfWeekChart from "./components/charts/DayOfWeekChart.jsx";
import BankHolidayChart from "./components/charts/BankHolidayChart.jsx";
import NotableStats from "./components/regions/NotableStats.jsx";
import TopLocations from "./components/regions/TopLocations.jsx";
import IncidentMap from "./components/map/IncidentMap.jsx";
import RegionPanel from "./components/regions/RegionPanel.jsx";
import IncidentCard from "./components/incidents/IncidentCard.jsx";
import {
  getStats, getMonthlyStats, getWeatherStats, getYearlyStats, getTimeOfDayStats,
  getActivityBreakdown, getNotableStats, getTopLocations, getElevationStats,
  getDaylightStats, getDayOfWeekStats, getBankHolidayStats, getRegions, getIncidents,
} from "./api/client.js";
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

  const [weather, setWeather] = useState(null);
  const [weatherLoading, setWeatherLoading] = useState(true);

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

  // Regions comparison is also filter-independent by design — comparing
  // "Peak District vs Lake District vs Snowdonia" stops meaning
  // anything once you've filtered down to a single region.
  const [regions, setRegions] = useState([]);
  const [regionsLoading, setRegionsLoading] = useState(true);
  useEffect(() => {
    getRegions()
      .then(setRegions)
      .catch(() => setRegions([]))
      .finally(() => setRegionsLoading(false));
  }, []);

  // Activity breakdown is filter-independent, same reasoning as
  // regions — the cross-region comparison is the whole point.
  const [activityBreakdown, setActivityBreakdown] = useState([]);
  const [activityLoading, setActivityLoading] = useState(true);
  useEffect(() => {
    getActivityBreakdown()
      .then(setActivityBreakdown)
      .catch(() => setActivityBreakdown([]))
      .finally(() => setActivityLoading(false));
  }, []);

  const [elevation, setElevation] = useState(null);
  const [elevationLoading, setElevationLoading] = useState(true);
  useEffect(() => {
    getElevationStats()
      .then(setElevation)
      .catch(() => setElevation(null))
      .finally(() => setElevationLoading(false));
  }, []);

  const [daylight, setDaylight] = useState(null);
  const [daylightLoading, setDaylightLoading] = useState(true);
  useEffect(() => {
    getDaylightStats()
      .then(setDaylight)
      .catch(() => setDaylight(null))
      .finally(() => setDaylightLoading(false));
  }, []);

  const [dayOfWeek, setDayOfWeek] = useState(null);
  const [dayOfWeekLoading, setDayOfWeekLoading] = useState(true);
  useEffect(() => {
    getDayOfWeekStats()
      .then(setDayOfWeek)
      .catch(() => setDayOfWeek(null))
      .finally(() => setDayOfWeekLoading(false));
  }, []);

  const [bankHoliday, setBankHoliday] = useState(null);
  const [bankHolidayLoading, setBankHolidayLoading] = useState(true);
  useEffect(() => {
    getBankHolidayStats()
      .then(setBankHoliday)
      .catch(() => setBankHoliday(null))
      .finally(() => setBankHolidayLoading(false));
  }, []);

  // Notable stats are inherently Snowdonia-specific (OVMRO is the only
  // source with duration/team-size data), so they don't respond to the
  // region filter — the component labels this clearly itself.
  const [notable, setNotable] = useState(null);
  const [notableLoading, setNotableLoading] = useState(true);
  useEffect(() => {
    getNotableStats()
      .then(setNotable)
      .catch(() => setNotable(null))
      .finally(() => setNotableLoading(false));
  }, []);

  // Unlike regions/activity/notable, top locations genuinely benefits
  // from the region filter — "busiest in the Peak District" is a
  // meaningful, different question from "busiest overall."
  const [topLocations, setTopLocations] = useState([]);
  const [topLocationsLoading, setTopLocationsLoading] = useState(true);
  useEffect(() => {
    setTopLocationsLoading(true);
    getTopLocations({ team: filters.team || undefined, limit: 10 })
      .then(setTopLocations)
      .catch(() => setTopLocations([]))
      .finally(() => setTopLocationsLoading(false));
  }, [filters.team]);

  useEffect(() => {
    setMonthlyLoading(true);
    getMonthlyStats(filters.team || undefined)
      .then(setMonthly)
      .catch(() => setMonthly([]))
      .finally(() => setMonthlyLoading(false));
  }, [filters.team]);

  const [yearly, setYearly] = useState([]);
  const [yearlyLoading, setYearlyLoading] = useState(true);
  useEffect(() => {
    setYearlyLoading(true);
    getYearlyStats(filters.team || undefined)
      .then(setYearly)
      .catch(() => setYearly([]))
      .finally(() => setYearlyLoading(false));
  }, [filters.team]);

  const [timeOfDay, setTimeOfDay] = useState(null);
  const [timeOfDayLoading, setTimeOfDayLoading] = useState(true);
  useEffect(() => {
    setTimeOfDayLoading(true);
    getTimeOfDayStats(filters.team || undefined)
      .then(setTimeOfDay)
      .catch(() => setTimeOfDay(null))
      .finally(() => setTimeOfDayLoading(false));
  }, [filters.team]);

  useEffect(() => {
    setWeatherLoading(true);
    getWeatherStats(filters.team || undefined)
      .then(setWeather)
      .catch(() => setWeather(null))
      .finally(() => setWeatherLoading(false));
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
          <YearlyChart data={yearly} loading={yearlyLoading} activeTeam={filters.team} />
        </div>

        <div className="container app__section app__insights-grid">
          <MonthlyChart data={monthly} loading={monthlyLoading} />
          <WeatherChart data={weather} loading={weatherLoading} />
          <TimeOfDayChart data={timeOfDay} loading={timeOfDayLoading} activeTeam={filters.team} />
        </div>

        <div className="container app__section" id="regions">
          <RegionPanel regions={regions} loading={regionsLoading} />
        </div>

        <div className="container app__section">
          <ActivityChart data={activityBreakdown} loading={activityLoading} />
        </div>

        <div className="container app__section app__insights-grid">
          <ElevationChart data={elevation} loading={elevationLoading} />
          <DaylightChart data={daylight} loading={daylightLoading} />
        </div>

        <div className="container app__section app__insights-grid">
          <DayOfWeekChart data={dayOfWeek} loading={dayOfWeekLoading} />
          <BankHolidayChart data={bankHoliday} loading={bankHolidayLoading} />
        </div>

        <div className="container app__section">
          <NotableStats data={notable} loading={notableLoading} />
        </div>

        <div className="container app__section">
          <TopLocations data={topLocations} loading={topLocationsLoading} />
        </div>

        <div className="container app__section">
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
      <Footer stats={stats} />
    </>
  );
}