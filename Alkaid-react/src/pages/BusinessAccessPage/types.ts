export type BusinessAccessStatus = 'valid' | 'invalid';
export type NotificationVersionType = 'latest' | 'previous';
export type BusinessAccessOperation = 'search' | 'invalidate' | 'notifications' | 'push';
export type BusinessAccessJobStatus = JobActivityStatus;

export interface BusinessAccessSearchValues {
  environment?: string;
  name?: string;
  certificateNo?: string;
}

export interface BusinessAccessSearchSubmission {
  environment: string;
  name?: string;
  certificateNo?: string;
}

export interface BusinessAccessConfig {
  environments: string[];
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

export interface BusinessAccessJobResult {
  records?: BusinessAccessRecord[];
  record?: BusinessAccessRecord;
  notifications?: BusinessAccessNotification[];
  pushResult?: NotificationPushResult;
}

export interface BusinessAccessJobSubmission extends JobSubmission {
  operation: BusinessAccessOperation;
  stage: string;
  traceId: string;
}

export interface BusinessAccessJobDetail extends JobSnapshot<BusinessAccessJobResult> {
  workflowId: string;
  stage: string;
}

export interface BusinessAccessWorkflowActivity {
  jobId?: number;
  operation: BusinessAccessOperation;
  label: string;
  status: BusinessAccessJobStatus;
  progress: number;
}
import type { JobActivityStatus, JobSnapshot, JobSubmission } from '../../types/jobs';
