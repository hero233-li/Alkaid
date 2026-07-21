import { useCallback, useEffect, useMemo, useState } from 'react';
import { Form } from 'antd';
import { getVerificationApprovalConfig } from '../api/verificationApproval';
import {
  buildVerificationSearchSubmission,
  getInitialVerificationSearchValues,
  getVerificationSearchOptions,
} from '../model/searchModel';
import type { VerificationSearchValues } from '../types';

export function useVerificationApprovalForm() {
  const [form] = Form.useForm<VerificationSearchValues>();
  const [config, setConfig] = useState<Awaited<
    ReturnType<typeof getVerificationApprovalConfig>
  > | null>(null);
  const [configLoading, setConfigLoading] = useState(true);
  const [configError, setConfigError] = useState<string | null>(null);
  const initialValues = useMemo(() => getInitialVerificationSearchValues(config), [config]);
  const options = useMemo(() => getVerificationSearchOptions(config), [config]);

  useEffect(() => {
    let active = true;
    setConfigLoading(true);
    void getVerificationApprovalConfig()
      .then((value) => {
        if (!active) return;
        setConfig(value);
        setConfigError(null);
        form.setFieldsValue(getInitialVerificationSearchValues(value));
      })
      .catch((error: unknown) => {
        if (active) {
          setConfigError(error instanceof Error ? error.message : '获取核实审批配置失败');
        }
      })
      .finally(() => {
        if (active) setConfigLoading(false);
      });
    return () => {
      active = false;
    };
  }, [form]);

  const createSubmission = useCallback(
    (values: VerificationSearchValues) => buildVerificationSearchSubmission(values),
    [],
  );

  const reset = useCallback(() => {
    form.resetFields();
    form.setFieldsValue(initialValues);
  }, [form, initialValues]);

  return {
    form,
    initialValues,
    options,
    configLoading,
    configError,
    createSubmission,
    reset,
  };
}
