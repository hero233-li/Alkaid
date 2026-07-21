import type { ReactNode } from 'react';
import {
  Card,
  Col,
  Form,
  Input,
  Row,
  Select,
  Switch,
  type CardProps,
  type FormInstance,
  type FormItemProps,
  type InputProps,
  type SelectProps,
  type SwitchProps,
} from 'antd';

export type SchemaFormControl = 'input' | 'select' | 'switch' | 'custom';

export interface SchemaFormOption {
  label: ReactNode;
  value: string | number;
  disabled?: boolean;
}

export interface SchemaFormField<TValues extends object> {
  name: NonNullable<FormItemProps<TValues>['name']>;
  label: ReactNode;
  control: SchemaFormControl;
  span?: number;
  required?: boolean;
  editable?: boolean;
  placeholder?: string;
  searchable?: boolean;
  options?: SchemaFormOption[];
  checkedLabel?: ReactNode;
  uncheckedLabel?: ReactNode;
  switchWidth?: number;
  requiredMessage?: string;
  rules?: FormItemProps['rules'];
  inputProps?: InputProps;
  selectProps?: SelectProps;
  switchProps?: SwitchProps;
  render?: (field: SchemaFormField<TValues>, form: FormInstance<TValues>) => ReactNode;
}

export interface SchemaFormActionContext<TValues extends object> {
  form: FormInstance<TValues>;
  submitting: boolean;
}

export interface SchemaFormProps<TValues extends object> {
  form: FormInstance<TValues>;
  fields: SchemaFormField<TValues>[];
  title?: ReactNode;
  submitting?: boolean;
  disabled?: boolean;
  cardProps?: Omit<CardProps, 'title' | 'children'>;
  onValuesChange?: (changedValues: Partial<TValues>, allValues: TValues) => void;
  onSubmit: (values: TValues) => void;
  renderActions?: (context: SchemaFormActionContext<TValues>) => ReactNode;
}

function renderControl<TValues extends object>(
  field: SchemaFormField<TValues>,
  form: FormInstance<TValues>,
) {
  if (field.render) {
    return field.render(field, form);
  }
  if (field.control === 'select') {
    return (
      <Select
        {...field.selectProps}
        disabled={field.editable === false || field.selectProps?.disabled}
        options={field.options}
        placeholder={field.placeholder ?? field.selectProps?.placeholder}
        showSearch={field.searchable ?? field.selectProps?.showSearch}
        optionFilterProp={field.selectProps?.optionFilterProp ?? 'label'}
        allowClear={field.selectProps?.allowClear ?? true}
      />
    );
  }
  if (field.control === 'switch') {
    return (
      <Switch
        {...field.switchProps}
        disabled={field.editable === false || field.switchProps?.disabled}
        checkedChildren={field.checkedLabel}
        unCheckedChildren={field.uncheckedLabel}
        style={{
          ...field.switchProps?.style,
          ...(field.switchWidth ? { minWidth: field.switchWidth } : {}),
        }}
      />
    );
  }
  if (field.control === 'custom') {
    return null;
  }
  return (
    <Input
      {...field.inputProps}
      disabled={field.editable === false || field.inputProps?.disabled}
      placeholder={field.placeholder ?? field.inputProps?.placeholder}
    />
  );
}

export default function SchemaForm<TValues extends object>({
  form,
  fields,
  title,
  submitting = false,
  disabled = false,
  cardProps,
  onValuesChange,
  onSubmit,
  renderActions,
}: SchemaFormProps<TValues>) {
  return (
    <Card {...cardProps} title={title}>
      <Form<TValues>
        form={form}
        layout="vertical"
        disabled={disabled}
        onValuesChange={onValuesChange}
        onFinish={onSubmit}
      >
        <Row gutter={[16, 4]}>
          {fields.map((field) => (
            <Col xs={24} sm={12} lg={field.span ?? 8} key={String(field.name)}>
              <Form.Item
                name={field.name as never}
                label={field.label}
                valuePropName={field.control === 'switch' ? 'checked' : 'value'}
                rules={
                  field.rules ??
                  (field.required
                    ? [
                        {
                          required: true,
                          message:
                            field.requiredMessage ??
                            `请填写${typeof field.label === 'string' ? field.label : '该字段'}`,
                        },
                      ]
                    : undefined)
                }
              >
                {renderControl(field, form)}
              </Form.Item>
            </Col>
          ))}
        </Row>
        {renderActions?.({ form, submitting })}
      </Form>
    </Card>
  );
}
