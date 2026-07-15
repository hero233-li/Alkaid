import type {
  ApplicationLinkActivity,
  ApplicationLinkJob,
  ApplicationLinkJobStatus,
  ApplicationLinkResult,
} from './types';

export const applicationLinkActivityLabel = '正在生成申请链接';

export const terminalApplicationLinkJobStatuses = new Set<ApplicationLinkJobStatus>([
  'success',
  'failed',
  'cancelled',
  'timed_out',
]);

export function buildApplicationLinkActivity(
  status: ApplicationLinkJobStatus,
  progress: number,
  jobId?: number,
): ApplicationLinkActivity {
  return {
    jobId,
    label: applicationLinkActivityLabel,
    status,
    progress,
  };
}

export function extractApplicationLinkResult(job: ApplicationLinkJob): ApplicationLinkResult {
  const links = job.result.links;
  if (!links || typeof links !== 'object') {
    throw new Error('申请链接生成结果缺少链接数据');
  }

  const result = links as Partial<ApplicationLinkResult>;
  if (typeof result.internalUrl !== 'string' || typeof result.externalUrl !== 'string') {
    throw new Error('申请链接生成结果格式不正确');
  }

  return {
    internalUrl: result.internalUrl,
    externalUrl: result.externalUrl,
    generatedAt: typeof result.generatedAt === 'string' ? result.generatedAt : '',
  };
}
