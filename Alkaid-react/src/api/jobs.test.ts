import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from './client';
import { deleteAllJobs, getJobDetail } from './jobs';

describe('Jobs api', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('clears all completed Jobs through the collection endpoint', async () => {
    const result = { deletedJobs: 5, activeJobs: 1 };
    const remove = vi.spyOn(apiClient, 'delete').mockResolvedValue({
      data: { ok: true, message: '已结束任务记录已全部清除', data: result },
    });

    await expect(deleteAllJobs()).resolves.toEqual(result);
    expect(remove).toHaveBeenCalledWith('/jobs/');
  });

  it('requests the business-only log view for product application details', async () => {
    const detail = { id: 7, logs: [{ id: 3, message: '申请资料校验完成' }] };
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue({
      data: { ok: true, message: '', data: detail },
    });

    await expect(getJobDetail(7, { includePayload: true, logView: 'business' })).resolves.toEqual(
      detail,
    );
    expect(get).toHaveBeenCalledWith('/jobs/7', {
      params: { includePayload: true, logView: 'business' },
    });
  });
});
