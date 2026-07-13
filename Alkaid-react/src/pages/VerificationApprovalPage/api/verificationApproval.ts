import type { ApiResponse } from '../../../types';
import { apiClient } from '../../../api/client';
import type {
  VerificationApprovalConfig,
  VerificationItemStatus,
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

function tracedRequestConfig() {
  const traceId = crypto.randomUUID().split('-').join('');
  return { ...requestConfig, headers: { 'X-Trace-ID': traceId } };
}

export async function getVerificationApprovalConfig() {
  const { data } = await apiClient.get<ApiResponse<VerificationApprovalConfig>>(
    '/product-data/verification-approval/config',
    requestConfig,
  );
  return unwrap(data, '获取核实审批配置失败');
}

export async function searchVerificationTask(submission: VerificationSearchSubmission) {
  const { data } = await apiClient.post<ApiResponse<VerificationTask | null>>(
    '/product-data/verification-approval/search',
    submission,
    tracedRequestConfig(),
  );
  return unwrap(data, '查询核实审批任务失败');
}

export async function claimVerificationTask(task: VerificationTask) {
  const { data } = await apiClient.post<ApiResponse<VerificationTask>>(
    `/product-data/verification-approval/${encodeURIComponent(task.id)}/claim`,
    { context: task },
    tracedRequestConfig(),
  );
  return unwrap(data, '领取核实审批任务失败');
}

export async function returnVerificationTask(task: VerificationTask) {
  const { data } = await apiClient.post<ApiResponse<VerificationTask>>(
    `/product-data/verification-approval/${encodeURIComponent(task.id)}/return`,
    { context: task },
    tracedRequestConfig(),
  );
  return unwrap(data, '退回核实审批任务失败');
}

export async function updateVerificationItem(
  task: VerificationTask,
  itemId: string,
  status: VerificationItemStatus,
) {
  const { data } = await apiClient.post<ApiResponse<VerificationTask>>(
    `/product-data/verification-approval/${encodeURIComponent(task.id)}/items/${encodeURIComponent(itemId)}`,
    { status, context: task },
    tracedRequestConfig(),
  );
  return unwrap(data, '更新核实项失败');
}

export async function submitVerificationAction(
  task: VerificationTask,
  action: VerificationQuickAction,
) {
  const { data } = await apiClient.post<ApiResponse<VerificationTask>>(
    `/product-data/verification-approval/${encodeURIComponent(task.id)}/actions/${action}`,
    { action, context: task },
    tracedRequestConfig(),
  );
  return unwrap(data, '提交核实审批操作失败');
}
