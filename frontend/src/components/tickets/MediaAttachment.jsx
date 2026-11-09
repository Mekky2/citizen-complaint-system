import { useEffect, useState } from 'react';
import client, { API_URL } from '../../api/client';
import { tr } from '../../i18n';

export default function MediaAttachment({ media }) {
  const [src, setSrc] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let objectUrl;
    const controller = new AbortController();

    async function loadMedia() {
      try {
        // Resolve the protected media URL against the backend, not Vite.
        const endpoint = new URL(media.url, API_URL).toString();

        const response = await client.get(endpoint, {
          responseType: 'blob',
          signal: controller.signal,
        });

        objectUrl = URL.createObjectURL(response.data);
        setSrc(objectUrl);
      } catch (err) {
        if (!controller.signal.aborted) setError(true);
      }
    }

    loadMedia();

    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [media.url]);

  if (error) {
    return (
      <div className="flex aspect-square items-center justify-center p-3 text-center text-sm text-red-400">
        {tr("تعذر تحميل المرفق")}
      </div>
    );
  }

  if (!src) {
    return (
      <div className="flex aspect-square items-center justify-center text-sm text-slate-400">
        {tr("جارٍ تحميل المرفق...")}
      </div>
    );
  }

  if (media.type === 'image') {
    return (
      <a href={src} target="_blank" rel="noreferrer">
        <img
          src={src}
          alt={tr("مرفق البلاغ")}
          className="aspect-square w-full object-cover"
        />
      </a>
    );
  }

  if (media.type === 'video') {
    return (
      <video
        src={src}
        controls
        preload="metadata"
        className="aspect-square w-full bg-black object-contain"
      />
    );
  }

  if (media.type === 'audio') {
    return (
      <div className="flex min-h-40 items-center justify-center p-3">
        <audio src={src} controls preload="metadata" className="w-full" />
      </div>
    );
  }

  return null;
}
