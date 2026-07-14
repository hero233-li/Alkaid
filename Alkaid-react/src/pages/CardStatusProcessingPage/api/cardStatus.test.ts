import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../../api/client';
import { submitCardAction, submitCardSearch } from './cardStatus';

describe('card status API', () => {
  afterEach(() => vi.restoreAllMocks());

  it('uses dedicated card search and action endpoints', async () => {
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({
      data: { ok: true, data: { id: 1, status: 'pending', progress: 0 } },
    });
    await submitCardSearch({ environment: '环境1', customerNo: 'C0001' });
    await submitCardAction('6222 01', 'deposit', {
      environment: '环境1',
      customerNo: 'C0001',
      certificateNo: 'ID1',
      cardNo: '6222 01',
      tellerNo: '310310',
      amount: 100,
    });

    expect(post.mock.calls[0][0]).toBe('/product-data/tools/cards/search');
    expect(post.mock.calls[1][0]).toBe('/product-data/tools/cards/6222%2001/actions/deposit');
  });
});
