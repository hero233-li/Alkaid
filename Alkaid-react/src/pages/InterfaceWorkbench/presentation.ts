import type { WorkbenchHistoryItem } from '../../types';

export const DEFAULT_REQUEST_NAME = '快捷请求';

export function methodClassName(method: string) {
  return `method-${method.toLowerCase()}`;
}

export function statusColor(statusCode?: number) {
  if (!statusCode) return 'default';
  if (statusCode < 300) return 'success';
  if (statusCode < 400) return 'processing';
  if (statusCode < 500) return 'warning';
  return 'error';
}

export function displayRequestName(
  item: Pick<WorkbenchHistoryItem, 'name' | 'url'> | null | undefined,
) {
  if (!item) return DEFAULT_REQUEST_NAME;
  const name = item.name.trim();
  if (!name || name === item.url || name.startsWith('/') || /^https?:\/\//.test(name)) {
    return DEFAULT_REQUEST_NAME;
  }
  try {
    const parsed = new URL(item.url);
    return name === parsed.pathname || name === parsed.host ? DEFAULT_REQUEST_NAME : item.name;
  } catch {
    return item.name;
  }
}
