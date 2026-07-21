import { useEffect, useRef, useState } from 'react';
import { message } from 'antd';
import {
  getApplicationDataConfig,
  pollApplicationData,
  submitApplicationData,
} from '../api/applicationData';
import type {
  ApplicationDataActivity,
  ApplicationDataConfig,
  ApplicationDataFormValues,
  ApplicationDataRecord,
} from '../types';

export function useApplicationDataGenerator() {
  const [config, setConfig] = useState<ApplicationDataConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [records, setRecords] = useState<ApplicationDataRecord[]>([]);
  const [activity, setActivity] = useState<ApplicationDataActivity | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const loadConfig = async () => {
    setConfigError(null);
    try {
      setConfig(await getApplicationDataConfig());
    } catch (error) {
      setConfigError(error instanceof Error ? error.message : '配置加载失败');
    }
  };
  useEffect(() => {
    void loadConfig();
    return () => controllerRef.current?.abort();
  }, []);
  const generate = async (values: ApplicationDataFormValues) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setRecords([]);
    setActivity({ label: '正在生成客户及企业数据', status: 'submitting', progress: 0 });
    try {
      const submitted = await submitApplicationData(values);
      setActivity({
        jobId: submitted.id,
        label: '正在生成客户及企业数据',
        status: submitted.status,
        progress: submitted.progress,
      });
      const job = await pollApplicationData(
        submitted.id,
        (value) =>
          setActivity({
            jobId: value.id,
            label: '正在生成客户及企业数据',
            status: value.status,
            progress: value.progress,
          }),
        { signal: controller.signal },
      );
      setRecords(job.result.records ?? []);
      message.success('申请数据生成完成');
    } catch (error) {
      if (!isCancelled(error)) message.error(error instanceof Error ? error.message : '生成失败');
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setActivity(null);
      }
    }
  };
  return {
    config,
    configError,
    records,
    activity,
    busy: Boolean(activity),
    generate,
    reloadConfig: loadConfig,
  };
}

function isCancelled(error: unknown) {
  return error instanceof Error && (error.name === 'AbortError' || error.name === 'CanceledError');
}
