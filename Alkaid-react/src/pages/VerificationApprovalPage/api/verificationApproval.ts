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

export async function claimVerificationTask(taskId: string) {
  const { data } = await apiClient.post<ApiResponse<VerificationTask>>(
    `/product-data/verification-approval/${encodeURIComponent(taskId)}/claim`,
    undefined,
    tracedRequestConfig(),
  );
  return unwrap(data, '领取核实审批任务失败');
}

export async function returnVerificationTask(taskId: string) {
  const { data } = await apiClient.post<ApiResponse<VerificationTask>>(
    `/product-data/verification-approval/${encodeURIComponent(taskId)}/return`,
    undefined,
    tracedRequestConfig(),
  );
  return unwrap(data, '退回核实审批任务失败');
}

export async function updateVerificationItem(
  taskId: string,
  itemId: string,
  status: VerificationItemStatus,
) {
  const { data } = await apiClient.post<ApiResponse<VerificationTask>>(
    `/product-data/verification-approval/${encodeURIComponent(taskId)}/items/${encodeURIComponent(itemId)}`,
    { status },
    tracedRequestConfig(),
  );
  return unwrap(data, '更新核实项失败');
}

export async function submitVerificationAction(
  taskId: string,
  action: VerificationQuickAction,
) {
  const { data } = await apiClient.post<ApiResponse<VerificationTask>>(
    `/product-data/verification-approval/${encodeURIComponent(taskId)}/actions/${action}`,
    undefined,
    tracedRequestConfig(),
  );
  return unwrap(data, '提交核实审批操作失败');
}
