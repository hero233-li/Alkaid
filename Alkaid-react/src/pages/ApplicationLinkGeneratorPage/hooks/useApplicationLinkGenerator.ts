import {useState} from 'react';
import {message} from 'antd';
import {pollApplicationLinkJob, submitApplicationLink} from '../api/applicationLink';
import type {ApplicationLinkActivity, ApplicationLinkFormValues, ApplicationLinkResult} from '../types';

export function useApplicationLinkGenerator() {
    const [result, setResult] = useState<ApplicationLinkResult | null>(null);
    const [activity, setActivity] = useState<ApplicationLinkActivity | null>(null);
    const generate = async (values: ApplicationLinkFormValues) => {
        setResult(null);
        setActivity({label: '正在生成申请链接', status: 'submitting', progress: 0});
        try {
            const submitted = await submitApplicationLink(values);
            setActivity({
                jobId: submitted.id,
                label: '正在生成申请链接',
                status: submitted.status,
                progress: submitted.progress
            });
            const job = await pollApplicationLinkJob(submitted.id, value => setActivity({
                jobId: value.id,
                label: '正在生成申请链接',
                status: value.status,
                progress: value.progress
            }));
            setResult(job.result.links as ApplicationLinkResult);
            message.success('申请链接生成完成')
        } catch (error) {
            message.error(error instanceof Error ? error.message : '生成失败')
        } finally {
            setActivity(null)
        }
    };
    return {result, activity, busy: Boolean(activity), generate}
}
