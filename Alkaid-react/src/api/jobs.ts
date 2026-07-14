import type { ApiResponse } from '../types';
import type { JobDetail, JobLog, JobStreamStatus } from '../types/jobs';
import { apiClient } from './client';

const terminalJobStatuses = new Set<JobStreamStatus['status']>([
  'success',
  'failed',
  'cancelled',
  'timed_out',
]);

export interface JobLogStreamResult {
  lastLogId: number;
  terminalStatusReceived: boolean;
}

export async function getJobDetail(id: number) {
  const { data } = await apiClient.get<ApiResponse<JobDetail>>(
    `/jobs/${id}`,
    { params: { includePayload: true } },
  );
  if (!data.ok) {
    throw new Error(data.message || '获取 Job 详情失败');
  }
  return data.data;
}

export async function retryJob(id: number) {
  const { data } = await apiClient.post<ApiResponse<JobDetail>>(`/jobs/${id}/retry`);
  if (!data.ok) {
    throw new Error(data.message || 'Job 重试失败');
  }
  return data.data;
}

export async function cancelJob(id: number) {
  const { data } = await apiClient.post<ApiResponse<JobDetail>>(`/jobs/${id}/cancel`);
  if (!data.ok) {
    throw new Error(data.message || 'Job 取消失败');
  }
  return data.data;
}

export async function streamJobLogs(
  id: number,
  afterId: number,
  handlers: {
    onLog: (log: JobLog) => void;
    onStatus: (status: JobStreamStatus) => void;
  },
  signal: AbortSignal,
) {
  const response = await fetch(`/api/jobs/${id}/logs/stream?afterId=${afterId}`, {
    headers: { Accept: 'text/event-stream' },
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`实时日志连接失败（${response.status}）`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let lastLogId = afterId;
  let terminalStatusReceived = false;
  while (!signal.aborted) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true }).split('\r\n').join('\n');
    let boundary = buffer.indexOf('\n\n');
    while (boundary >= 0) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const lines = block.split('\n');
      const eventName = lines.find((line) => line.startsWith('event:'))?.slice(6).trim() || 'message';
      const dataText = lines
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trim())
        .join('\n');
      if (dataText) {
        const eventData = JSON.parse(dataText) as JobLog | JobStreamStatus;
        if (eventName === 'log') {
          const log = eventData as JobLog;
          lastLogId = Math.max(lastLogId, log.id || 0);
          handlers.onLog(log);
        } else if (eventName === 'status') {
          const status = eventData as JobStreamStatus;
          terminalStatusReceived = terminalJobStatuses.has(status.status);
          handlers.onStatus(status);
        }
      }
      boundary = buffer.indexOf('\n\n');
    }
  }
  return { lastLogId, terminalStatusReceived } satisfies JobLogStreamResult;
}
