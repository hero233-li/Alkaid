import { apiClient } from '../../../api/client';
import { createWorkflowHeaders } from '../../../utils/requestId';
import { pollJobUntilTerminal } from '../../../utils/jobPolling';
import type {
  CardAction,
  CardActionValues,
  CardApiResponse,
  CardJob,
  CardJobStatus,
  CardSearchValues,
} from '../types';

interface Submission { id: number; status: CardJobStatus; progress: number }
const requestConfig = { showGlobalProgress: false, useResponseDelay: false };
const terminal = new Set<CardJobStatus>(['success', 'failed', 'cancelled', 'timed_out']);

function unwrap<T>(value: CardApiResponse<T>, fallback: string) {
  if (!value.ok) throw new Error(value.message || fallback);
  return value.data;
}

function workflowConfig() {
  return { ...requestConfig, headers: createWorkflowHeaders() };
}

export async function submitCardSearch(values: CardSearchValues) {
  const { data } = await apiClient.post<CardApiResponse<Submission>>(
    '/product-data/tools/cards/search', values, workflowConfig(),
  );
  return unwrap(data, '提交卡查询失败');
}

export async function submitCardAction(
  cardNo: string,
  action: CardAction,
  values: CardActionValues,
) {
  const { data } = await apiClient.post<CardApiResponse<Submission>>(
    `/product-data/tools/cards/${encodeURIComponent(cardNo)}/actions/${action}`,
    values,
    workflowConfig(),
  );
  return unwrap(data, '提交卡操作失败');
}

export async function pollCardJob(
  id: number,
  onProgress: (job: CardJob) => void,
  options: { signal?: AbortSignal; timeoutMs?: number } = {},
) {
  return pollJobUntilTerminal({
    fetchJob: async (signal) => {
      const { data } = await apiClient.get<CardApiResponse<CardJob>>(
        `/jobs/${id}`, { ...requestConfig, signal },
      );
      return unwrap(data, '获取卡处理 Job 失败');
    },
    onProgress,
    terminalStatuses: terminal,
    timeoutMessage: '卡处理 Job 轮询超时，请稍后查询任务状态',
    cancelledMessage: '卡处理 Job 轮询已取消',
    failureMessage: (job) => `Job ${job.status}`,
    intervalMs: 400,
    ...options,
  });
}
