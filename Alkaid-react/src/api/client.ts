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
    const message = error.response?.data?.message || error.message || '请求失败';
    return Promise.reject(new Error(message));
  },
);
