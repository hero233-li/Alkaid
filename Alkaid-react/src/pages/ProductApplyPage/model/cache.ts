import type { ProductApplicationConfig, ProductApplicationFormValues, ProductApplicationResult } from './types';

const FORM_CACHE_PREFIX = 'alioth:product-application-form:';
const RESULT_CACHE_LIMIT = 30;

export function formCacheKey(pageInstanceKey: string, configVersion: number) {
  return `${FORM_CACHE_PREFIX}v${configVersion}:${pageInstanceKey}`;
}

export function resultCacheKey(pageInstanceKey: string) {
  return `alioth:product-application-results:${pageInstanceKey}`;
}

export function clearStaleFormCaches(pageInstanceKey: string, activeKey: string) {
  Object.keys(sessionStorage)
    .filter((key) => key.startsWith(FORM_CACHE_PREFIX) && key.endsWith(`:${pageInstanceKey}`) && key !== activeKey)
    .forEach((key) => sessionStorage.removeItem(key));
}

export function readFormDraft(cacheKey: string): ProductApplicationFormValues {
  try {
    const value = JSON.parse(sessionStorage.getItem(cacheKey) || '{}');
    return value && typeof value === 'object' && !Array.isArray(value)
      ? value as ProductApplicationFormValues
      : {};
  } catch {
    return {};
  }
}

export function safeFormDraft(config: ProductApplicationConfig, values: ProductApplicationFormValues) {
  const persistableFields = new Set(
    config.fields.filter((field) => field.persistDraft).map((field) => field.name),
  );
  return Object.fromEntries(
    Object.entries(values).filter(([name, value]) => persistableFields.has(name) && value !== undefined),
  ) as ProductApplicationFormValues;
}

type ResultSummary = Omit<ProductApplicationResult, 'payload' | 'logs'>;

function toSummary(result: ProductApplicationResult): ResultSummary {
  const { payload: _payload, logs: _logs, ...summary } = result;
  return summary;
}

export function persistResultSummaries(cacheKey: string, results: ProductApplicationResult[]) {
  sessionStorage.setItem(
    cacheKey,
    JSON.stringify(results.slice(0, RESULT_CACHE_LIMIT).map(toSummary)),
  );
}

export function readResultSummaries(cacheKey: string): ProductApplicationResult[] {
  try {
    const value = JSON.parse(sessionStorage.getItem(cacheKey) || '[]');
    if (!Array.isArray(value)) {
      return [];
    }
    return value
      .filter((item) => item && typeof item === 'object' && typeof item.id === 'number')
      .map((item) => ({
        ...item,
        stage: item.stage || (item.status === 'success' ? 'completed' : item.status === 'failed' ? 'failed' : 'submitted'),
        payload: {},
        logs: [],
        traceId: item.traceId || '',
        idempotencyKey: item.idempotencyKey || '',
        attemptCount: item.attemptCount || 1,
      })) as ProductApplicationResult[];
  } catch {
    return [];
  }
}
