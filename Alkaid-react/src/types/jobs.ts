export type JobStatus =
  | 'pending'
  | 'running'
  | 'retrying'
  | 'success'
  | 'failed'
  | 'cancel_requested'
  | 'cancelled'
  | 'timed_out';

export type JobActivityStatus = JobStatus | 'submitting';

export interface JobSubmission {
  id: number;
  status: JobStatus;
  stage?: string;
  progress: number;
}

export interface JobSnapshot<TResult> extends JobSubmission {
  currentStep?: string;
  result: TResult;
  errorMessage?: string;
  errorCode?: string;
}

export interface JobLog {
  id?: number;
  jobId?: number;
  taskId?: string;
  attempt?: number;
  level: string;
  step?: string;
  stepId?: string;
  message: string;
  createdAt: string;
}

export interface JobApiCall {
  id: number;
  jobId: number;
  taskId?: string;
  attempt: number;
  step?: string;
  method: string;
  url: string;
  requestHeaders: Record<string, unknown>;
  requestBody?: unknown;
  responseStatus?: number;
  responseHeaders: Record<string, unknown>;
  responseBody?: unknown;
  responseTruncated: boolean;
  durationMs?: number;
  status: 'running' | 'success' | 'failed';
  errorType?: string;
  errorMessage?: string;
  startedAt: string;
  finishedAt?: string;
}

export interface JobDetail<TResult = Record<string, unknown>> extends JobSnapshot<TResult> {
  name: string;
  product: string;
  workflowId: string;
  stage: string;
  payload?: Record<string, unknown>;
  traceId: string;
  idempotencyKey: string;
  attemptCount: number;
  timeoutSeconds: number;
  deadlineAt?: string;
  createdAt: string;
  logs?: JobLog[];
  apiCalls?: JobApiCall[];
  apiCallCount: number;
}

export interface JobStreamStatus {
  status: JobStatus;
  progress: number;
}
