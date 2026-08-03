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

  it('parses a browser-style multiline cURL command', () => {
    const result = parseCurl(`curl 'https://example.test/orders?page=2' \\
  --request=POST \\
  --header='accept: application/json' \\
  --header='content-type: application/json' \\
  --cookie='session=abc' \\
  --data-raw='{"name":"Alioth"}'`);

    expect(result.method).toBe('POST');
    expect(result.url).toBe('https://example.test/orders');
    expect(result.params[0]).toMatchObject({ name: 'page', value: '2' });
    expect(result.headers).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ name: 'accept', value: 'application/json' }),
        expect.objectContaining({ name: 'Cookie', value: 'session=abc' }),
      ]),
    );
    expect(result.bodyMode).toBe('json');
    expect(result.body).toBe('{"name":"Alioth"}');
  });

  it('supports an absolute curl path and HEAD requests', () => {
    const result = parseCurl('/usr/bin/curl --head --url=https://example.test/health');

    expect(result.method).toBe('HEAD');
    expect(result.url).toBe('https://example.test/health');
  });
});
