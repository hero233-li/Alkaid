import {
  Button,
  Card,
  Col,
  DatePicker,
  Form,
  Input,
  Row,
  Select,
  Switch,
  type FormInstance,
} from 'antd';
import { Search } from 'lucide-react';
import { highFrequencyConfig } from '../config/highFrequencyConfig';
import type { HighFrequencySearchValues } from '../types';

export default function HighFrequencySearchForm({
  form,
  busy,
  onSubmit,
}: {
  form: FormInstance<HighFrequencySearchValues>;
  busy: boolean;
  onSubmit: (values: HighFrequencySearchValues) => void;
}) {
  const useDefaultParams = Form.useWatch('useDefaultParams', form) ?? true;
  return (
    <Card title="Risk050009 高频交易查询">
      <Form
        form={form}
        layout="vertical"
        disabled={busy}
        initialValues={{ environment: highFrequencyConfig.environments[0], useDefaultParams: true }}
        onFinish={onSubmit}
      >
        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item name="environment" label="环境" rules={[{ required: true }]}>
              <Select
                options={highFrequencyConfig.environments.map((value) => ({ value, label: value }))}
              />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="useDefaultParams" label="默认参数" valuePropName="checked">
              <Switch checkedChildren="开" unCheckedChildren="关" />
            </Form.Item>
          </Col>
          {!useDefaultParams && (
            <>
              <Col xs={24} md={8}>
                <Form.Item
                  name="cardNo"
                  label="卡号"
                  rules={[{ required: true, message: '请输入卡号' }]}
                >
                  <Input placeholder="请输入卡号" />
                </Form.Item>
              </Col>
              <Col xs={24} md={8}>
                <Form.Item
                  name="startDate"
                  label="起始时间"
                  rules={[{ required: true, message: '请选择起始时间' }]}
                >
                  <DatePicker style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col xs={24} md={8}>
                <Form.Item
                  name="endDate"
                  label="结束时间"
                  rules={[{ required: true, message: '请选择结束时间' }]}
                >
                  <DatePicker style={{ width: '100%' }} />
                </Form.Item>
              </Col>
            </>
          )}
        </Row>
        <div className="high-frequency-actions">
          <Button type="primary" htmlType="submit" icon={<Search size={16} />}>
            查询
          </Button>
        </div>
      </Form>
    </Card>
  );
}
