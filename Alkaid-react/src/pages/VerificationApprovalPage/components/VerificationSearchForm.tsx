import { Button, Card, Col, Form, Input, Row, Select, Space, type FormInstance } from 'antd';
import { RotateCcw, Search } from 'lucide-react';
import type { VerificationSearchValues } from '../types';

interface VerificationSearchFormProps {
  form: FormInstance<VerificationSearchValues>;
  initialValues: VerificationSearchValues;
  searching: boolean;
  configLoading: boolean;
  environmentOptions: Array<{ value: string; label: string }>;
  categoryOptions: Array<{ value: string; label: string }>;
  onSearch: (values: VerificationSearchValues) => void;
  onReset: () => void;
}

export default function VerificationSearchForm({
  form,
  initialValues,
  searching,
  configLoading,
  environmentOptions,
  categoryOptions,
  onSearch,
  onReset,
}: VerificationSearchFormProps) {
  return (
    <Card title="搜索条件">
      <Form<VerificationSearchValues>
        form={form}
        layout="vertical"
        initialValues={initialValues}
        disabled={searching || configLoading}
        onFinish={onSearch}
      >
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Form.Item
              name="environment"
              label="环境"
              rules={[{ required: true, message: '请选择环境' }]}
            >
              <Select options={environmentOptions} placeholder="请选择环境" />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item
              name="category"
              label="类别"
              rules={[{ required: true, message: '请选择类别' }]}
            >
              <Select options={categoryOptions} placeholder="请选择类别" />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item
              name="contractNo"
              label="合同号"
              rules={[{ required: true, message: '请输入合同号' }]}
            >
              <Input placeholder="请输入合同号，例如 HT20260710001" allowClear />
            </Form.Item>
          </Col>
        </Row>
        <div className="common-form-actions">
          <Space>
            <Button
              type="primary"
              htmlType="submit"
              icon={<Search size={16} />}
              loading={searching || configLoading}
            >
              搜索
            </Button>
            <Button
              icon={<RotateCcw size={16} />}
              disabled={searching || configLoading}
              onClick={onReset}
            >
              重置
            </Button>
          </Space>
        </div>
      </Form>
    </Card>
  );
}
