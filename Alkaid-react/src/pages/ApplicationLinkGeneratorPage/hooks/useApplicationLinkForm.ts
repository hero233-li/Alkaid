import { useCallback, useMemo } from 'react';
import { Form } from 'antd';
import { applicationLinkConfig } from '../config/applicationLinkConfig';
import {
  buildApplicationLinkFormModel,
  getApplicationLinkCascadeUpdates,
  getInitialApplicationLinkValues,
} from '../model/formModel';
import { buildApplicationLinkSubmission } from '../model/submission';
import type { ApplicationLinkFormValues } from '../model/types';

export function useApplicationLinkForm() {
  const [form] = Form.useForm<ApplicationLinkFormValues>();
  const initialValues = useMemo(
    () => getInitialApplicationLinkValues(applicationLinkConfig),
    [],
  );
  const watchedValues = Form.useWatch([], form) ?? initialValues;
  const formModel = useMemo(
    () => buildApplicationLinkFormModel(applicationLinkConfig, watchedValues),
    [watchedValues],
  );

  const handleValuesChange = useCallback((
    changedValues: Partial<ApplicationLinkFormValues>,
    allValues: ApplicationLinkFormValues,
  ) => {
    const updates = getApplicationLinkCascadeUpdates(
      applicationLinkConfig,
      changedValues,
      allValues,
    );
    if (Object.keys(updates).length) {
      form.setFieldsValue(updates);
    }
  }, [form]);

  const createSubmission = useCallback((values: ApplicationLinkFormValues) => (
    buildApplicationLinkSubmission(applicationLinkConfig, values)
  ), []);

  return {
    form,
    formModel,
    initialValues,
    handleValuesChange,
    createSubmission,
  };
}
