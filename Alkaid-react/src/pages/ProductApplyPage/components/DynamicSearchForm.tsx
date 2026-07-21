import { Button, Space, type FormInstance } from 'antd';
import { Play, RotateCcw } from 'lucide-react';
import { SchemaForm } from '../../../components/common';
import type { ProductApplicationFormValues, ProductFieldConfig } from '../model/types';

interface DynamicSearchFormProps {
  form: FormInstance<ProductApplicationFormValues>;
  fields: ProductFieldConfig[];
  submitting: boolean;
  onValuesChange: (
    changedValues: ProductApplicationFormValues,
    allValues: ProductApplicationFormValues,
  ) => void;
  onSubmit: (values: ProductApplicationFormValues) => void;
  onReset: () => void;
}

export default function DynamicSearchForm({
  form,
  fields,
  submitting,
  onValuesChange,
  onSubmit,
  onReset,
}: DynamicSearchFormProps) {
  return (
    <SchemaForm<ProductApplicationFormValues>
      form={form}
      fields={fields}
      title="申请参数"
      submitting={submitting}
      onValuesChange={onValuesChange}
      onSubmit={onSubmit}
      renderActions={() => (
        <div className="common-form-actions">
          <Space>
            <Button
              type="primary"
              htmlType="submit"
              loading={submitting}
              disabled={submitting}
              icon={<Play size={16} />}
            >
              {submitting ? '提交中' : '执行'}
            </Button>
            <Button icon={<RotateCcw size={16} />} onClick={onReset}>
              重置
            </Button>
          </Space>
        </div>
      )}
    />
  );
}
