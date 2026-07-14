import type { ApiResponse } from '../../../types';
import { apiClient } from '../../../api/client';
import { createWorkflowHeaders } from '../../../utils/requestId';
import type {
  VerificationApprovalConfig,
  VerificationItemStatus,
  VerificationJobDetail,
  VerificationJobSubmission,
  VerificationQuickAction,
  VerificationSearchSubmission,
  VerificationTask,
} from '../types';

const requestConfig = {
  showGlobalProgress: false,
  useResponseDelay: false,
};

function unwrap<T>(response: ApiResponse<T>, fallback: string) {
  if (!response.ok) {
    throw new Error(response.message || fallback);
  }
  return response.data;
}

function workflowRequestConfig() {
  return {
    ...requestConfig,
    headers: createWorkflowHeaders(),
  };
}

export async function getVerificationApprovalConfig() {
  const { data } = await apiClient.get<ApiResponse<VerificationApprovalConfig>>(
    '/product-data/verification-approval/config',
    requestConfig,
  );
  return unwrap(data, '获取核实审批配置失败');
}

export async function searchVerificationTask(submission: VerificationSearchSubmission) {
  const { data } = await apiClient.post<ApiResponse<VerificationJobSubmission>>(
    '/product-data/verification-approval/search',
    submission,
    workflowRequestConfig(),
  );
  return unwrap(data, '查询核实审批任务失败');
}

export async function claimVerificationTask(task: VerificationTask) {
  const { data } = await apiClient.post<ApiResponse<VerificationJobSubmission>>(
    `/product-data/verification-approval/${encodeURIComponent(task.id)}/claim`,
    { context: task },
    workflowRequestConfig(),
  );
  return unwrap(data, '领取核实审批任务失败');
}

export async function returnVerificationTask(task: VerificationTask) {
  const { data } = await apiClient.post<ApiResponse<VerificationJobSubmission>>(
    `/product-data/verification-approval/${encodeURIComponent(task.id)}/return`,
    { context: task },
    workflowRequestConfig(),
  );
  return unwrap(data, '退回核实审批任务失败');
}

export async function refreshVerificationTask(task: VerificationTask) {
  const { data } = await apiClient.post<ApiResponse<VerificationJobSubmission>>(
    `/product-data/verification-approval/${encodeURIComponent(task.id)}/refresh`,
    { context: task },
    workflowRequestConfig(),
  );
  return unwrap(data, '刷新核实审批任务失败');
}

export async function updateVerificationItem(
  task: VerificationTask,
  itemId: string,
  status: VerificationItemStatus,
) {
  const { data } = await apiClient.post<ApiResponse<VerificationJobSubmission>>(
    `/product-data/verification-approval/${encodeURIComponent(task.id)}/items/${encodeURIComponent(itemId)}`,
    { status, context: task },
    workflowRequestConfig(),
  );
  return unwrap(data, '更新核实项失败');
}

export async function submitVerificationAction(
  task: VerificationTask,
  action: VerificationQuickAction,
) {
  const { data } = await apiClient.post<ApiResponse<VerificationJobSubmission>>(
    `/product-data/verification-approval/${encodeURIComponent(task.id)}/actions/${action}`,
    { action, context: task },
    workflowRequestConfig(),
  );
  return unwrap(data, '提交核实审批操作失败');
}

export async function getVerificationJob(id: number, signal?: AbortSignal) {
  const { data } = await apiClient.get<ApiResponse<VerificationJobDetail>>(
    `/jobs/${id}`,
    { ...requestConfig, signal },
  );
  return unwrap(data, '获取核实审批 Job 进度失败');
}

const terminalStatuses = new Set(['success', 'failed', 'cancelled', 'timed_out']);

export async function pollVerificationJob(
  id: number,
  onProgress: (detail: VerificationJobDetail) => void,
  options: { signal?: AbortSignal; timeoutMs?: number } = {},
) {
  const deadline = Date.now() + (options.timeoutMs ?? 150_000);
  while (true) {
    if (options.signal?.aborted) throw abortError();
    if (Date.now() >= deadline) throw new Error('核实审批 Job 轮询超时，请稍后查询任务状态');
    const detail = await getVerificationJob(id, options.signal);
    onProgress(detail);
    if (detail.status === 'success') return detail;
    if (terminalStatuses.has(detail.status)) {
      throw new Error(detail.errorMessage || `核实审批 Job 执行失败：${detail.status}`);
    }
    await waitForNextPoll(500, options.signal);
  }
}

function abortError() {
  const error = new Error('核实审批 Job 轮询已取消');
  error.name = 'AbortError';
  return error;
}

function waitForNextPoll(delayMs: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(abortError());
      return;
    }
    const onAbort = () => {
      window.clearTimeout(timer);
      reject(abortError());
    };
    const timer = window.setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, delayMs);
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}
