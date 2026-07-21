import dayjs from 'dayjs';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../../api/client';
import {
  getApplicationDataConfig,
  pollApplicationData,
  submitApplicationData,
} from './applicationData';

describe('application data API', () => {
  afterEach(() => vi.restoreAllMocks());

  it('serializes the date and submits the complete generation request', async () => {
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({
      data: { ok: true, data: { id: 1, status: 'pending', progress: 0 } },
    });

    await submitApplicationData({
      environment: '环境1',
      currentDate: dayjs('2026-07-14'),
      birthDate: '1986-07-14',
      age: 40,
      gender: '男',
      tellerNo: '3103100',
      companyType: '91',
      count: 1_000,
    });

    expect(post).toHaveBeenCalledWith(
      '/product-data/tools/application-data/generate',
      expect.objectContaining({ currentDate: '2026-07-14', count: 1_000 }),
      expect.objectContaining({ headers: expect.any(Object) }),
    );
    expect(post.mock.calls[0][1]).toHaveProperty('birthDate', '1986-07-14');
  });

  it('loads backend config and stops polling when aborted', async () => {
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue({
      data: {
        ok: true,
        data: { environments: ['环境1'], genders: ['男', '女'], companyTypes: [], maxCount: 1000 },
      },
    });
    expect((await getApplicationDataConfig()).maxCount).toBe(1000);

    const controller = new AbortController();
    controller.abort();
    await expect(
      pollApplicationData(1, vi.fn(), { signal: controller.signal }),
    ).rejects.toMatchObject({ name: 'AbortError' });
    expect(get).toHaveBeenCalledTimes(1);
  });
});
