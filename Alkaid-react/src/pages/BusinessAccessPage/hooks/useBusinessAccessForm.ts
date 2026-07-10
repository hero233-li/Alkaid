import { useCallback, useMemo } from 'react';
import { Form } from 'antd';
import {
  buildBusinessAccessSearchSubmission,
  getInitialBusinessAccessSearchValues,
} from '../model/searchModel';
import type { BusinessAccessSearchValues } from '../types';

export function useBusinessAccessForm() {
  const [form] = Form.useForm<BusinessAccessSearchValues>();
  const initialValues = useMemo(() => getInitialBusinessAccessSearchValues(), []);

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
    createSubmission,
    reset,
  };
}
