import type { Dayjs } from 'dayjs';

export interface ApplicationDataFormValues {
  environment: string;
  currentDate: Dayjs;
  age: number;
  birthDate: string;
  gender: '男' | '女';
  tellerNo: string;
  companyType: '91' | '92';
  count: number;
}

export interface ApplicationDataRecord {
  id:number; environment:string; customerNo:string; customerName:string;
  certificateType:string; certificateNo:string; cardNo:string; phone:string;
  companyName:string; companyCreditCode:string; organizationCode:string;
}

export interface ApplicationDataApiResponse<T>{ok:boolean;data:T;message?:string}
export type ApplicationDataJobStatus='submitting'|'pending'|'running'|'retrying'|'success'|'failed'|'cancelled'|'timed_out';
export interface ApplicationDataJob{id:number;status:ApplicationDataJobStatus;progress:number;result:Record<string,unknown>;errorMessage?:string}
export interface ApplicationDataActivity{jobId?:number;status:ApplicationDataJobStatus;progress:number;label:string}
