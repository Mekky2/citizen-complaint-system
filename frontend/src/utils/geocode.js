import { LANG } from '../i18n';
import { tr } from '../i18n';
// Reverse geocoding via OpenStreetMap Nominatim (public service, no key). Failure is non-fatal:
// the citizen can always type the address by hand.
export async function reverseGeocode([lat, lng]) {
  const r = await fetch(`https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${lat}&lon=${lng}&accept-language=${LANG}&zoom=18`);
  if (!r.ok) throw new Error('geocode failed');
  const d = await r.json();
  const a = d.address || {};
  return {
    street: a.road || a.pedestrian || a.suburb || a.neighbourhood || '',
    governorate: (a.state || a.governorate || '').replace('محافظة ', '').replace(/ Governorate$/i, ''),
    city: a.city || a.town || a.village || a.county || '',
    full: d.display_name || '',
  };
}

// Forward search (address / landmark -> coordinates), Egypt only. Returns [{ id, label, position }].
export async function searchPlaces(q) {
  const r = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&q=${encodeURIComponent(q)}&countrycodes=eg&accept-language=${LANG}&limit=6`);
  if (!r.ok) throw new Error('search failed');
  const d = await r.json();
  return d.map((x) => ({ id: x.place_id, label: x.display_name, position: [Number(x.lat), Number(x.lon)] }));
}
