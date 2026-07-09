import type { ApiResponse } from '../types';
import { apiClient } from './client';

export type BusinessAccessStatus = 'valid' | 'invalid';
export type NotificationVersionType = 'latest' | 'previous';
export type BusinessAccessOperation = 'search' | 'invalidate' | 'notifications' | 'push';
export type BusinessAccessJobStatus =
  | 'submitting'
  | 'pending'
  | 'running'
  | 'retrying'
  | 'success'
  | 'failed'
  | 'cancel_requested'
  | 'cancelled'
  | 'timed_out';

export interface BusinessAccessSearchValues {
  environment: string;
  name?: string;
  certificateNo?: string;
}

export interface BusinessAccessRecord {
  id: number;
  businessNo: string;
  customerName: string;
  certificateNo: string;
  productName: string;
  organizationName: string;
  accessResult: '通过' | '人工复核' | '拒绝';
  status: BusinessAccessStatus;
  queriedAt: string;
}

export interface BusinessAccessNotification {
  id: number;
  notificationNo: string;
  notificationType: string;
  targetSystem: string;
  latestVersion: string;
  previousVersion: string;
  updatedAt: string;
}

export interface NotificationPushResult {
  businessRecordId: number;
  notificationId: number;
  versionType: NotificationVersionType;
  version: string;
  pushedAt: string;
  message: string;
}

export interface BusinessAccessJobSubmission {
  id: number;
  operation: BusinessAccessOperation;
  status: BusinessAccessJobStatus;
  stage: string;
  progress: number;
  traceId: string;
}

export interface BusinessAccessJobDetail {
  id: number;
  workflowId: string;
  status: BusinessAccessJobStatus;
  stage: string;
  progress: number;
  result: Record<string, unknown>;
  errorMessage?: string;
}

export interface BusinessAccessWorkflowActivity {
  jobId?: number;
  operation: BusinessAccessOperation;
  label: string;
  status: BusinessAccessJobStatus;
  progress: number;
}

const terminalStatuses = new Set<BusinessAccessJobStatus>([
  'success',
  'failed',
  'cancelled',
  'timed_out',
]);

function unwrap<T>(response: ApiResponse<T>, fallbackMessage: string) {
  if (!response.ok) {
    throw new Error(response.message || fallbackMessage);
  }
  return response.data;
}

function workflowHeaders() {
  const requestId = crypto.randomUUID();
  return {
    'X-Idempotency-Key': requestId,
    'X-Trace-ID': requestId.split('-').join(''),
  };
}

function workflowRequestConfig() {
  return {
    headers: workflowHeaders(),
    showGlobalProgress: false,
    useResponseDelay: false,
  };
}

const pollingRequestConfig = {
  showGlobalProgress: false,
  useResponseDelay: false,
};

export async function searchBusinessAccess(values: BusinessAccessSearchValues) {
  const { data } = await apiClient.post<ApiResponse<BusinessAccessJobSubmission>>(
    '/product-data/business-access/search',
    values,
    workflowRequestConfig(),
  );
  return unwrap(data, '提交业务准入查询失败');
}

export async function invalidateBusinessAccess(recordId: number) {
  const { data } = await apiClient.post<ApiResponse<BusinessAccessJobSubmission>>(
    `/product-data/business-access/${recordId}/invalidate`,
    undefined,
    workflowRequestConfig(),
  );
  return unwrap(data, '提交业务准入记录失效失败');
}

export async function listBusinessAccessNotifications(recordId: number) {
  const { data } = await apiClient.post<ApiResponse<BusinessAccessJobSubmission>>(
    `/product-data/business-access/${recordId}/notifications/query`,
    undefined,
    workflowRequestConfig(),
  );
  return unwrap(data, '提交通知记录查询失败');
}

export async function pushBusinessAccessNotification(
  recordId: number,
  notificationId: number,
  versionType: NotificationVersionType,
) {
  const action = versionType === 'latest' ? 'push-new' : 'push-old';
  const { data } = await apiClient.post<ApiResponse<BusinessAccessJobSubmission>>(
    `/product-data/business-access/${recordId}/notifications/${notificationId}/${action}`,
    undefined,
    workflowRequestConfig(),
  );
  return unwrap(data, '提交通知推送失败');
}

export async function getBusinessAccessJob(id: number) {
  const { data } = await apiClient.get<ApiResponse<BusinessAccessJobDetail>>(
    `/jobs/${id}`,
    pollingRequestConfig,
  );
  return unwrap(data, '获取业务准入 Job 进度失败');
}

export async function pollBusinessAccessJob(
  id: number,
  onProgress: (detail: BusinessAccessJobDetail) => void,
) {
  while (true) {
    const detail = await getBusinessAccessJob(id);
    onProgress(detail);
    if (detail.status === 'success') {
      return detail;
    }
    if (terminalStatuses.has(detail.status)) {
      throw new Error(detail.errorMessage || `业务准入 Job 执行失败：${detail.status}`);
    }
    await new Promise((resolve) => window.setTimeout(resolve, 500));
  }
}
