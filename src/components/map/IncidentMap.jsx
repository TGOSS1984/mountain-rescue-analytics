import { useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import HeatmapLayer from "./HeatmapLayer.jsx";
import "leaflet/dist/leaflet.css";
import "./IncidentMap.css";

// Roughly centred on the three regions together — Britain's uplands
// span a wide area, so this is a compromise start point; the map is
// pannable/zoomable, not trying to fit all three in one perfect frame.
const DEFAULT_CENTER = [53.6, -3.0];
const DEFAULT_ZOOM = 7;

const REGION_COLORS = {
  edale: "#E8541E",
  buxton: "#E8541E",
  wasdale: "#4472A8",
  ovmro: "#2F4538",
};

export default function IncidentMap({ incidents, loading }) {
  const [viewMode, setViewMode] = useState("markers"); // "markers" | "heatmap"
  const mappable = (incidents || []).filter((i) => i.lat != null && i.lon != null);

  return (
    <div className="incident-map">
      <div className="incident-map__header">
        <p className="eyebrow incident-map__eyebrow">
          {loading ? "Loading…" : `${mappable.length} mapped incident${mappable.length === 1 ? "" : "s"}`}
        </p>
        <div className="incident-map__toggle" role="group" aria-label="Map view">
          <button
            type="button"
            className={`incident-map__toggle-btn ${viewMode === "markers" ? "is-active" : ""}`}
            onClick={() => setViewMode("markers")}
          >
            Markers
          </button>
          <button
            type="button"
            className={`incident-map__toggle-btn ${viewMode === "heatmap" ? "is-active" : ""}`}
            onClick={() => setViewMode("heatmap")}
          >
            Heatmap
          </button>
        </div>
      </div>
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={DEFAULT_ZOOM}
        scrollWheelZoom={false}
        className="incident-map__container"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {viewMode === "heatmap" && <HeatmapLayer points={mappable} />}
        {viewMode === "markers" &&
          mappable.map((incident) => (
            <CircleMarker
              key={`${incident.source_team_id}-${incident.id ?? incident.location_text}-${incident.date}`}
              center={[incident.lat, incident.lon]}
              radius={6}
              pathOptions={{
                color: REGION_COLORS[incident.source_team_id] || "#5B6670",
                fillColor: REGION_COLORS[incident.source_team_id] || "#5B6670",
                fillOpacity: 0.7,
                weight: 1.5,
              }}
            >
              <Popup>
                <strong>{incident.location_text}</strong>
                <br />
                {incident.date || "Date unknown"}
                <br />
                {incident.activity_type.replace(/_/g, " ")}
              </Popup>
            </CircleMarker>
          ))}
      </MapContainer>
    </div>
  );
}