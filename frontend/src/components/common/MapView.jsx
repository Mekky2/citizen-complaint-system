import { useEffect } from 'react';
import { MapContainer, TileLayer, LayersControl, Marker, Circle, ZoomControl, AttributionControl, useMap, useMapEvents } from 'react-leaflet';
import { tr } from '../../i18n';
import L from 'leaflet';
import icon from 'leaflet/dist/images/marker-icon.png';
import icon2x from 'leaflet/dist/images/marker-icon-2x.png';
import shadow from 'leaflet/dist/images/marker-shadow.png';

// Vite doesn't resolve Leaflet's default marker URLs — set them explicitly.
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({ iconUrl: icon, iconRetinaUrl: icon2x, shadowUrl: shadow });

export const CAIRO = [30.0444, 31.2357];
export const MAX_ZOOM = 19;

// Two base layers: street map (OpenStreetMap) and satellite imagery (Esri World Imagery) — satellite makes it
// much easier to put the pin on the exact pothole/pole/entrance.
function Layers({ streetLabel, satelliteLabel }) {
  const map = useMap();
  // Leaflet hard-codes the English tooltip on the layers button.
  useEffect(() => { const el = map.getContainer().querySelector('.leaflet-control-layers-toggle'); if (el) { el.title = tr("طبقات الخريطة"); el.setAttribute('aria-label', tr("طبقات الخريطة")); } }, [map]);
  return (
    <LayersControl position="topright">
      <LayersControl.BaseLayer checked name={streetLabel}>
        <TileLayer attribution="&copy; OpenStreetMap" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={MAX_ZOOM} maxNativeZoom={19} />
      </LayersControl.BaseLayer>
      <LayersControl.BaseLayer name={satelliteLabel}>
        <TileLayer attribution="Tiles &copy; Esri" url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" maxZoom={MAX_ZOOM} maxNativeZoom={19} />
      </LayersControl.BaseLayer>
    </LayersControl>
  );
}

// Centres on the pin; when a GPS accuracy radius is known, frames the whole circle (never wider than zoom 15).
function Recenter({ position, accuracy, fly }) {
  const map = useMap();
  useEffect(() => {
    if (!position) return;
    if (accuracy && accuracy > 8) {
      const b = L.latLng(position).toBounds(accuracy * 2.6);
      map.fitBounds(b, { maxZoom: MAX_ZOOM - 1, animate: !!fly });
      if (map.getZoom() < 15) map.setView(position, 15);
    } else if (fly) map.flyTo(position, Math.max(map.getZoom(), 18), { duration: 0.6 });
    else map.setView(position, Math.max(map.getZoom(), 17));
  }, [position, accuracy, map, fly]);
  return null;
}

function ClickToPick({ onPick }) {
  useMapEvents({ click: (e) => onPick([e.latlng.lat, e.latlng.lng]) });
  return null;
}

// Read-only when `onPick` is omitted. With `onPick` the pin is draggable and the map is clickable.
// `accuracy` (metres) draws the GPS uncertainty circle. `markers`: [{ id, position, onClick? }] for multi-point views.
export default function MapView({ position, onPick, markers, height = 260, zoom = 17, accuracy, labels = {} }) {
  const center = position ?? markers?.[0]?.position ?? CAIRO;
  return (
    <div className="overflow-hidden rounded-xl border border-slate-600" style={{ height }} dir="ltr">
      <MapContainer center={center} zoom={position || markers?.length ? zoom : 10} maxZoom={MAX_ZOOM} className="h-full w-full" scrollWheelZoom={!!onPick} zoomControl={false} attributionControl={false}>
        <ZoomControl position="topleft" zoomInTitle={tr("تكبير")} zoomOutTitle={tr("تصغير")} />
        <AttributionControl prefix="Leaflet" />
        <Layers streetLabel={labels.street ?? tr("شارع")} satelliteLabel={labels.satellite ?? tr("قمر صناعي")} />
        {onPick && <ClickToPick onPick={onPick} />}
        {position && accuracy > 0 && <Circle center={position} radius={accuracy} pathOptions={{ color: '#3b82f6', weight: 1.5, fillColor: '#3b82f6', fillOpacity: 0.12 }} />}
        {position && (
          <Marker position={position} alt={tr("موقع البلاغ")} draggable={!!onPick}
            eventHandlers={onPick ? { dragend: (e) => { const ll = e.target.getLatLng(); onPick([ll.lat, ll.lng]); } } : undefined} />
        )}
        {position && <Recenter position={position} accuracy={accuracy} fly={!!onPick} />}
        {markers?.map((m) => (
          <Marker key={m.id} position={m.position} alt={tr("موقع البلاغ")} eventHandlers={m.onClick ? { click: m.onClick } : undefined} />
        ))}
      </MapContainer>
    </div>
  );
}
