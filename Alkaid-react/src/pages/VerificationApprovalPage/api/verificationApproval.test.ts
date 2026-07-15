import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../../api/client';
import { pollVerificationJob } from './verificationApproval';

vi.mock('../../../api/client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
}));

const response = (status: string, errorMessage?: string) => ({
  data: {
    ok: true,
    data: { id: 7, status, stage: status, progress: 100, result: {}, errorMessage },
  },
});

describe('verification job polling', () => {
  afterEach(() => vi.useRealTimers());

  it('returns immediately on success', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(response('success'));
    await expect(pollVerificationJob(7, vi.fn())).resolves.toMatchObject({ status: 'success' });
  });

  it('stops and exposes the backend message on failure', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(response('failed', '外系统失败'));
    await expect(pollVerificationJob(7, vi.fn())).rejects.toThrow('外系统失败');
  });

  it('honours timeout and AbortSignal', async () => {
    await expect(pollVerificationJob(7, vi.fn(), { timeoutMs: -1 })).rejects.toThrow('轮询超时');

    const controller = new AbortController();
    controller.abort();
    await expect(pollVerificationJob(7, vi.fn(), { signal: controller.signal })).rejects.toMatchObject({
      name: 'AbortError',
    });
  });
});
