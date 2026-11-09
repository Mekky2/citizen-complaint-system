// Landing page content that is NOT served by the API (the backend has no public endpoint for completed repairs).
// The first item is the hero image; the rest fill the gallery. Each item is ONE of:
//   { photo }          – a single photograph (no slider)
//   { before, after }  – a pair for the slider. Use ONLY two photos of the SAME place from the same angle.
// Optional: `credit: { author, license, url }` (shown under the image), `illustrative: true` (shows an "Illustration" badge).
// Captions describe only what is visible in the photo; the photos are separate cases, not one before/during/after sequence.
export const REPAIRS = [
  { id: 'paving', title: 'رصف طبقة أسفلت جديدة', photo: '/landing/paving.jpg' },
  { id: 'worn', title: 'سطح طريق متهالك', photo: '/landing/worn-road.jpg' },
  { id: 'prep', title: 'تجهيز الطريق للرصف', photo: '/landing/road-prep.jpg' },
  { id: 'new', title: 'طريق بعد الرصف والتخطيط', photo: '/landing/new-road.jpg' },
];
