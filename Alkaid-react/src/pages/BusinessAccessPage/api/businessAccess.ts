import type { ApiResponse } from '../../../types';
import { apiClient } from '../../../api/client';
import { terminalBusinessAccessJobStatuses } from '../model/jobModel';
import type {
  BusinessAccessJobDetail,
  BusinessAccessJobSubmission,
  BusinessAccessConfig,
  BusinessAccessSearchSubmission,
  NotificationVersionType,
} from '../types';

const pollingRequestConfig = {
  showGlobalProgress: false,
  useResponseDelay: false,
};

function unwrap<T>(response: ApiResponse<T>, fallbackMessage: string) {
  if (!response.ok) {
    throw new Error(response.message || fallbackMessage);
  }
  return response.data;
}

export async function getBusinessAccessConfig() {
  const { data } = await apiClient.get<ApiResponse<BusinessAccessConfig>>(
    '/product-data/business-access/config',
    pollingRequestConfig,
  );
  return unwrap(data, '获取业务准入配置失败');
}

function workflowRequestConfig() {
  const requestId = crypto.randomUUID();
  return {
    headers: {
      'X-Idempotency-Key': requestId,
      'X-Trace-ID': requestId.split('-').join(''),
    },
    showGlobalProgress: false,
    useResponseDelay: false,
  };
}

export async function searchBusinessAccess(values: BusinessAccessSearchSubmission) {
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
    if (terminalBusinessAccessJobStatuses.has(detail.status)) {
      throw new Error(detail.errorMessage || `业务准入 Job 执行失败：${detail.status}`);
    }
    await new Promise((resolve) => window.setTimeout(resolve, 500));
  }
}
