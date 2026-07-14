import dayjs from 'dayjs';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../../api/client';
import { submitApplicationData } from './applicationData';

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
      count: 100_000,
    });

    expect(post).toHaveBeenCalledWith(
      '/product-data/tools/application-data/generate',
      expect.objectContaining({ currentDate: '2026-07-14', count: 100_000 }),
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });
});
