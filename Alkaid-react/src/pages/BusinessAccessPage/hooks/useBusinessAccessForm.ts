import { useCallback, useEffect, useMemo, useState } from 'react';
import { Form } from 'antd';
import { getBusinessAccessConfig } from '../api/businessAccess';
import {
  buildBusinessAccessSearchSubmission,
  getBusinessAccessEnvironmentOptions,
  getInitialBusinessAccessSearchValues,
} from '../model/searchModel';
import type { BusinessAccessSearchValues } from '../types';

export function useBusinessAccessForm() {
  const [form] = Form.useForm<BusinessAccessSearchValues>();
  const [config, setConfig] = useState<Awaited<ReturnType<typeof getBusinessAccessConfig>> | null>(null);
  const [configLoading, setConfigLoading] = useState(true);
  const [configError, setConfigError] = useState<string | null>(null);
  const initialValues = useMemo(() => getInitialBusinessAccessSearchValues(config), [config]);
  const environmentOptions = useMemo(
    () => getBusinessAccessEnvironmentOptions(config),
    [config],
  );

  useEffect(() => {
    let active = true;
    void getBusinessAccessConfig()
      .then((value) => {
        if (!active) return;
        setConfig(value);
        setConfigError(null);
        form.setFieldsValue(getInitialBusinessAccessSearchValues(value));
      })
      .catch((error: unknown) => {
        if (active) {
          setConfigError(error instanceof Error ? error.message : '获取业务准入配置失败');
        }
      })
      .finally(() => {
        if (active) setConfigLoading(false);
      });
    return () => {
      active = false;
    };
  }, [form]);

  const createSubmission = useCallback((values: BusinessAccessSearchValues) => (
    buildBusinessAccessSearchSubmission(values)
  ), []);

  const reset = useCallback(() => {
    form.resetFields();
    form.setFieldsValue(initialValues);
  }, [form, initialValues]);

  return {
    form,
    initialValues,
    environmentOptions,
    configLoading,
    configError,
    createSubmission,
    reset,
  };
}
