import axios from 'axios';
import { API_RESPONSE_DELAY_MS } from '../config/runtimeConfig';

declare module 'axios' {
  export interface AxiosRequestConfig {
    showGlobalProgress?: boolean;
    useResponseDelay?: boolean;
  }
}

function wait(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export class ApiError extends Error {
  status?: number;
  code?: string;
  traceId?: string;
  retryable: boolean;
  details?: unknown;

  constructor(options: {
    message: string;
    status?: number;
    code?: string;
    traceId?: string;
    retryable?: boolean;
    details?: unknown;
  }) {
    super(options.message);
    this.name = 'ApiError';
    this.status = options.status;
    this.code = options.code;
    this.traceId = options.traceId;
    this.retryable = options.retryable ?? false;
    this.details = options.details;
  }
}

function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data;
    if (typeof data === 'string' && data.trim() && !data.trimStart().startsWith('<')) {
      return data;
    }
    if (data && typeof data === 'object') {
      const body = data as Record<string, unknown>;
      for (const key of ['message', 'detail', 'error']) {
        if (typeof body[key] === 'string' && body[key]) {
          return body[key] as string;
        }
      }
    }
    if (error.code === 'ERR_NETWORK') {
      return '后端服务不可达，请确认 Django 服务和端口 8000 已启动';
    }
    if (error.response?.status) {
      return `请求失败（HTTP ${error.response.status}）`;
    }
  }
  return error instanceof Error ? error.message : '请求失败';
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (!axios.isAxiosError(error)) {
    return new ApiError({ message: getErrorMessage(error), details: error });
  }
  const status = error.response?.status;
  const data = error.response?.data;
  const body = data && typeof data === 'object' ? (data as Record<string, unknown>) : undefined;
  const traceHeader = error.response?.headers?.['x-trace-id'];
  return new ApiError({
    message: getErrorMessage(error),
    status,
    code: typeof body?.code === 'string' ? body.code : error.code,
    traceId:
      typeof body?.traceId === 'string'
        ? body.traceId
        : typeof traceHeader === 'string'
          ? traceHeader
          : undefined,
    retryable: !status || status === 408 || status === 429 || status >= 500,
    details: body?.data,
  });
}

export const apiClient = axios.create({
  baseURL: '/api',
  timeout: 15000,
});

apiClient.interceptors.response.use(
  async (response) => {
    if (response.config.useResponseDelay !== false && API_RESPONSE_DELAY_MS > 0) {
      await wait(API_RESPONSE_DELAY_MS);
    }
    return response;
  },
  async (error) => {
    if (error.config?.useResponseDelay !== false && API_RESPONSE_DELAY_MS > 0) {
      await wait(API_RESPONSE_DELAY_MS);
    }
    if (axios.isCancel(error)) return Promise.reject(error);
    return Promise.reject(toApiError(error));
  },
);
