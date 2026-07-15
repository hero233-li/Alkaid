import { act, renderHook, waitFor } from '@testing-library/react';
import dayjs from 'dayjs';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as api from '../api/applicationData';
import type { ApplicationDataJob } from '../types';
import { useApplicationDataGenerator } from './useApplicationDataGenerator';

vi.mock('antd', () => ({ message: { success: vi.fn(), error: vi.fn() } }));
vi.mock('../api/applicationData');

const values = {
  environment: '环境1', currentDate: dayjs('2026-07-15'), age: 40,
  birthDate: '1986-07-14', gender: '男' as const, tellerNo: 'T1',
  companyType: '91' as const, count: 1,
};

describe('useApplicationDataGenerator', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getApplicationDataConfig).mockResolvedValue({
      environments: ['环境1'], genders: ['男'],
      companyTypes: [{ label: '公司', value: '91' }], maxCount: 1000,
    });
  });

  it('does not let the cancelled old flow clear the new flow activity', async () => {
    vi.mocked(api.submitApplicationData)
      .mockResolvedValueOnce({ id: 1, status: 'pending', progress: 0 })
      .mockResolvedValueOnce({ id: 2, status: 'pending', progress: 0 });
    let resolveSecond!: (job: ApplicationDataJob) => void;
    vi.mocked(api.pollApplicationData)
      .mockImplementationOnce((_id, _progress, options) => new Promise((_, reject) => {
        options?.signal?.addEventListener('abort', () => reject(new Error('wrapped cancellation')), { once: true });
      }))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveSecond = resolve; }));

    const { result } = renderHook(() => useApplicationDataGenerator());
    await waitFor(() => expect(result.current.config).not.toBeNull());

    let first!: Promise<void>;
    act(() => { first = result.current.generate(values); });
    await waitFor(() => expect(api.pollApplicationData).toHaveBeenCalledTimes(1));
    let second!: Promise<void>;
    act(() => { second = result.current.generate(values); });
    await act(async () => { await first; });

    expect(result.current.activity?.jobId).toBe(2);
    resolveSecond({ id: 2, status: 'success', progress: 100, result: { records: [] } });
    await act(async () => { await second; });
    expect(result.current.activity).toBeNull();
  });
});
