import { applicationLinkClient } from './client';
import type {
  ApplicationLinkApiResponse,
  ApplicationLinkFormValues,
  ApplicationLinkJob,
  ApplicationLinkJobStatus,
} from '../types';

interface JobSubmission { id: number; status: ApplicationLinkJobStatus; progress: number }
const requestConfig = { showGlobalProgress: false, useResponseDelay: false };
const terminalStatuses = new Set<ApplicationLinkJobStatus>(['success', 'failed', 'cancelled', 'timed_out']);

function unwrap<T>(response: ApplicationLinkApiResponse<T>, fallback: string) {
  if (!response.ok) throw new Error(response.message || fallback);
  return response.data;
}

function workflowConfig() {
  const id = crypto.randomUUID();
  return {
    ...requestConfig,
    headers: { 'X-Idempotency-Key': id, 'X-Trace-ID': id.split('-').join('') },
  };
}

export async function submitApplicationLink(values: ApplicationLinkFormValues) {
  const { data } = await applicationLinkClient.post<ApplicationLinkApiResponse<JobSubmission>>(
    '/product-data/tools/application-links/generate', values, workflowConfig(),
  );
  return unwrap(data, '提交申请链接生成失败');
}

export async function getApplicationLinkJob(id: number) {
  const { data } = await applicationLinkClient.get<ApplicationLinkApiResponse<ApplicationLinkJob>>(`/jobs/${id}`, requestConfig);
  return unwrap(data, '获取申请链接 Job 失败');
}

export async function pollApplicationLinkJob(id: number, onProgress: (job: ApplicationLinkJob) => void) {
  while (true) {
    const job = await getApplicationLinkJob(id);
    onProgress(job);
    if (job.status === 'success') return job;
    if (terminalStatuses.has(job.status)) throw new Error(job.errorMessage || `申请链接生成失败：${job.status}`);
    await new Promise((resolve) => window.setTimeout(resolve, 400));
  }
}
