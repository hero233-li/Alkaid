import type {
  BusinessAccessJobDetail,
  BusinessAccessJobStatus,
  BusinessAccessOperation,
  BusinessAccessRecord,
  BusinessAccessWorkflowActivity,
  NotificationPushResult,
} from '../types';

export const terminalBusinessAccessJobStatuses = new Set<BusinessAccessJobStatus>([
  'success',
  'failed',
  'cancelled',
  'timed_out',
]);

export const businessAccessJobStatusLabels: Record<BusinessAccessJobStatus, string> = {
  submitting: '正在提交',
  pending: '等待执行',
  running: '执行中',
  retrying: '重试中',
  success: '已完成',
  failed: '执行失败',
  cancel_requested: '取消中',
  cancelled: '已取消',
  timed_out: '已超时',
};

export function buildBusinessAccessWorkflowActivity(
  operation: BusinessAccessOperation,
  label: string,
  status: BusinessAccessJobStatus,
  progress: number,
  jobId?: number,
): BusinessAccessWorkflowActivity {
  return { operation, label, status, progress, jobId };
}

export function getBusinessAccessVisibleProgress(activity: BusinessAccessWorkflowActivity) {
  if (activity.progress > 0) {
    return activity.progress;
  }
  if (activity.status === 'submitting') {
    return 5;
  }
  if (activity.status === 'pending') {
    return 10;
  }
  return 15;
}

function requiredResultValue<T>(
  detail: BusinessAccessJobDetail,
  key: keyof BusinessAccessJobDetail['result'],
  message: string,
) {
  const value = detail.result[key];
  if (value === undefined || value === null) {
    throw new Error(message);
  }
  return value as T;
}

export function extractBusinessAccessRecords(detail: BusinessAccessJobDetail) {
  const records = detail.result.records;
  if (records === undefined || records === null) {
    return [];
  }
  if (!Array.isArray(records)) {
    throw new Error('查询结果 records 格式不正确');
  }
  return records;
}

export function extractBusinessAccessRecord(detail: BusinessAccessJobDetail) {
  return requiredResultValue<BusinessAccessRecord>(detail, 'record', '失效操作结果缺少 record');
}

export function extractBusinessAccessNotifications(detail: BusinessAccessJobDetail) {
  const notifications = detail.result.notifications;
  if (notifications === undefined || notifications === null) {
    return [];
  }
  if (!Array.isArray(notifications)) {
    throw new Error('通知查询结果格式不正确');
  }
  return notifications;
}

export function extractNotificationPushResult(detail: BusinessAccessJobDetail) {
  return requiredResultValue<NotificationPushResult>(
    detail,
    'pushResult',
    '通知推送结果缺少 pushResult',
  );
}
