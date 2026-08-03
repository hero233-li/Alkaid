import { Button, Card, Form, type FormInstance } from 'antd';
import dayjs from 'dayjs';
import { Sparkles } from 'lucide-react';
import { applicationDataConfig } from '../config/applicationDataConfig';
import type { ApplicationDataConfig, ApplicationDataFormValues } from '../types';
import CustomerDataSection from './CustomerDataSection';
import EnterpriseDataSection from './EnterpriseDataSection';

export default function ApplicationDataSearchForm({
  form,
  config,
  busy,
  onSubmit,
}: {
  form: FormInstance<ApplicationDataFormValues>;
  config: ApplicationDataConfig;
  busy: boolean;
  onSubmit: (values: ApplicationDataFormValues) => void;
}) {
  return (
    <Card title="申请数据生成">
      <Form
        form={form}
        layout="vertical"
        disabled={busy}
        onFinish={onSubmit}
        initialValues={{
          environment: config.environments[0],
          currentDate: dayjs(),
          age: applicationDataConfig.defaultAge,
          birthDate: dayjs()
            .subtract(applicationDataConfig.defaultAge, 'year')
            .format('YYYY-MM-DD'),
          gender: applicationDataConfig.defaultGender,
          tellerNo: applicationDataConfig.defaultTellerNo,
          companyType: applicationDataConfig.defaultCompanyType,
          count: applicationDataConfig.defaultCount,
        }}
      >
        <CustomerDataSection form={form} config={config} />
        <EnterpriseDataSection config={config} />
        <div className="application-data-actions">
          <Button type="primary" htmlType="submit" icon={<Sparkles size={16} />}>
            生成数据
          </Button>
        </div>
      </Form>
    </Card>
  );
}
