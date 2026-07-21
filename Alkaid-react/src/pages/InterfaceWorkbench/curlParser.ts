import type { WorkbenchBodyMode } from '../../types';
import {
  createDefaultHeaders,
  createFormRow,
  createKeyValueRow,
  isJsonText,
  splitUrlAndParams,
  type FormRow,
  type KeyValueRow,
} from './requestModel';

export interface CurlPayload {
  method: string;
  url: string;
  params: KeyValueRow[];
  headers: KeyValueRow[];
  bodyMode: WorkbenchBodyMode;
  body: string;
  formRows: FormRow[];
}

function tokenizeCurl(input: string) {
  const tokens: string[] = [];
  let current = '';
  let quote: '"' | "'" | null = null;
  let escaping = false;
  for (const char of input.replace(/\r?\n\s*\\/g, ' ').trim()) {
    if (escaping) {
      current += char;
      escaping = false;
    } else if (char === '\\') {
      escaping = true;
    } else if (quote) {
      if (char === quote) quote = null;
      else current += char;
    } else if (char === '"' || char === "'") {
      quote = char;
    } else if (/\s/.test(char)) {
      if (current) {
        tokens.push(current);
        current = '';
      }
    } else {
      current += char;
    }
  }
  if (current) tokens.push(current);
  return tokens;
}

function parseHeaderLine(value: string) {
  const index = value.indexOf(':');
  if (index < 0) return null;
  return createKeyValueRow('header', value.slice(0, index).trim(), value.slice(index + 1).trim());
}

function parseFormPart(value: string) {
  const pair = value.split(';')[0];
  const index = pair.indexOf('=');
  if (index < 0) return null;
  const name = pair.slice(0, index).trim();
  const rawValue = pair.slice(index + 1);
  if (!name) return null;
  return rawValue.startsWith('@')
    ? createFormRow('file', name, rawValue)
    : createFormRow('text', name, rawValue);
}

function inferBodyMode(headers: KeyValueRow[], body: string, formRows: FormRow[]) {
  if (formRows.length > 0) return 'form-data' as const;
  const contentType =
    headers.find((row) => row.name.toLowerCase() === 'content-type')?.value.toLowerCase() || '';
  if (!body) return 'none' as const;
  if (contentType.includes('application/x-www-form-urlencoded')) return 'form-urlencoded' as const;
  if (contentType.includes('multipart/form-data')) return 'form-data' as const;
  if (contentType.includes('application/json') || isJsonText(body)) return 'json' as const;
  return 'raw' as const;
}

export function parseCurl(input: string): CurlPayload {
  const tokens = tokenizeCurl(input);
  if (tokens[0]?.toLowerCase() === 'curl') tokens.shift();

  let method = '';
  let rawUrl = '';
  const headers: KeyValueRow[] = [];
  const dataParts: string[] = [];
  const formRows: FormRow[] = [];

  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    const next = () => tokens[++index] || '';
    if (token === '-X' || token === '--request') {
      method = next().toUpperCase();
    } else if (token.startsWith('-X') && token.length > 2) {
      method = token.slice(2).toUpperCase();
    } else if (token === '-H' || token === '--header') {
      const header = parseHeaderLine(next());
      if (header) headers.push(header);
    } else if (token.startsWith('-H') && token.length > 2) {
      const header = parseHeaderLine(token.slice(2));
      if (header) headers.push(header);
    } else if (
      ['-d', '--data', '--data-raw', '--data-binary', '--data-urlencode'].includes(token)
    ) {
      dataParts.push(next());
    } else if (token === '-F' || token === '--form' || token === '--form-string') {
      const row = parseFormPart(next());
      if (row) formRows.push(row);
    } else if (token === '-b' || token === '--cookie') {
      const cookie = next();
      if (cookie) headers.push(createKeyValueRow('header', 'Cookie', cookie));
    } else if (token === '--url') {
      rawUrl = next();
    } else if (!token.startsWith('-') && !rawUrl) {
      rawUrl = token;
    }
  }

  if (!rawUrl) throw new Error('没有从 cURL 中解析到 URL');
  const body = dataParts.join('&');
  const bodyMode = inferBodyMode(headers, body, formRows);
  const urlEncodedRows: FormRow[] = [];
  if (bodyMode === 'form-urlencoded') {
    new URLSearchParams(body).forEach((value, name) =>
      urlEncodedRows.push(createFormRow('text', name, value)),
    );
  }
  const splitUrl = splitUrlAndParams(rawUrl);
  return {
    method: method || (body || formRows.length ? 'POST' : 'GET'),
    url: splitUrl.url,
    params: splitUrl.params,
    headers: headers.length ? headers : createDefaultHeaders(),
    bodyMode,
    body,
    formRows: formRows.length ? formRows : urlEncodedRows,
  };
}
