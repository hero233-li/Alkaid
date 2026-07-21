import type { ApiResponse } from '../../../types';
import { apiClient } from '../../../api/client';
import { createWorkflowHeaders } from '../../../utils/requestId';
import { pollJobUntilTerminal } from '../../../utils/jobPolling';
import type {
  VerificationApprovalConfig,
  VerificationContextProof,
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

export async function claimVerificationTask(
  task: VerificationTask,
  contextProof: VerificationContextProof,
) {
  const { data } = await apiClient.post<ApiResponse<VerificationJobSubmission>>(
    `/product-data/verification-approval/${encodeURIComponent(task.id)}/claim`,
    { context: task, contextProof },
    workflowRequestConfig(),
  );
  return unwrap(data, '领取核实审批任务失败');
}

export async function returnVerificationTask(
  task: VerificationTask,
  contextProof: VerificationContextProof,
) {
  const { data } = await apiClient.post<ApiResponse<VerificationJobSubmission>>(
    `/product-data/verification-approval/${encodeURIComponent(task.id)}/return`,
    { context: task, contextProof },
    workflowRequestConfig(),
  );
  return unwrap(data, '退回核实审批任务失败');
}

export async function refreshVerificationTask(
  task: VerificationTask,
  contextProof: VerificationContextProof,
) {
  const { data } = await apiClient.post<ApiResponse<VerificationJobSubmission>>(
    `/product-data/verification-approval/${encodeURIComponent(task.id)}/refresh`,
    { context: task, contextProof },
    workflowRequestConfig(),
  );
  return unwrap(data, '刷新核实审批任务失败');
}

export async function updateVerificationItem(
  task: VerificationTask,
  contextProof: VerificationContextProof,
  itemId: string,
  status: VerificationItemStatus,
) {
  const { data } = await apiClient.post<ApiResponse<VerificationJobSubmission>>(
    `/product-data/verification-approval/${encodeURIComponent(task.id)}/items/${encodeURIComponent(itemId)}`,
    { status, context: task, contextProof },
    workflowRequestConfig(),
  );
  return unwrap(data, '更新核实项失败');
}

export async function submitVerificationAction(
  task: VerificationTask,
  contextProof: VerificationContextProof,
  action: VerificationQuickAction,
) {
  const { data } = await apiClient.post<ApiResponse<VerificationJobSubmission>>(
    `/product-data/verification-approval/${encodeURIComponent(task.id)}/actions/${action}`,
    { action, context: task, contextProof },
    workflowRequestConfig(),
  );
  return unwrap(data, '提交核实审批操作失败');
}

export async function getVerificationJob(id: number, signal?: AbortSignal) {
  const { data } = await apiClient.get<ApiResponse<VerificationJobDetail>>(`/jobs/${id}`, {
    ...requestConfig,
    signal,
  });
  return unwrap(data, '获取核实审批 Job 进度失败');
}

const terminalStatuses = new Set(['success', 'failed', 'cancelled', 'timed_out']);

export async function pollVerificationJob(
  id: number,
  onProgress: (detail: VerificationJobDetail) => void,
  options: { signal?: AbortSignal; timeoutMs?: number } = {},
) {
  return pollJobUntilTerminal({
    fetchJob: (signal) => getVerificationJob(id, signal),
    onProgress,
    terminalStatuses,
    timeoutMessage: '核实审批 Job 轮询超时，请稍后查询任务状态',
    cancelledMessage: '核实审批 Job 轮询已取消',
    failureMessage: (detail) => `核实审批 Job 执行失败：${detail.status}`,
    ...options,
  });
}
