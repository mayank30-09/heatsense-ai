import { MapContainer, TileLayer } from "react-leaflet";

// Surat-centered view for the initial application shell.
const SURAT_CENTER: [number, number] = [21.1702, 72.8311];

export function MapShell() {
  return (
    <div className="map-frame" aria-label="HEATSENSE AI map">
      <MapContainer
        center={SURAT_CENTER}
        zoom={11}
        scrollWheelZoom
        className="leaflet-map"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
      </MapContainer>
      <div className="map-badge">Base map only · Day 1</div>
    </div>
  );
}
