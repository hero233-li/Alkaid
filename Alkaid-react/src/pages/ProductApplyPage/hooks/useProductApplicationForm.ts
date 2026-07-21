import { useCallback, useEffect, useMemo, useRef } from 'react';
import { Form, message } from 'antd';
import {
  buildProductApplicationFields,
  getInitialProductApplicationValues,
  normalizeProductApplicationValues,
} from '../model/configAdapter';
import { clearStaleFormCaches, formCacheKey, readFormDraft, safeFormDraft } from '../model/cache';
import { buildProductSubmission } from '../model/submission';
import type { ProductApplicationConfig, ProductApplicationFormValues } from '../model/types';

export function useProductApplicationForm(
  config: ProductApplicationConfig | null,
  pageInstanceKey: string,
) {
  const [form] = Form.useForm<ProductApplicationFormValues>();
  const previousCompanyName = useRef('');
  const watchedValues = Form.useWatch([], form) || {};
  const cacheKey = config ? formCacheKey(pageInstanceKey, config.version) : '';
  const fields = useMemo(
    () => (config ? buildProductApplicationFields(config, watchedValues) : []),
    [config, watchedValues],
  );

  useEffect(() => {
    if (!config || !cacheKey) {
      return;
    }
    clearStaleFormCaches(pageInstanceKey, cacheKey);
    const initialValues = getInitialProductApplicationValues(config);
    const draft = readFormDraft(cacheKey);
    const normalizedValues = normalizeProductApplicationValues(config, {
      ...initialValues,
      ...draft,
    });
    form.resetFields();
    form.setFieldsValue(normalizedValues);
    previousCompanyName.current = String(normalizedValues.companyName || '').trim();
  }, [cacheKey, config, form, pageInstanceKey]);

  const handleValuesChange = useCallback(
    (changedValues: ProductApplicationFormValues, allValues: ProductApplicationFormValues) => {
      if (!config || !cacheKey) {
        return;
      }
      const changedName = Object.keys(changedValues)[0];
      if (!changedName) {
        return;
      }
      const nextValues = { ...allValues };
      const updates: ProductApplicationFormValues = {};

      for (const fieldName of config.cascadeResetMap[changedName] || []) {
        nextValues[fieldName] = undefined;
        const nextField = buildProductApplicationFields(config, nextValues).find(
          (field) => field.name === fieldName,
        );
        const nextValue = nextField?.options?.[0]?.value;
        updates[fieldName] = nextValue;
        nextValues[fieldName] = nextValue;
      }
      if (changedName === 'product') {
        const activeFields = buildProductApplicationFields(config, nextValues);
        const activeFieldNames = new Set(activeFields.map((field) => field.name));
        for (const field of config.fields) {
          const nextValue = activeFieldNames.has(field.name)
            ? (nextValues[field.name] ?? field.defaultValue)
            : undefined;
          updates[field.name] = nextValue;
          nextValues[field.name] = nextValue;
        }
      }
      if (changedName === 'companyName') {
        const nextCompanyName = String(nextValues.companyName || '').trim();
        const changedBetweenCustomerKinds = !previousCompanyName.current || !nextCompanyName;
        if (changedBetweenCustomerKinds) {
          updates.legalPerson = true;
          nextValues.legalPerson = true;
        }
        previousCompanyName.current = nextCompanyName;
      }
      if (Object.keys(updates).length) {
        form.setFieldsValue(updates);
      }
      sessionStorage.setItem(cacheKey, JSON.stringify(safeFormDraft(config, nextValues)));
    },
    [cacheKey, config, form],
  );

  const createSubmission = useCallback(
    (values: ProductApplicationFormValues) => {
      if (!config) {
        throw new Error('产品申请配置尚未加载');
      }
      return buildProductSubmission(config, values);
    },
    [config],
  );

  const reset = useCallback(() => {
    if (!config || !cacheKey) {
      return;
    }
    sessionStorage.removeItem(cacheKey);
    form.resetFields();
    form.setFieldsValue(getInitialProductApplicationValues(config));
    previousCompanyName.current = '';
    message.success('表单已重置');
  }, [cacheKey, config, form]);

  return {
    form,
    fields,
    handleValuesChange,
    createSubmission,
    reset,
  };
}
