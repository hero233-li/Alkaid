import { apiClient } from '../../../api/client';
import { createWorkflowHeaders } from '../../../utils/requestId';
import { pollJobUntilTerminal } from '../../../utils/jobPolling';
import type {
  ApplicationDataApiResponse,
  ApplicationDataConfig,
  ApplicationDataFormValues,
  ApplicationDataJob,
  ApplicationDataJobStatus,
} from '../types';

interface Submission {
  id: number;
  status: ApplicationDataJobStatus;
  progress: number;
}

const requestConfig = { showGlobalProgress: false, useResponseDelay: false };
const terminal = new Set<ApplicationDataJobStatus>(['success', 'failed', 'cancelled', 'timed_out']);

function unwrap<T>(value: ApplicationDataApiResponse<T>, fallback: string) {
  if (!value.ok) throw new Error(value.message || fallback);
  return value.data;
}

export async function getApplicationDataConfig() {
  const { data } = await apiClient.get<ApplicationDataApiResponse<ApplicationDataConfig>>(
    '/product-data/tools/application-data/config',
    requestConfig,
  );
  return unwrap(data, '获取申请数据配置失败');
}

export async function submitApplicationData(values: ApplicationDataFormValues) {
  const { data } = await apiClient.post<ApplicationDataApiResponse<Submission>>(
    '/product-data/tools/application-data/generate',
    { ...values, currentDate: values.currentDate.format('YYYY-MM-DD') },
    { ...requestConfig, headers: createWorkflowHeaders() },
  );
  return unwrap(data, '提交申请数据生成失败');
}

export async function pollApplicationData(
  id: number,
  onProgress: (job: ApplicationDataJob) => void,
  options: { signal?: AbortSignal; timeoutMs?: number } = {},
) {
  return pollJobUntilTerminal({
    fetchJob: async (signal) => {
      const { data } = await apiClient.get<ApplicationDataApiResponse<ApplicationDataJob>>(
        `/jobs/${id}`,
        { ...requestConfig, signal },
      );
      return unwrap(data, '获取申请数据 Job 失败');
    },
    onProgress,
    terminalStatuses: terminal,
    timeoutMessage: '申请数据 Job 轮询超时，请稍后查询任务状态',
    cancelledMessage: '申请数据 Job 轮询已取消',
    failureMessage: (job) => `生成失败：${job.status}`,
    intervalMs: 400,
    ...options,
  });
}
