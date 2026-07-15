import { Alert, Button, Form, Spin } from 'antd';
import { useState } from 'react';
import ApplicationDataQrModal from './components/ApplicationDataQrModal';
import ApplicationDataResultList from './components/ApplicationDataResultList';
import ApplicationDataSearchForm from './components/ApplicationDataSearchForm';
import ApplicationDataWorkflowModal from './components/ApplicationDataWorkflowModal';
import { useApplicationDataGenerator } from './hooks/useApplicationDataGenerator';
import type { ApplicationDataFormValues } from './types';
import './styles.css';

export default function ApplicationDataGeneratorPage() {
  const [form] = Form.useForm<ApplicationDataFormValues>();
  const state = useApplicationDataGenerator();
  const [qr, setQr] = useState('');
  if (state.configError) return <Alert type="error" showIcon message="申请数据配置加载失败" description={state.configError} action={<Button onClick={() => void state.reloadConfig()}>重新加载</Button>} />;
  if (!state.config) return <Spin />;
  return <div className="application-data-page">
    <ApplicationDataSearchForm form={form} config={state.config} busy={state.busy} onSubmit={(values) => void state.generate(values)} />
    <ApplicationDataResultList records={state.records} onQr={setQr} />
    <ApplicationDataQrModal value={qr} onClose={() => setQr('')} />
    <ApplicationDataWorkflowModal activity={state.activity} />
  </div>;
}
