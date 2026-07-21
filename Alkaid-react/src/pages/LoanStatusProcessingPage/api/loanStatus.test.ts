import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../../api/client';
import { pollLoanJob, submitLoanAction, submitLoanSearch } from './loanStatus';

describe('loan status API', () => {
  afterEach(() => vi.restoreAllMocks());

  it('does not reuse card endpoints for loan operations', async () => {
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({
      data: { ok: true, data: { id: 1, status: 'pending', progress: 0 } },
    });
    await submitLoanSearch({ environment: '环境1', customerNo: 'C0001' });
    await submitLoanAction('LN/001', 'freeze', {
      environment: '环境1',
      customerNo: 'C0001',
      certificateNo: 'ID1',
      cardNo: 'CARD1',
      tellerNo: '310310',
      quotaNo: 'QT1',
      contractNo: 'LN/001',
    });

    expect(post.mock.calls[0][0]).toBe('/product-data/tools/loans/search');
    expect(post.mock.calls[1][0]).toBe('/product-data/tools/loans/LN%2F001/actions/freeze');
  });

  it('stops polling when the page aborts', async () => {
    const get = vi.spyOn(apiClient, 'get');
    const controller = new AbortController();
    controller.abort();
    await expect(pollLoanJob(1, vi.fn(), { signal: controller.signal })).rejects.toMatchObject({
      name: 'AbortError',
    });
    expect(get).not.toHaveBeenCalled();
  });
});
