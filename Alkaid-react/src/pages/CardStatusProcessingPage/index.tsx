import { Form } from 'antd';
import { useState } from 'react';
import CardActionModal from './components/CardActionModal';
import CardResultList from './components/CardResultList';
import CardSearchForm from './components/CardSearchForm';
import CardWorkflowModal from './components/CardWorkflowModal';
import PasswordResultModal from './components/PasswordResultModal';
import { useCardStatusProcessing } from './hooks/useCardStatusProcessing';
import type { CardAction, CardActionValues, CardSearchValues } from './types';
import './styles.css';

export default function CardStatusProcessingPage() {
  const [form] = Form.useForm<CardSearchValues>();
  const state = useCardStatusProcessing();
  const [selectedCardNo, setSelectedCardNo] = useState<string | null>(null);
  const [action, setAction] = useState<CardAction | null>(null);
  const selected = state.records.find((record) => record.cardNo === selectedCardNo) ?? null;
  const close = () => setAction(null);
  const search = async (values: CardSearchValues) => {
    setSelectedCardNo(null);
    setAction(null);
    await state.search(values);
  };
  const execute = async (values: CardActionValues) => {
    if (selected && action && (await state.execute(selected, action, values))) close();
  };

  return (
    <div className="card-status-page">
      <CardSearchForm form={form} busy={state.busy} onSubmit={(values) => void search(values)} />
      <CardResultList
        records={state.records}
        selectedCardNo={selectedCardNo}
        busy={state.busy}
        onSelect={(record) => setSelectedCardNo(record?.cardNo ?? null)}
        onAction={setAction}
      />
      <CardActionModal
        card={selected}
        action={action}
        onClose={close}
        onSubmit={(values) => void execute(values)}
      />
      <PasswordResultModal password={state.password} onClose={() => state.setPassword('')} />
      <CardWorkflowModal activity={state.activity} />
    </div>
  );
}
