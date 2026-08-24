import { useEffect } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet.heat";

/**
 * leaflet.heat isn't a React component — it's an imperative Leaflet
 * plugin that adds a canvas layer directly to a map instance. This
 * wraps it as a small effect-driven component so it can sit inside
 * <MapContainer> like any other react-leaflet layer, using useMap() to
 * get the underlying Leaflet map and manage the heat layer's lifecycle
 * (added on mount/data change, removed on unmount) the same way
 * react-leaflet's own layers do internally.
 */
export default function HeatmapLayer({ points }) {
  const map = useMap();

  useEffect(() => {
    if (!points || points.length === 0) return undefined;

    // [lat, lon, intensity] — intensity left at a flat 0.5 rather than
    // varying it per point, since we don't have a meaningful per-point
    // weight (severity data is too inconsistent across sources to use
    // safely here — see docs/data-dictionary.md on outcome_source).
    const heatPoints = points.map((p) => [p.lat, p.lon, 0.5]);

    const heatLayer = L.heatLayer(heatPoints, {
      radius: 22,
      blur: 18,
      maxZoom: 12,
      gradient: {
        0.2: "#4472A8",
        0.4: "#2F4538",
        0.6: "#F2C14E",
        0.8: "#E8541E",
        1.0: "#C24313",
      },
    });

    heatLayer.addTo(map);
    return () => {
      map.removeLayer(heatLayer);
    };
  }, [map, points]);

  return null;
}