import { useState } from 'react';
import { message } from 'antd';
import { pollHighFrequencyJob, submitHighFrequencyQuery } from '../api/highFrequency';
import type { DynamicQueryResult, HighFrequencySearchValues, WorkflowActivity } from '../types';
export function useHighFrequencyTransaction() {
  const [activity, setActivity] = useState<WorkflowActivity | null>(null);
  const [result, setResult] = useState<DynamicQueryResult | null>(null);
  const query = async (values: HighFrequencySearchValues) => {
    setResult(null);
    setActivity({ label: '正在提交高频交易查询', status: 'submitting', progress: 0 });
    try {
      const submission = await submitHighFrequencyQuery(values);
      const job = await pollHighFrequencyJob(submission.id, (current) =>
        setActivity({
          jobId: submission.id,
          label: '正在执行高频交易查询',
          status: current.status,
          progress: current.progress,
          currentStep: current.currentStep,
        }),
      );
      const raw = job.result.queryResult;
      if (!raw) throw new Error('高频交易 Job 结果缺少 queryResult');
      setResult({
        ...raw,
        functionCode: raw.functionCode || 'risk050009',
        functionName: raw.functionName || '高频交易',
        head: raw.head ?? raw.columns ?? [],
        body: raw.body ?? raw.rows ?? [],
      });
    } catch (error) {
      message.error(error instanceof Error ? error.message : '查询失败');
    } finally {
      setActivity(null);
    }
  };
  return { activity, result, busy: Boolean(activity), query, closeResult: () => setResult(null) };
}
