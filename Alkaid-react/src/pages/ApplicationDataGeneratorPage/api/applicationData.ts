import { apiClient } from '../../../api/client';
import { createWorkflowHeaders } from '../../../utils/requestId';
import type {
  ApplicationDataApiResponse,
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
const terminal = new Set<ApplicationDataJobStatus>([
  'success', 'failed', 'cancelled', 'timed_out',
]);

function unwrap<T>(value: ApplicationDataApiResponse<T>, fallback: string) {
  if (!value.ok) throw new Error(value.message || fallback);
  return value.data;
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
) {
  while (true) {
    const { data } = await apiClient.get<ApplicationDataApiResponse<ApplicationDataJob>>(
      `/jobs/${id}`,
      requestConfig,
    );
    const job = unwrap(data, '获取申请数据 Job 失败');
    onProgress(job);
    if (job.status === 'success') return job;
    if (terminal.has(job.status)) {
      throw new Error(job.errorMessage || `生成失败：${job.status}`);
    }
    await new Promise((resolve) => window.setTimeout(resolve, 400));
  }
}
