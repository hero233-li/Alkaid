import { Button, Card, Col, Form, Input, Row, Select, Space, type FormInstance } from 'antd';
import { RotateCcw, Search } from 'lucide-react';
import type { BusinessAccessSearchValues } from '../../../api/businessAccess';
import { businessAccessConfig } from '../config/businessAccessConfig';

const environmentOptions = businessAccessConfig.environments.map((value) => ({ value, label: value }));

interface BusinessAccessSearchFormProps {
  form: FormInstance<BusinessAccessSearchValues>;
  busy: boolean;
  searching: boolean;
  onSearch: (values: BusinessAccessSearchValues) => void;
}

export default function BusinessAccessSearchForm({
  form,
  busy,
  searching,
  onSearch,
}: BusinessAccessSearchFormProps) {
  const submitSearch = (values: BusinessAccessSearchValues) => {
    onSearch({
      environment: values.environment,
      name: values.name?.trim(),
      certificateNo: values.certificateNo?.trim(),
    });
  };

  return (
    <Card title="查询条件">
      <Form<BusinessAccessSearchValues>
        form={form}
        layout="vertical"
        disabled={busy}
        initialValues={{ environment: businessAccessConfig.environments[0] }}
        onFinish={submitSearch}
      >
        <div className="business-access-search-form">
          <Row gutter={[16, 4]} justify="center">
            <Col xs={24} md={8}>
              <Form.Item
                name="environment"
                label="环境"
                rules={[{ required: true, message: '请选择环境' }]}
              >
                <Select options={environmentOptions} placeholder="请选择环境" allowClear={false} />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item
                name="name"
                label="姓名"
                dependencies={['certificateNo']}
                rules={[
                  ({ getFieldValue }) => ({
                    validator() {
                      const name = String(getFieldValue('name') ?? '').trim();
                      const certificateNo = String(getFieldValue('certificateNo') ?? '').trim();
                      return name || certificateNo
                        ? Promise.resolve()
                        : Promise.reject(new Error('姓名和身份证号至少填写一个'));
                    },
                  }),
                ]}
              >
                <Input placeholder="请输入姓名" allowClear />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item
                name="certificateNo"
                label="身份证号"
                dependencies={['name']}
                rules={[
                  ({ getFieldValue }) => ({
                    validator() {
                      const name = String(getFieldValue('name') ?? '').trim();
                      const certificateNo = String(getFieldValue('certificateNo') ?? '').trim();
                      return name || certificateNo
                        ? Promise.resolve()
                        : Promise.reject(new Error('姓名和身份证号至少填写一个'));
                    },
                  }),
                ]}
              >
                <Input placeholder="请输入身份证号" maxLength={18} allowClear />
              </Form.Item>
            </Col>
          </Row>
        </div>
        <div className="common-form-actions">
          <Space>
            <Button
              type="primary"
              htmlType="submit"
              icon={<Search size={16} />}
              loading={searching}
              disabled={busy}
            >
              查询
            </Button>
            <Button
              disabled={busy}
              icon={<RotateCcw size={16} />}
              onClick={() => {
                form.resetFields();
                form.setFieldValue('environment', businessAccessConfig.environments[0]);
              }}
            >
              重置
            </Button>
          </Space>
        </div>
      </Form>
    </Card>
  );
}
