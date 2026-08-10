import { describe, expect, it } from 'vitest';

import { parseResponseCookies } from './responseModel';

describe('parseResponseCookies', () => {
  it('parses cookie value and attributes from response headers', () => {
    expect(
      parseResponseCookies({
        'set-cookie': ['session=abc=123; HttpOnly; Path=/'],
      }),
    ).toEqual([
      {
        id: 'response-cookie-0',
        name: 'session',
        value: 'abc=123',
        attributes: ['HttpOnly', 'Path=/'],
      },
    ]);
  });
});
