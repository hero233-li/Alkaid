export interface JobLike {
  status: string;
  errorMessage?: string | null;
}

export interface JobPollingOptions<T extends JobLike> {
  fetchJob: (signal?: AbortSignal) => Promise<T>;
  onProgress: (job: T) => void;
  terminalStatuses: ReadonlySet<string>;
  timeoutMessage: string;
  cancelledMessage: string;
  failureMessage: (job: T) => string;
  failureError?: (job: T, message: string) => Error;
  signal?: AbortSignal;
  timeoutMs?: number;
  intervalMs?: number;
}

export async function pollJobUntilTerminal<T extends JobLike>(options: JobPollingOptions<T>) {
  const deadline = Date.now() + (options.timeoutMs ?? 150_000);
  while (true) {
    if (options.signal?.aborted) throw abortError(options.cancelledMessage);
    if (Date.now() >= deadline) throw new Error(options.timeoutMessage);
    let job: T;
    try {
      job = await options.fetchJob(options.signal);
    } catch (error) {
      if (options.signal?.aborted) throw abortError(options.cancelledMessage);
      throw error;
    }
    options.onProgress(job);
    if (job.status === 'success') return job;
    if (options.terminalStatuses.has(job.status)) {
      const message = job.errorMessage || options.failureMessage(job);
      throw options.failureError?.(job, message) ?? new Error(message);
    }
    await waitForPoll(options.intervalMs ?? 500, options.signal, options.cancelledMessage);
  }
}

function abortError(message: string) {
  const error = new Error(message);
  error.name = 'AbortError';
  return error;
}

function waitForPoll(delayMs: number, signal: AbortSignal | undefined, message: string) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) return reject(abortError(message));
    const onAbort = () => {
      window.clearTimeout(timer);
      reject(abortError(message));
    };
    const timer = window.setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, delayMs);
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}
