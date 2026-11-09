
import { useEffect, useMemo, useRef, useState } from 'react';
import { Camera, ImagePlus, X, Video } from 'lucide-react';
import { cn } from '../../utils/cn';
import { tr } from '../../i18n';

export default function FileUpload({
  files,
  onChange,
  accept = 'image/*',
  multiple = true,
  label = tr("اسحب الصور أو الفيديو هنا أو اخترها من جهازك"),
  maxSizeMB = 50,
  onReject,
  camera = true
}) {
  const pick = useRef(null);
  const cam = useRef(null);
  const [over, setOver] = useState(false);

  const add = (list) => {
    const selected = Array.from(list || []);

    const ok = selected.filter((f) => {
      if (f.size > maxSizeMB * 1024 * 1024) {
        onReject?.(
          tr("{p0}: الحجم أكبر من {p1} ميجابايت", {
            p0: f.name,
            p1: maxSizeMB
          })
        );
        return false;
      }

      if (!f.type.startsWith('image/') && !f.type.startsWith('video/')) {
        onReject?.(`${f.name}: نوع الملف غير مدعوم`);
        return false;
      }

      return true;
    });

    onChange(multiple ? [...files, ...ok] : ok.slice(0, 1));
  };

  const urls = useMemo(
    () => files.map((f) =>
      f.type.startsWith('image/') || f.type.startsWith('video/')
        ? URL.createObjectURL(f)
        : null
    ),
    [files]
  );

  useEffect(() => {
    return () => urls.forEach((url) => url && URL.revokeObjectURL(url));
  }, [urls]);

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          add(e.dataTransfer.files);
        }}
        className={cn(
          'rounded-xl border-2 border-dashed p-5 text-center transition',
          over
            ? 'border-blue-400 bg-blue-500/10'
            : 'border-slate-600 bg-slate-900/40'
        )}
      >
        <ImagePlus className="mx-auto h-9 w-9 text-blue-400" aria-hidden />

        <p className="mt-2 font-semibold text-slate-100">{label}</p>

        <p className="mt-1 text-xs text-slate-400">
          الصور والفيديوهات - الحد الأقصى {maxSizeMB} MB
        </p>

        <div className="mt-3 flex flex-wrap justify-center gap-2">
          <button
            type="button"
            onClick={() => pick.current?.click()}
            className="flex items-center gap-2 rounded-lg bg-slate-700 px-4 py-2 text-sm font-bold hover:bg-slate-600"
          >
            <ImagePlus className="h-4 w-4" aria-hidden />
            {tr("اختيار ملفات")}
          </button>

          {camera && (
            <button
              type="button"
              onClick={() => cam.current?.click()}
              className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-bold hover:bg-blue-500"
            >
              <Camera className="h-4 w-4" aria-hidden />
              {tr("فتح الكاميرا")}
            </button>
          )}
        </div>

        <input
          ref={pick}
          type="file"
          hidden
          accept={accept}
          multiple={multiple}
          onChange={(e) => {
            add(e.target.files);
            e.target.value = '';
          }}
        />

        <input
          ref={cam}
          type="file"
          hidden
          accept="image/*"
          capture="environment"
          onChange={(e) => {
            add(e.target.files);
            e.target.value = '';
          }}
        />
      </div>

      {files.length > 0 && (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {files.map((f, i) => (
            <li
              key={`${f.name}-${i}`}
              className="relative aspect-square overflow-hidden rounded-xl border border-slate-600 bg-slate-900"
            >
              {urls[i] && f.type.startsWith('image/') ? (
                <img
                  src={urls[i]}
                  alt={f.name}
                  className="h-full w-full object-cover"
                />
              ) : f.type.startsWith('video/') ? (
                <div className="flex h-full flex-col items-center justify-center gap-2 p-2">
                  <Video className="h-10 w-10 text-blue-400" />
                  <video
                    src={urls[i]}
                    muted
                    preload="metadata"
                    className="max-h-20 max-w-full rounded"
                  />
                  <span className="w-full truncate text-center text-xs text-slate-300">
                    {f.name}
                  </span>
                </div>
              ) : (
                <span className="flex h-full items-center justify-center p-2 text-center text-xs text-slate-300">
                  {f.name}
                </span>
              )}

              <button
                type="button"
                aria-label={tr("إزالة {p0}", { p0: f.name })}
                onClick={() => onChange(files.filter((_, j) => j !== i))}
                className="absolute end-1.5 top-1.5 rounded-full bg-slate-950/80 p-1.5 hover:bg-red-600"
              >
                <X className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
