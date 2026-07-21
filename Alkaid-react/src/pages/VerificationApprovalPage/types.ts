export type VerificationOwnershipStatus = 'unclaimed' | 'claimed';
export type VerificationItemStatus = 'pending' | 'completed';
export type VerificationQuickAction = 'complete' | 'supplement' | 'submit' | 'approval-submit';
export type VerificationOperation =
  'search' | 'claim' | 'return' | 'refresh' | 'item-update' | 'action';
export type VerificationJobStatus =
  | 'submitting'
  | 'pending'
  | 'running'
  | 'retrying'
  | 'success'
  | 'failed'
  | 'cancel_requested'
  | 'cancelled'
  | 'timed_out';

export interface VerificationSearchValues {
  environment?: string;
  category?: string;
  contractNo?: string;
}

export interface VerificationSearchSubmission {
  environment: string;
  category: string;
  contractNo: string;
}

export interface VerificationApprovalConfig {
  environments: string[];
  categories: string[];
}

export interface VerificationItem {
  id: string;
  title: string;
  status: VerificationItemStatus;
}

export interface VerificationTask {
  id: string;
  contractNo: string;
  ownershipStatus: VerificationOwnershipStatus;
  taskStatus: string;
  node: string;
  tellerNo: string;
  organizationNo: string;
  productName: string;
  items: VerificationItem[];
}

export interface VerificationContextProof {
  sourceJobId: number;
  version: number;
  digest: string;
}

export interface VerificationActionDefinition {
  key: VerificationQuickAction;
  label: string;
  title: string;
  description: string;
}

export interface VerificationJobSubmission {
  id: number;
  status: VerificationJobStatus;
  stage: string;
  progress: number;
}

export interface VerificationJobDetail extends VerificationJobSubmission {
  result: {
    task?: VerificationTask | null;
    contextProof?: VerificationContextProof | null;
  };
  errorMessage?: string;
}

export interface VerificationWorkflowActivity {
  jobId?: number;
  operation: VerificationOperation;
  label: string;
  status: VerificationJobStatus;
  progress: number;
}
