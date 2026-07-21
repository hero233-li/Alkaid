import { useCallback, useState } from 'react';
import { message } from 'antd';
import { pollApplicationLinkJob, submitApplicationLink } from '../api/applicationLink';
import { buildApplicationLinkActivity, extractApplicationLinkResult } from '../model/jobModel';
import type {
  ApplicationLinkActivity,
  ApplicationLinkResult,
  ApplicationLinkSubmission,
} from '../model/types';

export function useApplicationLinkGenerator() {
  const [result, setResult] = useState<ApplicationLinkResult | null>(null);
  const [activity, setActivity] = useState<ApplicationLinkActivity | null>(null);

  const generate = useCallback(async (values: ApplicationLinkSubmission) => {
    setResult(null);
    setActivity(buildApplicationLinkActivity('submitting', 0));
    try {
      const submitted = await submitApplicationLink(values);
      setActivity(buildApplicationLinkActivity(submitted.status, submitted.progress, submitted.id));
      const job = await pollApplicationLinkJob(submitted.id, (value) => {
        setActivity(buildApplicationLinkActivity(value.status, value.progress, value.id));
      });
      setResult(extractApplicationLinkResult(job));
      message.success('申请链接生成完成');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '生成失败');
    } finally {
      setActivity(null);
    }
  }, []);

  return { result, activity, busy: Boolean(activity), generate };
}
