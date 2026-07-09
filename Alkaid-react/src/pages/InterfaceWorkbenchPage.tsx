import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Checkbox,
  Empty,
  Input,
  Modal,
  Popconfirm,
  Segmented,
  Select,
  Space,
  Spin,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import {
  ChevronDown,
  ChevronRight,
  Clipboard,
  FileJson,
  FolderOpen,
  History,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  SendHorizontal,
  Trash2,
  Upload,
  Zap,
} from 'lucide-react';
import {
  clearWorkbenchHistory,
  deleteWorkbenchHistory,
  executeWorkbenchRequest,
  fetchWorkbenchHistory,
  fetchWorkbenchHistoryDetail,
  renameWorkbenchHistory,
  type WorkbenchFilePart,
} from '../api/workbench';
import type {
  WorkbenchBodyMode,
  WorkbenchFormFieldPayload,
  WorkbenchFormFieldType,
  WorkbenchHistoryItem,
  WorkbenchRequestPayload,
  WorkbenchResponsePayload,
} from '../types';
import {
  REQUEST_CODE_LANGUAGE_OPTIONS,
  generateRequestCode,
  type RequestCodeLanguage,
} from '../utils/workbenchCodegen';

const { TextArea } = Input;

const METHOD_OPTIONS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD'].map((method) => ({
  label: method,
  value: method,
}));
const BODY_MODE_OPTIONS: Array<{ label: string; value: WorkbenchBodyMode }> = [
  { label: 'none', value: 'none' },
  { label: 'form-data', value: 'form-data' },
  { label: 'x-www-form-urlencoded', value: 'form-urlencoded' },
  { label: 'JSON', value: 'json' },
  { label: 'Raw', value: 'raw' },
];
const FORM_FIELD_TYPE_OPTIONS: Array<{ label: string; value: WorkbenchFormFieldType }> = [
  { label: '文本', value: 'text' },
  { label: '文件', value: 'file' },
];
const AUTH_TYPE_OPTIONS = [
  { label: '无认证', value: 'none' },
  { label: 'Bearer Token', value: 'bearer' },
];
const DEFAULT_REQUEST_NAME = '快捷请求';
const CURL_PLACEHOLDER = `curl -X POST https://example.com/api -H 'Content-Type: application/json' -d '{"name":"Alioth"}'`;
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

interface KeyValueRow {
  id: string;
  enabled: boolean;
  name: string;
  value: string;
}

interface FormRow {
  id: string;
  enabled: boolean;
  type: WorkbenchFormFieldType;
  name: string;
  value: string;
  filePartName: string;
  file: File | null;
}

interface CurlPayload {
  method: string;
  url: string;
  params: KeyValueRow[];
  headers: KeyValueRow[];
  bodyMode: WorkbenchBodyMode;
  body: string;
  formRows: FormRow[];
}

let rowId = 0;

function nextId(prefix: string) {
  rowId += 1;
  return `${prefix}-${Date.now()}-${rowId}`;
}

function createKeyValueRow(prefix: string, name = '', value = '', enabled = true): KeyValueRow {
  return {
    id: nextId(prefix),
    enabled,
    name,
    value,
  };
}

function createFormRow(type: WorkbenchFormFieldType = 'text', name = '', value = '', enabled = true): FormRow {
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

function createDefaultHeaders() {
  return [createKeyValueRow('header', 'Accept', 'application/json'), createKeyValueRow('header', 'Content-Type', 'application/json')];
}

function createDefaultFormRows() {
  return [createFormRow()];
}

function recordToRows(prefix: string, record: Record<string, string> = {}) {
  const rows = Object.entries(record).map(([name, value]) => createKeyValueRow(prefix, name, value));
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
  if (existingKey) {
    delete headers[existingKey];
  }
}

function buildCookieHeader(rows: KeyValueRow[]) {
  return rows
    .filter((row) => row.enabled && row.name.trim())
    .map((row) => `${row.name.trim()}=${row.value}`)
    .join('; ');
}

function buildHeaders(rows: KeyValueRow[], bodyMode: WorkbenchBodyMode, cookieRows: KeyValueRow[], authType: string, authToken: string) {
  const headers = rows.reduce<Record<string, string>>((result, row) => {
    const name = row.name.trim();
    if (row.enabled && name && !RESTRICTED_HEADER_NAMES.has(name.toLowerCase())) {
      result[name] = row.value;
    }
    return result;
  }, {});

  if (bodyMode === 'none' || bodyMode === 'form-data') {
    removeHeader(headers, 'Content-Type');
  }
  if (bodyMode === 'json' && !findHeaderKey(headers, 'Content-Type')) {
    setHeader(headers, 'Content-Type', 'application/json; charset=UTF-8');
  }
  if (bodyMode === 'form-urlencoded') {
    setHeader(headers, 'Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8');
  }

  const cookieHeader = buildCookieHeader(cookieRows);
  if (cookieHeader) {
    setHeader(headers, 'Cookie', cookieHeader);
  }
  if (authType === 'bearer' && authToken.trim()) {
    setHeader(headers, 'Authorization', `Bearer ${authToken.trim()}`);
  }
  return headers;
}

function buildFormFields(rows: FormRow[]): WorkbenchFormFieldPayload[] {
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

function buildFileParts(rows: FormRow[]): WorkbenchFilePart[] {
  return rows
    .filter((row) => row.enabled && row.type === 'file' && row.name.trim() && row.file)
    .map((row) => ({
      partName: row.filePartName,
      file: row.file as File,
    }));
}

function formFieldsToRows(fields: WorkbenchFormFieldPayload[] = []) {
  const rows = fields.map((field) => {
    const row = createFormRow(field.type || 'text', field.name, field.type === 'file' ? field.fileName || '' : field.value, field.enabled);
    row.filePartName = field.filePartName || row.filePartName;
    return row;
  });
  return rows.length ? rows : createDefaultFormRows();
}

function splitUrlAndParams(rawUrl: string) {
  try {
    const parsed = new URL(rawUrl);
    const params: KeyValueRow[] = [];
    parsed.searchParams.forEach((value, name) => params.push(createKeyValueRow('param', name, value)));
    parsed.search = '';
    return {
      url: parsed.toString(),
      params,
    };
  } catch {
    return { url: rawUrl, params: [] };
  }
}

function buildUrlWithParams(rawUrl: string, params: KeyValueRow[]) {
  const activeParams = params.filter((row) => row.enabled && row.name.trim());
  if (!activeParams.length) {
    return rawUrl;
  }
  try {
    const parsed = new URL(rawUrl);
    parsed.search = '';
    activeParams.forEach((row) => parsed.searchParams.append(row.name.trim(), row.value));
    return parsed.toString();
  } catch {
    return rawUrl;
  }
}

function formatJsonText(value: string) {
  return JSON.stringify(JSON.parse(value), null, 2);
}

function formatMaybeJson(value: string) {
  if (!value) {
    return '';
  }
  try {
    return formatJsonText(value);
  } catch {
    return value;
  }
}

function isJsonText(value: string) {
  if (!value.trim()) {
    return false;
  }
  try {
    JSON.parse(value);
    return true;
  } catch {
    return false;
  }
}

interface ResponseCookieItem {
  id: string;
  name: string;
  value: string;
  attributes: string[];
}

function parseResponseCookies(headers: Record<string, string[]> = {}): ResponseCookieItem[] {
  const setCookieValues = Object.entries(headers)
    .filter(([name]) => name.toLowerCase() === 'set-cookie' || name.toLowerCase() === 'set-cookie2')
    .flatMap(([, values]) => values || []);

  return setCookieValues.map((cookie, index) => {
    const parts = cookie.split(';').map((part) => part.trim()).filter(Boolean);
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

function ResponseHeadersView({ headers }: { headers: Record<string, string[]> }) {
  const rows = Object.entries(headers || {});
  if (!rows.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无响应 Header" />;
  }

  return (
    <div className="response-kv-table">
      <div className="response-kv-row response-kv-head">
        <span>名称</span>
        <span>值</span>
      </div>
      {rows.map(([name, values]) => (
        <div className="response-kv-row" key={name}>
          <Typography.Text className="response-kv-name">{name}</Typography.Text>
          <code>{(values || []).join('\n')}</code>
        </div>
      ))}
    </div>
  );
}

function ResponseCookiesView({ cookies }: { cookies: ResponseCookieItem[] }) {
  if (!cookies.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="响应中没有 Set-Cookie" />;
  }

  return (
    <div className="response-cookie-list">
      {cookies.map((cookie) => (
        <div className="response-cookie-item" key={cookie.id}>
          <div className="response-cookie-value">
            <Typography.Text strong>{cookie.name || '(未命名 Cookie)'}</Typography.Text>
            <code>{cookie.value}</code>
          </div>
          {cookie.attributes.length ? (
            <div className="response-cookie-attributes">
              {cookie.attributes.map((attribute) => <Tag key={attribute}>{attribute}</Tag>)}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function jsonScalar(value: unknown) {
  if (typeof value === 'string') {
    return <span className="json-value-string">{JSON.stringify(value)}</span>;
  }
  if (value === null) {
    return <span className="json-value-null">null</span>;
  }
  if (typeof value === 'boolean') {
    return <span className="json-value-boolean">{String(value)}</span>;
  }
  return <span className="json-value-number">{String(value)}</span>;
}

interface CollapsibleJsonNodeProps {
  value: unknown;
  label?: string;
  depth: number;
  startLine: number;
  trailingComma?: boolean;
}

function jsonLineCount(value: unknown): number {
  if (Array.isArray(value)) {
    return 2 + value.reduce((lines, item) => lines + jsonLineCount(item), 0);
  }
  if (value !== null && typeof value === 'object') {
    return 2 + Object.values(value as Record<string, unknown>).reduce<number>((lines, item) => lines + jsonLineCount(item), 0);
  }
  return 1;
}

function CollapsibleJsonNode({ value, label, depth, startLine, trailingComma = false }: CollapsibleJsonNodeProps) {
  const isArray = Array.isArray(value);
  const isObject = value !== null && typeof value === 'object' && !isArray;
  const isBranch = isArray || isObject;
  const [expanded, setExpanded] = useState(true);
  const indentation = { paddingLeft: `${depth * 20}px` };
  const labelNode = label === undefined ? null : <span className="json-key">{JSON.stringify(label)}: </span>;

  if (!isBranch) {
    return (
      <div className="json-code-line">
        <span className="json-line-number">{startLine}</span>
        <span className="json-code-content" style={indentation}>
          <span className="json-fold-placeholder" />
          {labelNode}
          {jsonScalar(value)}
          {trailingComma ? <span>,</span> : null}
        </span>
      </div>
    );
  }

  const entries: Array<[string | undefined, unknown]> = isArray
    ? (value as unknown[]).map((item) => [undefined, item])
    : Object.entries(value as Record<string, unknown>);
  const opening = isArray ? '[' : '{';
  const closing = isArray ? ']' : '}';
  let nextChildLine = startLine + 1;
  const children = entries.map(([key, item], index) => {
    const childStartLine = nextChildLine;
    nextChildLine += jsonLineCount(item);
    return (
      <CollapsibleJsonNode
        key={`${depth}-${key ?? index}`}
        value={item}
        label={key}
        depth={depth + 1}
        startLine={childStartLine}
        trailingComma={index < entries.length - 1}
      />
    );
  });
  const closingLine = startLine + jsonLineCount(value) - 1;

  return (
    <>
      <div className={`json-code-line ${expanded ? '' : 'is-collapsed'}`}>
        <span className="json-line-number">{startLine}</span>
        <span className="json-code-content" style={indentation}>
          <button
            type="button"
            className="json-fold-button"
            aria-label={expanded ? '折叠当前结构' : '展开当前结构'}
            onClick={() => setExpanded((current) => !current)}
          >
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
          {labelNode}
          <span>{opening}</span>
          {!expanded ? <span className="json-collapsed-content">…</span> : null}
          {!expanded ? <span>{closing}</span> : null}
          {!expanded && trailingComma ? <span>,</span> : null}
        </span>
      </div>
      {expanded ? children : null}
      {expanded ? (
        <div className="json-code-line">
          <span className="json-line-number">{closingLine}</span>
          <span className="json-code-content" style={indentation}>
            <span className="json-fold-placeholder" />
            <span>{closing}</span>
            {trailingComma ? <span>,</span> : null}
          </span>
        </div>
      ) : null}
    </>
  );
}

function JsonResponseViewer({ body }: { body: string }) {
  const parsed = useMemo(() => {
    try {
      const value = JSON.parse(body);
      return { structured: value !== null && typeof value === 'object', value };
    } catch {
      return { structured: false, value: body };
    }
  }, [body]);
  if (!body) {
    return <div className="response-code response-code-empty">(空响应)</div>;
  }
  if (!parsed.structured) {
    return <pre className="response-code">{formatMaybeJson(body)}</pre>;
  }

  return (
    <div className="json-code-viewer">
      <CollapsibleJsonNode key={body} value={parsed.value} depth={0} startLine={1} />
    </div>
  );
}

function methodClassName(method: string) {
  return `method-${method.toLowerCase()}`;
}

function statusColor(statusCode?: number) {
  if (!statusCode) {
    return 'default';
  }
  if (statusCode >= 200 && statusCode < 300) {
    return 'success';
  }
  if (statusCode >= 300 && statusCode < 400) {
    return 'processing';
  }
  if (statusCode >= 400 && statusCode < 500) {
    return 'warning';
  }
  if (statusCode >= 500) {
    return 'error';
  }
  return 'default';
}

function normalizeCurl(input: string) {
  return input.replace(/\r?\n\s*\\/g, ' ').trim();
}

function tokenizeCurl(input: string) {
  const tokens: string[] = [];
  let current = '';
  let quote: '"' | "'" | null = null;
  let escaping = false;

  for (const char of input) {
    if (escaping) {
      current += char;
      escaping = false;
      continue;
    }
    if (char === '\\') {
      escaping = true;
      continue;
    }
    if (quote) {
      if (char === quote) {
        quote = null;
      } else {
        current += char;
      }
      continue;
    }
    if (char === '"' || char === "'") {
      quote = char;
      continue;
    }
    if (/\s/.test(char)) {
      if (current) {
        tokens.push(current);
        current = '';
      }
      continue;
    }
    current += char;
  }
  if (current) {
    tokens.push(current);
  }
  return tokens;
}

function parseHeaderLine(value: string) {
  const index = value.indexOf(':');
  if (index < 0) {
    return null;
  }
  return createKeyValueRow('header', value.slice(0, index).trim(), value.slice(index + 1).trim());
}

function parseFormPart(value: string) {
  const pair = value.split(';')[0];
  const index = pair.indexOf('=');
  if (index < 0) {
    return null;
  }
  const name = pair.slice(0, index).trim();
  const rawValue = pair.slice(index + 1);
  if (!name) {
    return null;
  }
  if (rawValue.startsWith('@')) {
    return createFormRow('file', name, rawValue);
  }
  return createFormRow('text', name, rawValue);
}

function parseUrlEncodedRows(body: string) {
  const rows: FormRow[] = [];
  try {
    const params = new URLSearchParams(body);
    params.forEach((value, name) => rows.push(createFormRow('text', name, value)));
  } catch {
    return rows;
  }
  return rows;
}

function inferBodyMode(headers: KeyValueRow[], body: string, formRows: FormRow[]): WorkbenchBodyMode {
  if (formRows.length > 0) {
    return 'form-data';
  }
  const contentType = headers.find((row) => row.name.toLowerCase() === 'content-type')?.value.toLowerCase() || '';
  if (!body) {
    return 'none';
  }
  if (contentType.includes('application/x-www-form-urlencoded')) {
    return 'form-urlencoded';
  }
  if (contentType.includes('multipart/form-data')) {
    return 'form-data';
  }
  if (contentType.includes('application/json') || isJsonText(body)) {
    return 'json';
  }
  return 'raw';
}

function parseCurl(input: string): CurlPayload {
  const tokens = tokenizeCurl(normalizeCurl(input));
  if (tokens[0]?.toLowerCase() === 'curl') {
    tokens.shift();
  }

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
      continue;
    }
    if (token.startsWith('-X') && token.length > 2) {
      method = token.slice(2).toUpperCase();
      continue;
    }
    if (token === '-H' || token === '--header') {
      const header = parseHeaderLine(next());
      if (header) {
        headers.push(header);
      }
      continue;
    }
    if (token.startsWith('-H') && token.length > 2) {
      const header = parseHeaderLine(token.slice(2));
      if (header) {
        headers.push(header);
      }
      continue;
    }
    if (['-d', '--data', '--data-raw', '--data-binary', '--data-urlencode'].includes(token)) {
      dataParts.push(next());
      continue;
    }
    if (token === '-F' || token === '--form' || token === '--form-string') {
      const row = parseFormPart(next());
      if (row) {
        formRows.push(row);
      }
      continue;
    }
    if (token === '-b' || token === '--cookie') {
      const cookie = next();
      if (cookie) {
        headers.push(createKeyValueRow('header', 'Cookie', cookie));
      }
      continue;
    }
    if (token === '--url') {
      rawUrl = next();
      continue;
    }
    if (!token.startsWith('-') && !rawUrl) {
      rawUrl = token;
    }
  }

  if (!rawUrl) {
    throw new Error('没有从 cURL 中解析到 URL');
  }

  const body = dataParts.join('&');
  const bodyMode = inferBodyMode(headers, body, formRows);
  const urlEncodedRows = bodyMode === 'form-urlencoded' ? parseUrlEncodedRows(body) : [];
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

function isGeneratedRequestName(name: string, url: string) {
  const trimmedName = name.trim();
  if (!trimmedName || trimmedName === url || trimmedName.startsWith('/') || trimmedName.startsWith('http://') || trimmedName.startsWith('https://')) {
    return true;
  }
  try {
    const parsed = new URL(url);
    return trimmedName === parsed.pathname || trimmedName === parsed.host;
  } catch {
    return false;
  }
}

function displayRequestName(item: Pick<WorkbenchHistoryItem, 'name' | 'url'> | null | undefined) {
  if (!item || isGeneratedRequestName(item.name || '', item.url || '')) {
    return DEFAULT_REQUEST_NAME;
  }
  return item.name;
}

interface RequestCodeViewProps {
  payload: WorkbenchRequestPayload | null;
  language: RequestCodeLanguage;
  onLanguageChange: (language: RequestCodeLanguage) => void;
}

function RequestCodeView({ payload, language, onLanguageChange }: RequestCodeViewProps) {
  const code = useMemo(() => (payload ? generateRequestCode(payload, language) : ''), [payload, language]);

  const copyCode = async () => {
    if (!code) {
      return;
    }
    try {
      await navigator.clipboard.writeText(code);
      message.success('请求代码已复制');
    } catch {
      message.error('复制失败');
    }
  };

  if (!payload) {
    return (
      <div className="request-code-empty">
        <Empty description="发送请求后查看实际请求代码" />
      </div>
    );
  }

  return (
    <div className="request-code-view">
      <div className="request-code-toolbar">
        <Segmented
          value={language}
          options={REQUEST_CODE_LANGUAGE_OPTIONS}
          onChange={(value) => onLanguageChange(value as RequestCodeLanguage)}
        />
        <Tooltip title="复制请求代码">
          <Button icon={<Clipboard size={16} />} onClick={copyCode}>
            复制
          </Button>
        </Tooltip>
      </div>
      <pre className="response-code request-code-block">{code}</pre>
    </div>
  );
}

export default function InterfaceWorkbenchPage() {
  const [method, setMethod] = useState('GET');
  const [url, setUrl] = useState('');
  const [params, setParams] = useState<KeyValueRow[]>([]);
  const [headers, setHeaders] = useState<KeyValueRow[]>(createDefaultHeaders);
  const [cookies, setCookies] = useState<KeyValueRow[]>([]);
  const [authType, setAuthType] = useState('none');
  const [authToken, setAuthToken] = useState('');
  const [bodyMode, setBodyMode] = useState<WorkbenchBodyMode>('none');
  const [body, setBody] = useState('');
  const [formRows, setFormRows] = useState<FormRow[]>(createDefaultFormRows);
  const [timeoutSeconds, setTimeoutSeconds] = useState(30);
  const [response, setResponse] = useState<WorkbenchResponsePayload | null>(null);
  const [lastRequest, setLastRequest] = useState<WorkbenchRequestPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyItems, setHistoryItems] = useState<WorkbenchHistoryItem[]>([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState<number | null>(null);
  const [historySearch, setHistorySearch] = useState('');
  const [curlModalOpen, setCurlModalOpen] = useState(false);
  const [curlText, setCurlText] = useState('');
  const [renameModalOpen, setRenameModalOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState<WorkbenchHistoryItem | null>(null);
  const [renameName, setRenameName] = useState('');
  const [renameSaving, setRenameSaving] = useState(false);
  const [requestCodeLanguage, setRequestCodeLanguage] = useState<RequestCodeLanguage>('shell');

  const filteredHistory = useMemo(() => {
    const keyword = historySearch.trim().toLowerCase();
    if (!keyword) {
      return historyItems;
    }
    return historyItems.filter((item) => `${item.method} ${displayRequestName(item)} ${item.url}`.toLowerCase().includes(keyword));
  }, [historyItems, historySearch]);
  const selectedHistoryItem = useMemo(
    () => historyItems.find((item) => item.id === selectedHistoryId) || null,
    [historyItems, selectedHistoryId],
  );
  const requestTabTitle = displayRequestName(selectedHistoryItem);

  const updateRow = (setter: React.Dispatch<React.SetStateAction<KeyValueRow[]>>, id: string, patch: Partial<KeyValueRow>) => {
    setter((rows) => rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  };

  const removeRow = (setter: React.Dispatch<React.SetStateAction<KeyValueRow[]>>, id: string) => {
    setter((rows) => rows.filter((row) => row.id !== id));
  };

  const updateFormRow = (id: string, patch: Partial<FormRow>) => {
    setFormRows((rows) => rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  };

  const loadHistory = async (selectId?: number) => {
    setHistoryLoading(true);
    try {
      const items = await fetchWorkbenchHistory();
      setHistoryItems(items);
      if (selectId) {
        setSelectedHistoryId(selectId);
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : '请求历史获取失败');
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const resetRequest = () => {
    setMethod('GET');
    setUrl('');
    setParams([]);
    setHeaders(createDefaultHeaders());
    setCookies([]);
    setAuthType('none');
    setAuthToken('');
    setBodyMode('none');
    setBody('');
    setFormRows(createDefaultFormRows());
    setResponse(null);
    setLastRequest(null);
    setSelectedHistoryId(null);
  };

  const parseParamsFromUrl = () => {
    if (!url.includes('?')) {
      return;
    }
    const splitUrl = splitUrlAndParams(url);
    setUrl(splitUrl.url);
    setParams(splitUrl.params);
  };

  const sendRequest = async () => {
    if (!url.trim()) {
      message.warning('请先填写 URL');
      return;
    }
    const finalUrl = buildUrlWithParams(url.trim(), params);
    const payload: WorkbenchRequestPayload = {
      method,
      url: finalUrl,
      headers: buildHeaders(headers, bodyMode, cookies, authType, authToken),
      bodyMode,
      body: bodyMode === 'none' ? '' : body,
      formFields: bodyMode === 'form-urlencoded' || bodyMode === 'form-data' ? buildFormFields(formRows) : [],
      timeoutSeconds,
    };
    setLoading(true);
    try {
      const result = await executeWorkbenchRequest(payload, bodyMode === 'form-data' ? buildFileParts(formRows) : []);
      setResponse(result);
      setLastRequest(payload);
      await loadHistory(result.historyId);
      if (result.success) {
        message.success('请求完成');
      } else {
        message.error(result.errorMessage || '请求失败');
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : '请求失败');
    } finally {
      setLoading(false);
    }
  };

  const openHistory = async (id: number) => {
    setSelectedHistoryId(id);
    setHistoryLoading(true);
    try {
      const detail = await fetchWorkbenchHistoryDetail(id);
      const payload = detail.requestPayload;
      const splitUrl = splitUrlAndParams(payload.url || detail.url);
      setMethod(payload.method || detail.method || 'GET');
      setUrl(splitUrl.url);
      setParams(splitUrl.params);
      setHeaders(recordToRows('header', payload.headers || detail.requestHeaders || {}));
      setCookies([]);
      setAuthType('none');
      setAuthToken('');
      setBodyMode(payload.bodyMode || 'raw');
      setBody(payload.body || '');
      setFormRows(formFieldsToRows(payload.formFields));
      setResponse({
        success: Boolean(detail.success),
        statusCode: detail.responseStatus || 0,
        durationMs: detail.durationMs || 0,
        headers: detail.responseHeaders || {},
        body: detail.responseBody || '',
        errorMessage: detail.errorMessage,
        historyId: detail.id,
      });
      setLastRequest(payload);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '请求历史详情获取失败');
    } finally {
      setHistoryLoading(false);
    }
  };

  const clearHistory = async () => {
    try {
      await clearWorkbenchHistory();
      setHistoryItems([]);
      setSelectedHistoryId(null);
      message.success('请求历史已清理');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '请求历史清理失败');
    }
  };

  const startRenameHistory = (item: WorkbenchHistoryItem) => {
    setRenameTarget(item);
    setRenameName(displayRequestName(item));
    setRenameModalOpen(true);
  };

  const submitRenameHistory = async () => {
    if (!renameTarget) {
      return;
    }
    const nextName = renameName.trim();
    if (!nextName) {
      message.warning('请求名称不能为空');
      return;
    }
    setRenameSaving(true);
    try {
      const updated = await renameWorkbenchHistory(renameTarget.id, nextName);
      setHistoryItems((items) => items.map((item) => (item.id === updated.id ? updated : item)));
      setRenameModalOpen(false);
      setRenameTarget(null);
      message.success('请求名称已修改');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '请求名称修改失败');
    } finally {
      setRenameSaving(false);
    }
  };

  const deleteHistoryItem = async (id: number) => {
    try {
      await deleteWorkbenchHistory(id);
      setHistoryItems((items) => items.filter((item) => item.id !== id));
      if (selectedHistoryId === id) {
        setSelectedHistoryId(null);
        setResponse(null);
        setLastRequest(null);
      }
      message.success('请求记录已删除');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '请求删除失败');
    }
  };

  const formatBody = () => {
    if (bodyMode !== 'json') {
      message.warning('只有 JSON 请求体可以格式化');
      return;
    }
    if (!body.trim()) {
      return;
    }
    try {
      setBody(formatJsonText(body));
    } catch {
      message.warning('当前请求体不是合法 JSON');
    }
  };

  const openCurlModal = () => {
    setCurlText('');
    setCurlModalOpen(true);
  };

  const closeCurlModal = () => {
    setCurlModalOpen(false);
    setCurlText('');
  };

  const importCurl = () => {
    try {
      const parsed = parseCurl(curlText);
      setMethod(METHOD_OPTIONS.some((item) => item.value === parsed.method) ? parsed.method : 'GET');
      setUrl(parsed.url);
      setParams(parsed.params);
      setHeaders(parsed.headers.length ? parsed.headers : createDefaultHeaders());
      setBodyMode(parsed.bodyMode);
      setBody(parsed.bodyMode === 'form-urlencoded' || parsed.bodyMode === 'form-data' ? '' : parsed.body);
      setFormRows(parsed.formRows.length ? parsed.formRows : createDefaultFormRows());
      closeCurlModal();
      message.success('cURL 已导入');
    } catch (error) {
      message.error(error instanceof Error ? error.message : 'cURL 解析失败');
    }
  };

  const copyResponseBody = async () => {
    if (!response?.body) {
      return;
    }
    try {
      await navigator.clipboard.writeText(response.body);
      message.success('响应体已复制');
    } catch {
      message.error('复制失败');
    }
  };

  const responseCookies = response ? parseResponseCookies(response.headers) : [];
  const responseHeaderCount = response ? Object.keys(response.headers || {}).length : 0;
  const showFormEditor = bodyMode === 'form-urlencoded' || bodyMode === 'form-data';

  const keyValueEditor = (
    rows: KeyValueRow[],
    setter: React.Dispatch<React.SetStateAction<KeyValueRow[]>>,
    prefix: string,
    addText = '新增参数',
  ) => (
    <div className="kv-editor">
      <div className="workbench-section-header slim">
        <Typography.Text strong>{addText.replace('新增', '')}</Typography.Text>
        <Button icon={<Plus size={16} />} onClick={() => setter((items) => [...items, createKeyValueRow(prefix)])}>
          {addText}
        </Button>
      </div>
      <div className="kv-grid kv-grid-head">
        <span>启用</span>
        <span>参数名</span>
        <span>参数值</span>
        <span>操作</span>
      </div>
      <div className="kv-list">
        {rows.map((row) => (
          <div className="kv-grid" key={row.id}>
            <Checkbox checked={row.enabled} onChange={(event) => updateRow(setter, row.id, { enabled: event.target.checked })} />
            <Input value={row.name} placeholder="name" onChange={(event) => updateRow(setter, row.id, { name: event.target.value })} />
            <Input value={row.value} placeholder="value" onChange={(event) => updateRow(setter, row.id, { value: event.target.value })} />
            <Tooltip title="删除">
              <Button icon={<Trash2 size={16} />} onClick={() => removeRow(setter, row.id)} />
            </Tooltip>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="workbench-apifox">
      <aside className="workbench-library">
        <div className="workbench-library-title">
          <div>
            <Typography.Title level={4}>接口管理</Typography.Title>
            <Typography.Text type="secondary">快速请求</Typography.Text>
          </div>
          <Tooltip title="新建请求">
            <Button type="primary" icon={<Plus size={16} />} onClick={resetRequest} />
          </Tooltip>
        </div>
        <Input
          prefix={<Search size={16} />}
          value={historySearch}
          placeholder="搜索请求历史"
          onChange={(event) => setHistorySearch(event.target.value)}
        />
        <div className="workbench-library-actions">
          <Button icon={<Upload size={16} />} onClick={openCurlModal}>
            导入 cURL
          </Button>
          <Button icon={<RefreshCw size={16} />} onClick={() => loadHistory()} />
          <Popconfirm title="清空请求历史？" okText="清空" cancelText="取消" onConfirm={clearHistory}>
            <Button icon={<Trash2 size={16} />} />
          </Popconfirm>
        </div>

        <div className="history-group-label">
          <FolderOpen size={16} />
          <span>请求历史</span>
          <Tag>{historyItems.length}</Tag>
        </div>
        <Spin spinning={historyLoading}>
          <div className="history-list">
            {filteredHistory.length ? (
              filteredHistory.map((item) => (
                <div className={`history-item ${selectedHistoryId === item.id ? 'active' : ''}`} key={item.id}>
                  <button className="history-item-main" onClick={() => openHistory(item.id)}>
                    <span className={`history-method ${methodClassName(item.method)}`}>{item.method}</span>
                    <span className="history-content">
                      <span className="history-name">{displayRequestName(item)}</span>
                      <span className="history-url">{item.url}</span>
                    </span>
                    <span className="history-meta">
                      <Tag color={item.success ? statusColor(item.responseStatus) : 'error'}>{item.responseStatus || 'ERR'}</Tag>
                      <span>{item.durationMs ?? '-'}ms</span>
                    </span>
                  </button>
                  <span className="history-item-actions">
                    <Tooltip title="修改名称">
                      <Button size="small" type="text" icon={<Pencil size={14} />} onClick={() => startRenameHistory(item)} />
                    </Tooltip>
                    <Popconfirm title="删除这条请求？" okText="删除" cancelText="取消" onConfirm={() => deleteHistoryItem(item.id)}>
                      <Button size="small" type="text" danger icon={<Trash2 size={14} />} />
                    </Popconfirm>
                  </span>
                </div>
              ))
            ) : (
              <Empty className="history-empty" image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无请求记录" />
            )}
          </div>
        </Spin>
      </aside>

      <main className="workbench-main-pane">
        <div className="workbench-tabs-strip">
          <div className="request-tab active">
            <Zap size={15} />
            <span>{requestTabTitle}</span>
          </div>
          <Button icon={<Plus size={16} />} onClick={resetRequest} />
        </div>

        <section className="request-editor-pane">
          <div className="request-url-bar">
            <Select className="method-select" value={method} options={METHOD_OPTIONS} onChange={setMethod} />
            <Input
              value={url}
              placeholder="https://example.com/api/demo"
              onBlur={parseParamsFromUrl}
              onChange={(event) => setUrl(event.target.value)}
              onPressEnter={sendRequest}
            />
            <Button type="primary" icon={<SendHorizontal size={16} />} loading={loading} onClick={sendRequest}>
              发送
            </Button>
          </div>

          <Tabs
            className="request-config-tabs"
            items={[
              {
                key: 'params',
                label: `Params ${params.filter((row) => row.enabled && row.name.trim()).length}`,
                children: keyValueEditor(params, setParams, 'param', '新增参数'),
              },
              {
                key: 'body',
                label: 'Body',
                children: (
                  <div className="body-editor">
                    <div className="body-mode-line">
                      <Segmented value={bodyMode} options={BODY_MODE_OPTIONS} onChange={(value) => setBodyMode(value as WorkbenchBodyMode)} />
                      <Button icon={<FileJson size={16} />} disabled={bodyMode !== 'json'} onClick={formatBody}>
                        格式化 JSON
                      </Button>
                    </div>
                    {bodyMode === 'none' ? (
                      <div className="body-empty">
                        <Empty description="该请求没有 Body" />
                      </div>
                    ) : null}
                    {bodyMode === 'json' || bodyMode === 'raw' ? (
                      <TextArea
                        className="request-body-input"
                        value={body}
                        placeholder={bodyMode === 'json' ? '{"name":"Alioth"}' : 'raw request body'}
                        onChange={(event) => setBody(event.target.value)}
                      />
                    ) : null}
                    {showFormEditor ? (
                      <>
                        <div className={`form-field-grid form-field-head ${bodyMode === 'form-data' ? 'with-type' : ''}`}>
                          <span>启用</span>
                          {bodyMode === 'form-data' ? <span>类型</span> : null}
                          <span>名称</span>
                          <span>值</span>
                          <span>操作</span>
                        </div>
                        <div className="form-field-list">
                          {formRows.map((row) => (
                            <div className={`form-field-grid ${bodyMode === 'form-data' ? 'with-type' : ''}`} key={row.id}>
                              <Checkbox
                                checked={row.enabled}
                                onChange={(event) => updateFormRow(row.id, { enabled: event.target.checked })}
                              />
                              {bodyMode === 'form-data' ? (
                                <Select
                                  value={row.type}
                                  options={FORM_FIELD_TYPE_OPTIONS}
                                  onChange={(value) => updateFormRow(row.id, { type: value, value: '', file: null })}
                                />
                              ) : null}
                              <Input
                                value={row.name}
                                placeholder="name"
                                onChange={(event) => updateFormRow(row.id, { name: event.target.value })}
                              />
                              {bodyMode === 'form-data' && row.type === 'file' ? (
                                <div className="file-field-cell">
                                  <input
                                    className="form-file-input"
                                    type="file"
                                    onChange={(event) => updateFormRow(row.id, { file: event.currentTarget.files?.[0] || null })}
                                  />
                                  {row.file ? <Typography.Text type="secondary">{row.file.name}</Typography.Text> : null}
                                  {!row.file && row.value ? <Typography.Text type="secondary">{row.value}</Typography.Text> : null}
                                </div>
                              ) : (
                                <Input
                                  value={row.value}
                                  placeholder="value"
                                  onChange={(event) => updateFormRow(row.id, { value: event.target.value })}
                                />
                              )}
                              <Tooltip title="删除">
                                <Button icon={<Trash2 size={16} />} onClick={() => setFormRows((rows) => rows.filter((item) => item.id !== row.id))} />
                              </Tooltip>
                            </div>
                          ))}
                        </div>
                        <Button icon={<Plus size={16} />} onClick={() => setFormRows((rows) => [...rows, createFormRow()])}>
                          新增字段
                        </Button>
                      </>
                    ) : null}
                  </div>
                ),
              },
              {
                key: 'headers',
                label: `Headers ${headers.filter((row) => row.enabled && row.name.trim()).length}`,
                children: keyValueEditor(headers, setHeaders, 'header', '新增 Header'),
              },
              {
                key: 'cookies',
                label: `Cookies ${cookies.filter((row) => row.enabled && row.name.trim()).length}`,
                children: keyValueEditor(cookies, setCookies, 'cookie', '新增 Cookie'),
              },
              {
                key: 'auth',
                label: 'Auth',
                children: (
                  <div className="auth-editor">
                    <Select value={authType} options={AUTH_TYPE_OPTIONS} onChange={setAuthType} />
                    <Input.Password
                      value={authToken}
                      disabled={authType !== 'bearer'}
                      placeholder="Bearer Token"
                      onChange={(event) => setAuthToken(event.target.value)}
                    />
                  </div>
                ),
              },
            ]}
          />
        </section>

        <section className="response-pane">
          <div className="response-summary">
            <div className="response-title">
              <History size={16} />
              <Typography.Text strong>响应</Typography.Text>
            </div>
            {response ? (
              <Space>
                <Tag color={response.success ? statusColor(response.statusCode) : 'error'}>
                  {response.success ? response.statusCode : 'ERROR'}
                </Tag>
                <Typography.Text type="secondary">{response.durationMs} ms</Typography.Text>
                <Tooltip title="复制响应体">
                  <Button icon={<Clipboard size={16} />} onClick={copyResponseBody} />
                </Tooltip>
              </Space>
            ) : null}
          </div>

          {!response ? (
            <div className="response-empty">
              <Empty description="发送请求后查看响应，每次请求都会写入左侧历史" />
            </div>
          ) : (
            <>
              {response.errorMessage ? <Alert type="error" message={response.errorMessage} showIcon /> : null}
              <Tabs
                className="response-tabs"
                items={[
                  {
                    key: 'body',
                    label: 'Body',
                    children: <JsonResponseViewer body={response.body} />,
                  },
                  {
                    key: 'cookies',
                    label: `Cookie ${responseCookies.length}`,
                    children: <ResponseCookiesView cookies={responseCookies} />,
                  },
                  {
                    key: 'headers',
                    label: `Header ${responseHeaderCount}`,
                    children: <ResponseHeadersView headers={response.headers || {}} />,
                  },
                  {
                    key: 'actual',
                    label: '实际请求',
                    children: (
                      <RequestCodeView
                        payload={lastRequest}
                        language={requestCodeLanguage}
                        onLanguageChange={setRequestCodeLanguage}
                      />
                    ),
                  },
                ]}
              />
            </>
          )}
        </section>
      </main>

      <Modal
        title="导入 cURL"
        open={curlModalOpen}
        onCancel={closeCurlModal}
        onOk={importCurl}
        okText="解析并填入"
        cancelText="取消"
        width={720}
      >
        <TextArea
          className="curl-import-input"
          value={curlText}
          placeholder={CURL_PLACEHOLDER}
          onChange={(event) => setCurlText(event.target.value)}
        />
      </Modal>

      <Modal
        title="修改请求名称"
        open={renameModalOpen}
        confirmLoading={renameSaving}
        onCancel={() => {
          setRenameModalOpen(false);
          setRenameTarget(null);
        }}
        onOk={submitRenameHistory}
        okText="保存"
        cancelText="取消"
      >
        <Input
          value={renameName}
          placeholder="请输入请求名称"
          maxLength={200}
          onChange={(event) => setRenameName(event.target.value)}
          onPressEnter={submitRenameHistory}
        />
      </Modal>
    </div>
  );
}
