import { describe, expect, it } from 'vitest';
import { pollJobUntilTerminal } from './jobPolling';

describe('pollJobUntilTerminal', () => {
  it('reports an in-flight HTTP cancellation as AbortError even if the client wraps it', async () => {
    const controller = new AbortController();
    const polling = pollJobUntilTerminal({
      fetchJob: (signal) => new Promise<never>((_resolve, reject) => {
        signal?.addEventListener('abort', () => reject(new Error('请求失败')), { once: true });
      }),
      onProgress: () => undefined,
      terminalStatuses: new Set(['failed']),
      timeoutMessage: '超时',
      cancelledMessage: '已取消',
      failureMessage: () => '失败',
      signal: controller.signal,
    });
    controller.abort();
    await expect(polling).rejects.toMatchObject({ name: 'AbortError', message: '已取消' });
  });
});
