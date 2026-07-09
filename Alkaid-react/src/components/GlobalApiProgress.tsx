import { useEffect, useState, type CSSProperties } from 'react';
import { API_PROGRESS_EVENT, type ApiProgressDetail } from '../api/progress';
import { API_RESPONSE_DELAY_MS } from '../config/runtimeConfig';

interface ProgressState extends ApiProgressDetail {
  sequence: number;
}

export default function GlobalApiProgress() {
  const [progress, setProgress] = useState<ProgressState>({
    pending: 0,
    delayMs: API_RESPONSE_DELAY_MS,
    sequence: 0,
  });

  useEffect(() => {
    const handleProgress = (event: Event) => {
      const detail = (event as CustomEvent<ApiProgressDetail>).detail;
      setProgress((current) => ({
        pending: detail.pending,
        delayMs: detail.delayMs,
        sequence: detail.pending > 0 && current.pending === 0 ? current.sequence + 1 : current.sequence,
      }));
    };

    window.addEventListener(API_PROGRESS_EVENT, handleProgress);
    return () => window.removeEventListener(API_PROGRESS_EVENT, handleProgress);
  }, []);

  if (progress.pending <= 0) {
    return null;
  }

  return (
    <div className="global-api-progress" role="status" aria-live="polite">
      <span className="global-api-progress-text">
        {progress.pending > 1 ? `正在处理 ${progress.pending} 个请求...` : '正在处理请求...'}
      </span>
      <div
        key={progress.sequence}
        className="global-api-progress-track"
        style={
          {
            '--progress-duration': `${Math.max(progress.delayMs, 600)}ms`,
          } as CSSProperties
        }
      >
        <div className="global-api-progress-bar" />
      </div>
    </div>
  );
}
