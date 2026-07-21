import { useMemo, useState } from 'react';
import { Empty, Tag, Typography } from 'antd';
import { ChevronDown, ChevronRight } from 'lucide-react';

import { formatMaybeJson } from './requestModel';
import type { ResponseCookieItem } from './responseModel';

export function ResponseHeadersView({ headers }: { headers: Record<string, string[]> }) {
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

export function ResponseCookiesView({ cookies }: { cookies: ResponseCookieItem[] }) {
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
              {cookie.attributes.map((attribute) => (
                <Tag key={attribute}>{attribute}</Tag>
              ))}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function jsonScalar(value: unknown) {
  if (typeof value === 'string')
    return <span className="json-value-string">{JSON.stringify(value)}</span>;
  if (value === null) return <span className="json-value-null">null</span>;
  if (typeof value === 'boolean')
    return <span className="json-value-boolean">{String(value)}</span>;
  return <span className="json-value-number">{String(value)}</span>;
}

function jsonLineCount(value: unknown): number {
  if (Array.isArray(value)) return 2 + value.reduce((sum, item) => sum + jsonLineCount(item), 0);
  if (value !== null && typeof value === 'object') {
    return (
      2 +
      Object.values(value as Record<string, unknown>).reduce<number>(
        (sum, item) => sum + jsonLineCount(item),
        0,
      )
    );
  }
  return 1;
}

interface JsonNodeProps {
  value: unknown;
  label?: string;
  depth: number;
  startLine: number;
  trailingComma?: boolean;
}

function JsonNode({ value, label, depth, startLine, trailingComma = false }: JsonNodeProps) {
  const isArray = Array.isArray(value);
  const isObject = value !== null && typeof value === 'object' && !isArray;
  const [expanded, setExpanded] = useState(true);
  const indentation = { paddingLeft: `${depth * 20}px` };
  const labelNode =
    label === undefined ? null : <span className="json-key">{JSON.stringify(label)}: </span>;
  if (!isArray && !isObject) {
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
  let nextLine = startLine + 1;
  const children = entries.map(([key, item], index) => {
    const childLine = nextLine;
    nextLine += jsonLineCount(item);
    return (
      <JsonNode
        key={`${depth}-${key ?? index}`}
        value={item}
        label={key}
        depth={depth + 1}
        startLine={childLine}
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

export function JsonResponseViewer({ body }: { body: string }) {
  const parsed = useMemo(() => {
    try {
      const value = JSON.parse(body);
      return { structured: value !== null && typeof value === 'object', value };
    } catch {
      return { structured: false, value: body };
    }
  }, [body]);
  if (!body) return <div className="response-code response-code-empty">(空响应)</div>;
  if (!parsed.structured) return <pre className="response-code">{formatMaybeJson(body)}</pre>;
  return (
    <div className="json-code-viewer">
      <JsonNode key={body} value={parsed.value} depth={0} startLine={1} />
    </div>
  );
}
