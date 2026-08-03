import type { WorkbenchFilePart } from '../../api/workbench';
import type {
  WorkbenchBodyMode,
  WorkbenchFormFieldPayload,
  WorkbenchFormFieldType,
} from '../../types';

const RESTRICTED_HEADER_NAMES = new Set([
  'connection',
  'content-length',
  'expect',
  'host',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
]);

export interface KeyValueRow {
  id: string;
  enabled: boolean;
  name: string;
  value: string;
}

export interface FormRow {
  id: string;
  enabled: boolean;
  type: WorkbenchFormFieldType;
  name: string;
  value: string;
  filePartName: string;
  file: File | null;
}

let rowId = 0;

function nextId(prefix: string) {
  rowId += 1;
  return `${prefix}-${Date.now()}-${rowId}`;
}

export function createKeyValueRow(
  prefix: string,
  name = '',
  value = '',
  enabled = true,
): KeyValueRow {
  return { id: nextId(prefix), enabled, name, value };
}

export function createFormRow(
  type: WorkbenchFormFieldType = 'text',
  name = '',
  value = '',
  enabled = true,
): FormRow {
  const id = nextId('field');
  return {
    id,
    enabled,
    type,
    name,
    value,
    filePartName: `file-${id}`,
    file: null,
  };
}

export function createDefaultHeaders() {
  return [
    createKeyValueRow('header', 'Accept', 'application/json'),
    createKeyValueRow('header', 'Content-Type', 'application/json'),
  ];
}

export function createDefaultFormRows() {
  return [createFormRow()];
}

export function recordToRows(prefix: string, record: Record<string, string> = {}) {
  const rows = Object.entries(record).map(([name, value]) =>
    createKeyValueRow(prefix, name, value),
  );
  return rows.length ? rows : [createKeyValueRow(prefix)];
}

function findHeaderKey(headers: Record<string, string>, name: string) {
  return Object.keys(headers).find((key) => key.toLowerCase() === name.toLowerCase());
}

function setHeader(headers: Record<string, string>, name: string, value: string) {
  const existingKey = findHeaderKey(headers, name);
  headers[existingKey || name] = value;
}

function removeHeader(headers: Record<string, string>, name: string) {
  const existingKey = findHeaderKey(headers, name);
  if (existingKey) delete headers[existingKey];
}

export function buildHeaders(
  rows: KeyValueRow[],
  bodyMode: WorkbenchBodyMode,
  cookieRows: KeyValueRow[],
  authType: string,
  authToken: string,
) {
  const headers = rows.reduce<Record<string, string>>((result, row) => {
    const name = row.name.trim();
    if (row.enabled && name && !RESTRICTED_HEADER_NAMES.has(name.toLowerCase())) {
      result[name] = row.value;
    }
    return result;
  }, {});
  if (bodyMode === 'none' || bodyMode === 'form-data') removeHeader(headers, 'Content-Type');
  if (bodyMode === 'json' && !findHeaderKey(headers, 'Content-Type')) {
    setHeader(headers, 'Content-Type', 'application/json; charset=UTF-8');
  }
  if (bodyMode === 'form-urlencoded') {
    setHeader(headers, 'Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8');
  }
  const cookies = cookieRows
    .filter((row) => row.enabled && row.name.trim())
    .map((row) => `${row.name.trim()}=${row.value}`)
    .join('; ');
  if (cookies) setHeader(headers, 'Cookie', cookies);
  if (authType === 'bearer' && authToken.trim()) {
    setHeader(headers, 'Authorization', `Bearer ${authToken.trim()}`);
  }
  return headers;
}

export function buildFormFields(rows: FormRow[]): WorkbenchFormFieldPayload[] {
  return rows
    .filter((row) => row.enabled && row.name.trim())
    .map((row) => ({
      id: row.id,
      enabled: row.enabled,
      type: row.type,
      name: row.name.trim(),
      value: row.type === 'file' ? '' : row.value,
      filePartName: row.type === 'file' ? row.filePartName : undefined,
      fileName: row.type === 'file' ? row.file?.name || row.value : undefined,
      contentType: row.type === 'file' ? row.file?.type : undefined,
    }));
}

export function buildFileParts(rows: FormRow[]): WorkbenchFilePart[] {
  return rows
    .filter((row) => row.enabled && row.type === 'file' && row.name.trim() && row.file)
    .map((row) => ({ partName: row.filePartName, file: row.file as File }));
}

export function formFieldsToRows(fields: WorkbenchFormFieldPayload[] = []) {
  const rows = fields.map((field) => {
    const row = createFormRow(
      field.type || 'text',
      field.name,
      field.type === 'file' ? field.fileName || '' : field.value,
      field.enabled,
    );
    row.filePartName = field.filePartName || row.filePartName;
    return row;
  });
  return rows.length ? rows : createDefaultFormRows();
}

export function splitUrlAndParams(rawUrl: string) {
  try {
    const parsed = new URL(rawUrl);
    const params: KeyValueRow[] = [];
    parsed.searchParams.forEach((value, name) =>
      params.push(createKeyValueRow('param', name, value)),
    );
    parsed.search = '';
    return { url: parsed.toString(), params };
  } catch {
    return { url: rawUrl, params: [] };
  }
}

export function buildUrlWithParams(rawUrl: string, params: KeyValueRow[]) {
  const activeParams = params.filter((row) => row.enabled && row.name.trim());
  if (!activeParams.length) return rawUrl;
  try {
    const parsed = new URL(rawUrl);
    parsed.search = '';
    activeParams.forEach((row) => parsed.searchParams.append(row.name.trim(), row.value));
    return parsed.toString();
  } catch {
    return rawUrl;
  }
}

export function formatJsonText(value: string) {
  return JSON.stringify(JSON.parse(value), null, 2);
}

export function formatMaybeJson(value: string) {
  if (!value) return '';
  try {
    return formatJsonText(value);
  } catch {
    return value;
  }
}

export function isJsonText(value: string) {
  if (!value.trim()) return false;
  try {
    JSON.parse(value);
    return true;
  } catch {
    return false;
  }
}
