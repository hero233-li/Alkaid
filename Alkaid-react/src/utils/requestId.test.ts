import { afterEach, describe, expect, it, vi } from 'vitest';

import { createRequestId, createWorkflowHeaders } from './requestId';

describe('requestId', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('uses randomUUID when the browser provides it', () => {
    vi.stubGlobal('crypto', { randomUUID: () => 'native-uuid' });
    expect(createRequestId()).toBe('native-uuid');
  });

  it('falls back when randomUUID is unavailable on an intranet HTTP page', () => {
    vi.stubGlobal('crypto', {
      getRandomValues: (values: Uint8Array) => {
        values.fill(10);
        return values;
      },
    });
    vi.spyOn(Date, 'now').mockReturnValue(1);

    const headers = createWorkflowHeaders();

    expect(headers['X-Idempotency-Key']).toBe('000000000001-0a0a0a0a0a0a0a0a0a0a');
    expect(headers['X-Trace-ID']).toBe('0000000000010a0a0a0a0a0a0a0a0a0a');
  });
});
