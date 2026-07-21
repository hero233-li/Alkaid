import { Button, Card, Col, Form, Input, Row, Select, type FormInstance } from 'antd';
import { Link2 } from 'lucide-react';
import type { ApplicationLinkFormModel } from '../model/formModel';
import type { ApplicationLinkFormValues } from '../model/types';

interface ApplicationLinkSearchFormProps {
  form: FormInstance<ApplicationLinkFormValues>;
  formModel: ApplicationLinkFormModel;
  initialValues: ApplicationLinkFormValues;
  busy: boolean;
  onValuesChange: (
    changedValues: Partial<ApplicationLinkFormValues>,
    allValues: ApplicationLinkFormValues,
  ) => void;
  onSubmit: (values: ApplicationLinkFormValues) => void;
}

export default function ApplicationLinkSearchForm({
  form,
  formModel,
  initialValues,
  busy,
  onValuesChange,
  onSubmit,
}: ApplicationLinkSearchFormProps) {
  return (
    <Card title="申请链接配置">
      <Form
        form={form}
        layout="vertical"
        disabled={busy}
        onFinish={onSubmit}
        initialValues={initialValues}
        onValuesChange={onValuesChange}
      >
        <Row gutter={16} wrap={false} className="application-link-base-fields">
          <Col flex="1 1 0">
            <Form.Item name="environment" label="环境" rules={[{ required: true }]}>
              <Select options={formModel.environmentOptions} />
            </Form.Item>
          </Col>
          <Col flex="1 1 0">
            <Form.Item name="category" label="类别" rules={[{ required: true }]}>
              <Select disabled={!formModel.environment} options={formModel.categoryOptions} />
            </Form.Item>
          </Col>
          <Col flex="1 1 0">
            <Form.Item name="product" label="产品" rules={[{ required: true }]}>
              <Select disabled={!formModel.category} options={formModel.productOptions} />
            </Form.Item>
          </Col>
          {formModel.cooperationProjectOptions.length > 0 && (
            <Col flex="1 1 0">
              <Form.Item name="cooperationProjectId" label="合作项目" rules={[{ required: true }]}>
                <Select options={formModel.cooperationProjectOptions} />
              </Form.Item>
            </Col>
          )}
          <Col flex="1 1 0">
            <Form.Item name="loanType" label="首贷续贷" rules={[{ required: true }]}>
              <Select options={formModel.loanTypeOptions} />
            </Form.Item>
          </Col>
        </Row>
        {formModel.dynamic && (
          <Row gutter={16}>
            <Col span={24}>
              <Form.Item
                name="requestJson"
                label="动态链接 JSON 参数"
                rules={[{ required: true, message: '请输入动态链接 JSON 参数' }]}
              >
                <Input.TextArea
                  autoSize={{ minRows: 6, maxRows: 16 }}
                  placeholder={
                    '{\n  "customerName": "张三",\n  "applicationArea": "成都",\n  "amount": 100000\n}'
                  }
                />
              </Form.Item>
            </Col>
          </Row>
        )}
        <Row gutter={16}>
          {formModel.showRestoreStatus && (
            <Col span={8}>
              <Form.Item name="restoreStatus" label="还原状况" rules={[{ required: true }]}>
                <Select options={formModel.restoreStatusOptions} />
              </Form.Item>
            </Col>
          )}
          {formModel.showSpcode && (
            <Col span={8}>
              <Form.Item name="spcode" label="企业代码 spcode" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
            </Col>
          )}
        </Row>
        <div className="application-link-actions">
          <Button type="primary" htmlType="submit" icon={<Link2 size={16} />}>
            生成申请链接
          </Button>
        </div>
      </Form>
    </Card>
  );
}
