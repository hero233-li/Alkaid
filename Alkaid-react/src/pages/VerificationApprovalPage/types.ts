export type VerificationOwnershipStatus = 'unclaimed' | 'claimed';
export type VerificationItemStatus = 'pending' | 'completed';
export type VerificationQuickAction = 'complete' | 'supplement' | 'submit' | 'approval-submit';

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

export interface VerificationActionDefinition {
  key: VerificationQuickAction;
  label: string;
  title: string;
  description: string;
}
