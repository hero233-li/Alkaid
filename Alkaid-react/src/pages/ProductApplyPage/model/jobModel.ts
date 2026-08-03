import type { JobDetail, JobStatus } from '../../../types/jobs';
import type { ProductApplicationResult } from './types';

export const terminalStatuses = new Set<JobStatus>(['success', 'failed', 'cancelled', 'timed_out']);
export const activeStatuses = new Set<JobStatus>([
  'pending',
  'running',
  'retrying',
  'cancel_requested',
]);

export const statusMeta: Record<JobStatus, { label: string; color: string }> = {
  pending: { label: '等待执行', color: 'default' },
  running: { label: '执行中', color: 'processing' },
  retrying: { label: '等待重试', color: 'warning' },
  success: { label: '已完成', color: 'success' },
  failed: { label: '失败', color: 'error' },
  cancel_requested: { label: '取消中', color: 'warning' },
  cancelled: { label: '已取消', color: 'default' },
  timed_out: { label: '已超时', color: 'error' },
};

export function mergeJobDetail(
  result: ProductApplicationResult,
  detail: JobDetail,
): ProductApplicationResult {
  return {
    ...result,
    name: detail.name || result.name,
    status: detail.status,
    stage: detail.stage,
    progress: detail.progress,
    payload: detail.payload ?? result.payload,
    errorMessage: detail.errorMessage,
    errorCode: detail.errorCode,
    traceId: detail.traceId,
    idempotencyKey: detail.idempotencyKey,
    attemptCount: detail.attemptCount,
    deadlineAt: detail.deadlineAt,
  };
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'medium' }).format(
    new Date(value),
  );
}
