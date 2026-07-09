export interface CardRecord { environment:string; customerNo:string; certificateNo:string; cardNo:string; balance:number; status:string }
export interface CardSearchValues { environment:string; customerNo:string }
export type CardAction='deposit'|'withdraw'|'transfer'|'card-pin-reset'|'login-password-reset';
export interface CardActionValues { environment:string;customerNo:string;certificateNo:string;cardNo:string;tellerNo:string;amount?:number;targetCard?:string }
export interface CardApiResponse<T>{ok:boolean;data:T;message?:string}
export type CardJobStatus='submitting'|'pending'|'running'|'retrying'|'success'|'failed'|'cancelled'|'timed_out';
export interface CardJob{id:number;status:CardJobStatus;progress:number;currentStep?:string;result:Record<string,unknown>;errorMessage?:string}
export interface CardActivity{jobId?:number;label:string;status:CardJobStatus;progress:number;currentStep?:string}
