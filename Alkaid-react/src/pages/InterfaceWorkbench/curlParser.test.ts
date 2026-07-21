import { describe, expect, it } from 'vitest';

import { parseCurl } from './curlParser';

describe('parseCurl', () => {
  it('parses method, query, headers, and JSON body', () => {
    const result = parseCurl(
      `curl -X POST 'https://example.test/orders?page=2' -H 'Content-Type: application/json' -d '{"name":"Alioth"}'`,
    );

    expect(result.method).toBe('POST');
    expect(result.url).toBe('https://example.test/orders');
    expect(result.params[0]).toMatchObject({ name: 'page', value: '2' });
    expect(result.bodyMode).toBe('json');
    expect(result.body).toBe('{"name":"Alioth"}');
  });
});
