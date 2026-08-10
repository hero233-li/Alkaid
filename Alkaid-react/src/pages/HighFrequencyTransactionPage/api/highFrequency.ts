import { highFrequencyClient } from './client';
import { pollJobUntilTerminal } from '../../../utils/jobPolling';
import { createWorkflowHeaders } from '../../../utils/requestId';
import type {
  ApiResponse,
  HighFrequencySearchValues,
  HighFrequencyQueryPayload,
  JobStatus,
  JobSubmission,
  WorkflowJob,
} from '../types';
const requestConfig = { showGlobalProgress: false, useResponseDelay: false };
const terminal = new Set<JobStatus>([
  'success',
  'failed',
  'cancel_requested',
  'cancelled',
  'timed_out',
]);
function unwrap<T>(response: ApiResponse<T>, fallback: string) {
  if (!response.ok) throw new Error(response.message || fallback);
  return response.data;
}
function workflowConfig() {
  return {
    ...requestConfig,
    headers: createWorkflowHeaders(),
  };
}
export async function submitHighFrequencyQuery(values: HighFrequencySearchValues) {
  const payload: HighFrequencyQueryPayload = values.useDefaultParams
    ? { environment: values.environment }
    : {
        environment: values.environment,
        cardNo: values.cardNo,
        queryStartDate: values.startDate?.format('YYYY-MM-DD'),
        queryEndDate: values.endDate?.format('YYYY-MM-DD'),
      };
  return unwrap(
    (
      await highFrequencyClient.post<ApiResponse<JobSubmission>>(
        '/product-data/tools/post-loan/high-frequency/query',
        payload,
        workflowConfig(),
      )
    ).data,
    '查询提交失败',
  );
}
export async function pollHighFrequencyJob(
  id: number,
  onProgress: (job: WorkflowJob) => void,
  options: { signal?: AbortSignal; timeoutMs?: number } = {},
) {
  return pollJobUntilTerminal({
    fetchJob: async (signal) =>
      unwrap(
        (
          await highFrequencyClient.get<ApiResponse<WorkflowJob>>(`/jobs/${id}`, {
            ...requestConfig,
            signal,
          })
        ).data,
        '获取高频交易 Job 失败',
      ),
    onProgress,
    terminalStatuses: terminal,
    timeoutMessage: '高频交易 Job 轮询超时，请稍后查询任务状态',
    cancelledMessage: '高频交易 Job 轮询已取消',
    failureMessage: (job) => `高频交易 Job 执行失败：${job.status}`,
    intervalMs: 400,
    ...options,
  });
}
