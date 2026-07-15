import { useCallback, useEffect, useMemo, useState } from 'react';
import { Form } from 'antd';
import { getApplicationLinkConfig } from '../api/applicationLink';
import { applicationLinkLocalOptions } from '../config/applicationLinkConfig';
import {
  buildApplicationLinkFormModel,
  getApplicationLinkCascadeUpdates,
  getInitialApplicationLinkValues,
} from '../model/formModel';
import { buildApplicationLinkSubmission } from '../model/submission';
import type { ApplicationLinkConfig, ApplicationLinkFormValues } from '../model/types';

const emptyConfig: ApplicationLinkConfig = {
  environments: [],
  products: [],
  cooperationProjects: [],
  ...applicationLinkLocalOptions,
};

export function useApplicationLinkForm() {
  const [form] = Form.useForm<ApplicationLinkFormValues>();
  const [config, setConfig] = useState<ApplicationLinkConfig>(emptyConfig);
  const [configLoading, setConfigLoading] = useState(true);
  const [configError, setConfigError] = useState('');
  const initialValues = useMemo(
    () => getInitialApplicationLinkValues(config),
    [config],
  );
  const watchedValues = Form.useWatch([], form) ?? initialValues;
  const formModel = useMemo(
    () => buildApplicationLinkFormModel(config, watchedValues),
    [config, watchedValues],
  );

  useEffect(() => {
    let active = true;
    void getApplicationLinkConfig()
      .then((backendConfig) => {
        if (!active) return;
        const nextConfig = { ...backendConfig, ...applicationLinkLocalOptions };
        setConfig(nextConfig);
        form.setFieldsValue(getInitialApplicationLinkValues(nextConfig));
      })
      .catch((error: unknown) => {
        if (active) {
          setConfigError(error instanceof Error ? error.message : '获取申请链接配置失败');
        }
      })
      .finally(() => {
        if (active) setConfigLoading(false);
      });
    return () => { active = false; };
  }, [form]);

  const handleValuesChange = useCallback((
    changedValues: Partial<ApplicationLinkFormValues>,
    allValues: ApplicationLinkFormValues,
  ) => {
    const updates = getApplicationLinkCascadeUpdates(
      config,
      changedValues,
      allValues,
    );
    if (Object.keys(updates).length) {
      form.setFieldsValue(updates);
    }
  }, [config, form]);

  const createSubmission = useCallback((values: ApplicationLinkFormValues) => (
    buildApplicationLinkSubmission(config, values)
  ), [config]);

  return {
    form,
    formModel,
    initialValues,
    handleValuesChange,
    createSubmission,
    configLoading,
    configError,
  };
}
