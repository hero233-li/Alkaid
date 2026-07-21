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

export interface JobDetail<TResult = Record<string, unknown>> extends JobSnapshot<TResult> {
  name: string;
  workflowId: string;
  stage: string;
  payload?: Record<string, unknown>;
  traceId: string;
  idempotencyKey: string;
  attemptCount: number;
  timeoutSeconds: number;
  deadlineAt?: string;
  createdAt: string;
}

export interface JobStreamStatus {
  status: JobStatus;
  progress: number;
}
