import axios from 'axios';
import { API_RESPONSE_DELAY_MS } from '../config/runtimeConfig';
import { emitApiProgress } from './progress';

let pendingApiRequests = 0;

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

function updateApiProgress(delta: number) {
  pendingApiRequests = Math.max(0, pendingApiRequests + delta);
  emitApiProgress({
    pending: pendingApiRequests,
    delayMs: API_RESPONSE_DELAY_MS,
  });
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

export const apiClient = axios.create({
  baseURL: '/api',
  timeout: 15000,
});

apiClient.interceptors.request.use((config) => {
  if (config.showGlobalProgress !== false) {
    updateApiProgress(1);
  }
  return config;
});

apiClient.interceptors.response.use(
  async (response) => {
    if (response.config.useResponseDelay !== false && API_RESPONSE_DELAY_MS > 0) {
      await wait(API_RESPONSE_DELAY_MS);
    }
    if (response.config.showGlobalProgress !== false) {
      updateApiProgress(-1);
    }
    return response;
  },
  async (error) => {
    if (error.config?.useResponseDelay !== false && API_RESPONSE_DELAY_MS > 0) {
      await wait(API_RESPONSE_DELAY_MS);
    }
    if (error.config?.showGlobalProgress !== false) {
      updateApiProgress(-1);
    }
    return Promise.reject(new Error(getErrorMessage(error)));
  },
);
