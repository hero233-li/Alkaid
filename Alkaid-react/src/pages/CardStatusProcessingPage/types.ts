import type { JobActivityStatus, JobSnapshot } from '../../types/jobs';

export interface CardRecord {
  environment: string;
  customerNo: string;
  certificateNo: string;
  cardNo: string;
  balance: number;
  status: string;
}
export interface CardSearchValues {
  environment: string;
  customerNo: string;
}
export type CardAction =
  'deposit' | 'withdraw' | 'transfer' | 'card-pin-reset' | 'login-password-reset';
export interface CardActionValues {
  environment: string;
  customerNo: string;
  certificateNo: string;
  cardNo: string;
  tellerNo: string;
  amount?: number;
  targetCard?: string;
}
export interface CardApiResponse<T> {
  ok: boolean;
  data: T;
  message?: string;
}
export type CardJobStatus = JobActivityStatus;
export interface CardJobResult {
  cards?: CardRecord[];
  actionResult?: { card: CardRecord; message: string; password?: string };
}
export type CardJob = JobSnapshot<CardJobResult>;
export interface CardActivity {
  jobId?: number;
  label: string;
  status: CardJobStatus;
  progress: number;
  currentStep?: string;
}
