import{highFrequencyClient}from'./client';
import type{ApiResponse,HighFrequencySearchValues,HighFrequencyQueryPayload,JobStatus,JobSubmission,WorkflowJob}from'../types';
const requestConfig={showGlobalProgress:false,useResponseDelay:false};
const terminal=new Set<JobStatus>(['success','failed','cancelled','timed_out']);
function unwrap<T>(response:ApiResponse<T>,fallback:string){if(!response.ok)throw new Error(response.message||fallback);return response.data}
function workflowConfig(){const id=crypto.randomUUID();return{...requestConfig,headers:{'X-Idempotency-Key':id,'X-Trace-ID':id.split('-').join('')}}}
export async function submitHighFrequencyQuery(values:HighFrequencySearchValues){const payload:HighFrequencyQueryPayload=values.useDefaultParams?{environment:values.environment}:{environment:values.environment,cardNo:values.cardNo,queryStartDate:values.startDate?.format('YYYY-MM-DD'),queryEndDate:values.endDate?.format('YYYY-MM-DD')};return unwrap((await highFrequencyClient.post<ApiResponse<JobSubmission>>('/product-data/tools/post-loan/high-frequency/query',payload,workflowConfig())).data,'查询提交失败')}
export async function pollHighFrequencyJob(id:number,onProgress:(job:WorkflowJob)=>void){while(true){const job=unwrap((await highFrequencyClient.get<ApiResponse<WorkflowJob>>(`/jobs/${id}`,requestConfig)).data,'获取 Workflow Job 失败');onProgress(job);if(job.status==='success')return job;if(terminal.has(job.status))throw new Error(job.errorMessage||`Workflow Job ${job.status}`);await new Promise(resolve=>window.setTimeout(resolve,400))}}
