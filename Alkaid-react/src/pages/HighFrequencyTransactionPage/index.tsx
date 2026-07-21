import { Form } from 'antd';
import HighFrequencySearchForm from './components/HighFrequencySearchForm';
import HighFrequencyWorkflowModal from './components/HighFrequencyWorkflowModal';
import Risk050009ResultList from './components/Risk050009ResultList';
import { useHighFrequencyTransaction } from './hooks/useHighFrequencyTransaction';
import type { HighFrequencySearchValues } from './types';
import './styles.css';
export default function HighFrequencyTransactionPage() {
  const [form] = Form.useForm<HighFrequencySearchValues>();
  const state = useHighFrequencyTransaction();
  return (
    <div className="page-surface high-frequency-page">
      <HighFrequencySearchForm
        form={form}
        busy={state.busy}
        onSubmit={(values) => void state.query(values)}
      />
      <Risk050009ResultList result={state.result} busy={state.busy} />
      <HighFrequencyWorkflowModal activity={state.activity} />
    </div>
  );
}
