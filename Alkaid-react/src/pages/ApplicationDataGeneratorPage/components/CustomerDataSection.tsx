import { Col, DatePicker, Form, Input, InputNumber, Row, Select, type FormInstance } from 'antd';
import dayjs from 'dayjs';
import type { ApplicationDataConfig, ApplicationDataFormValues } from '../types';

export default function CustomerDataSection({
  form,
  config,
}: {
  form: FormInstance<ApplicationDataFormValues>;
  config: ApplicationDataConfig;
}) {
  const syncBirthDate = () => {
    const date = form.getFieldValue('currentDate') ?? dayjs();
    form.setFieldValue(
      'birthDate',
      date.subtract(form.getFieldValue('age') ?? 40, 'year').format('YYYY-MM-DD'),
    );
  };
  return (
    <>
      <div className="application-data-section-title">客户数据生成</div>
      <Row gutter={16}>
        <Col span={8}>
          <Form.Item name="environment" label="环境" rules={[{ required: true }]}>
            <Select options={config.environments.map((value) => ({ value, label: value }))} />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="currentDate" label="当前时间" rules={[{ required: true }]}>
            <DatePicker style={{ width: '100%' }} onChange={syncBirthDate} />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="age" label="年龄" rules={[{ required: true }]}>
            <InputNumber min={18} max={100} style={{ width: '100%' }} onChange={syncBirthDate} />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="birthDate" label="出生日期" rules={[{ required: true }]}>
            <Input readOnly />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="gender" label="性别" rules={[{ required: true }]}>
            <Select options={config.genders.map((value) => ({ value, label: value }))} />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="tellerNo" label="开卡柜员" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
        </Col>
      </Row>
    </>
  );
}
