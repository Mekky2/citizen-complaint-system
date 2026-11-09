import { useCallback, useEffect, useRef, useState } from 'react';
import { errorMessage } from '../utils/errors';

// Standard loading/error/data contract for every API-driven view.
// `fn` is re-run whenever `deps` change or `reload()` is called. Stale responses are discarded.
export default function useFetch(fn, deps = [], { enabled = true, pollMs = 0 } = {}) {
  const [state, setState] = useState({ data: null, loading: enabled, error: null, raw: null });
  const seq = useRef(0);

  const run = useCallback(() => {
    const id = ++seq.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    return fn()
      .then((data) => { if (id === seq.current) setState({ data, loading: false, error: null, raw: null }); })
      .catch((err) => { if (id === seq.current) setState({ data: null, loading: false, error: errorMessage(err), raw: err }); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => { if (enabled) run(); else setState({ data: null, loading: false, error: null, raw: null }); }, [run, enabled]);

  // Optional silent polling (no loading flash): keeps dashboards fresh without a websocket.
  useEffect(() => {
    if (!pollMs || !enabled) return undefined;
    const t = setInterval(() => {
      if (document.hidden) return;
      const id = ++seq.current;
      fn().then((data) => { if (id === seq.current) setState({ data, loading: false, error: null, raw: null }); }).catch(() => {});
    }, pollMs);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pollMs, enabled, run]);

  return { ...state, reload: run };
}
