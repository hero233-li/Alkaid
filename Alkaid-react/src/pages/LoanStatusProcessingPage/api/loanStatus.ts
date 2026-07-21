import { apiClient } from '../../../api/client';
import { createWorkflowHeaders } from '../../../utils/requestId';
import { pollJobUntilTerminal } from '../../../utils/jobPolling';
import type {
  LoanAction,
  LoanActionValues,
  LoanApiResponse,
  LoanJob,
  LoanJobStatus,
  LoanSearchValues,
} from '../types';

interface Submission {
  id: number;
  status: LoanJobStatus;
  progress: number;
}
const requestConfig = { showGlobalProgress: false, useResponseDelay: false };
const terminal = new Set<LoanJobStatus>(['success', 'failed', 'cancelled', 'timed_out']);

function unwrap<T>(value: LoanApiResponse<T>, fallback: string) {
  if (!value.ok) throw new Error(value.message || fallback);
  return value.data;
}

function workflowConfig() {
  return { ...requestConfig, headers: createWorkflowHeaders() };
}

export async function submitLoanSearch(values: LoanSearchValues) {
  const { data } = await apiClient.post<LoanApiResponse<Submission>>(
    '/product-data/tools/loans/search',
    values,
    workflowConfig(),
  );
  return unwrap(data, '查询提交失败');
}

export async function submitLoanAction(
  contractNo: string,
  action: LoanAction,
  values: LoanActionValues,
) {
  const { data } = await apiClient.post<LoanApiResponse<Submission>>(
    `/product-data/tools/loans/${encodeURIComponent(contractNo)}/actions/${action}`,
    values,
    workflowConfig(),
  );
  return unwrap(data, '操作提交失败');
}

export class LoanJobError extends Error {
  constructor(
    message: string,
    public job: LoanJob,
  ) {
    super(message);
  }
}

export async function pollLoanJob(
  id: number,
  onProgress: (job: LoanJob) => void,
  options: { signal?: AbortSignal; timeoutMs?: number } = {},
) {
  return pollJobUntilTerminal({
    fetchJob: async (signal) => {
      const { data } = await apiClient.get<LoanApiResponse<LoanJob>>(`/jobs/${id}`, {
        ...requestConfig,
        signal,
      });
      return unwrap(data, '获取 Job 失败');
    },
    onProgress,
    terminalStatuses: terminal,
    timeoutMessage: '贷款状态 Job 轮询超时，请稍后查询任务状态',
    cancelledMessage: '贷款状态 Job 轮询已取消',
    failureMessage: (job) => `Job ${job.status}`,
    failureError: (job, message) => new LoanJobError(message, job),
    intervalMs: 400,
    ...options,
  });
}
