export interface ResponseCookieItem {
  id: string;
  name: string;
  value: string;
  attributes: string[];
}

export function parseResponseCookies(headers: Record<string, string[]> = {}): ResponseCookieItem[] {
  const values = Object.entries(headers)
    .filter(([name]) => ['set-cookie', 'set-cookie2'].includes(name.toLowerCase()))
    .flatMap(([, items]) => items || []);
  return values.map((cookie, index) => {
    const parts = cookie
      .split(';')
      .map((part) => part.trim())
      .filter(Boolean);
    const nameValue = parts.shift() || '';
    const separator = nameValue.indexOf('=');
    return {
      id: `response-cookie-${index}`,
      name: separator >= 0 ? nameValue.slice(0, separator).trim() : nameValue,
      value: separator >= 0 ? nameValue.slice(separator + 1).trim() : '',
      attributes: parts,
    };
  });
}
