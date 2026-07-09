import { message } from 'antd';
import { useState } from 'react';
import ApplicationLinkQrModal from './components/ApplicationLinkQrModal';
import ApplicationLinkResultList from './components/ApplicationLinkResultList';
import ApplicationLinkSearchForm from './components/ApplicationLinkSearchForm';
import ApplicationLinkWorkflowModal from './components/ApplicationLinkWorkflowModal';
import { useApplicationLinkForm } from './hooks/useApplicationLinkForm';
import { useApplicationLinkGenerator } from './hooks/useApplicationLinkGenerator';
import type { ApplicationLinkFormValues } from './model/types';
import './styles.css';

export default function ApplicationLinkGeneratorPage() {
  const applicationForm = useApplicationLinkForm();
  const generator = useApplicationLinkGenerator();
  const [qr, setQr] = useState('');

  const submit = (values: ApplicationLinkFormValues) => {
    try {
      void generator.generate(applicationForm.createSubmission(values));
    } catch (error) {
      message.error(error instanceof Error ? error.message : '申请链接配置不完整');
    }
  };

  return (
    <div className="application-link-page">
      <ApplicationLinkSearchForm
        form={applicationForm.form}
        formModel={applicationForm.formModel}
        initialValues={applicationForm.initialValues}
        busy={generator.busy}
        onValuesChange={applicationForm.handleValuesChange}
        onSubmit={submit}
      />
      <ApplicationLinkResultList result={generator.result} onQr={setQr} />
      <ApplicationLinkQrModal value={qr} onClose={() => setQr('')} />
      <ApplicationLinkWorkflowModal activity={generator.activity} />
    </div>
  );
}
