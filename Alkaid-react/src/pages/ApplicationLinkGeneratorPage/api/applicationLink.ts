import { applicationLinkClient } from './client';
import { terminalApplicationLinkJobStatuses } from '../model/jobModel';
import { createWorkflowHeaders } from '../../../utils/requestId';
import { pollJobUntilTerminal } from '../../../utils/jobPolling';
import type {
  ApplicationLinkApiResponse,
  ApplicationLinkBackendConfig,
  ApplicationLinkJob,
  ApplicationLinkSubmission,
} from '../model/types';
import type { JobSubmission } from '../../../types/jobs';

const requestConfig = { showGlobalProgress: false, useResponseDelay: false };

function unwrap<T>(response: ApplicationLinkApiResponse<T>, fallback: string) {
  if (!response.ok) throw new Error(response.message || fallback);
  return response.data;
}

export async function getApplicationLinkConfig() {
  const { data } = await applicationLinkClient.get<
    ApplicationLinkApiResponse<ApplicationLinkBackendConfig>
  >('/product-data/tools/application-links/config', requestConfig);
  return unwrap(data, '获取申请链接配置失败');
}

function workflowConfig() {
  return {
    ...requestConfig,
    headers: createWorkflowHeaders(),
  };
}

export async function submitApplicationLink(values: ApplicationLinkSubmission) {
  const { data } = await applicationLinkClient.post<ApplicationLinkApiResponse<JobSubmission>>(
    '/product-data/tools/application-links/generate',
    values,
    workflowConfig(),
  );
  return unwrap(data, '提交申请链接生成失败');
}

export async function getApplicationLinkJob(id: number, signal?: AbortSignal) {
  const { data } = await applicationLinkClient.get<ApplicationLinkApiResponse<ApplicationLinkJob>>(
    `/jobs/${id}`,
    { ...requestConfig, signal },
  );
  return unwrap(data, '获取申请链接 Job 失败');
}

export async function pollApplicationLinkJob(
  id: number,
  onProgress: (job: ApplicationLinkJob) => void,
  options: { signal?: AbortSignal; timeoutMs?: number } = {},
) {
  return pollJobUntilTerminal({
    fetchJob: (signal) => getApplicationLinkJob(id, signal),
    onProgress,
    terminalStatuses: terminalApplicationLinkJobStatuses,
    timeoutMessage: '申请链接 Job 轮询超时，请稍后查询任务状态',
    cancelledMessage: '申请链接 Job 轮询已取消',
    failureMessage: (job) => `申请链接生成失败：${job.status}`,
    intervalMs: 400,
    ...options,
  });
}
