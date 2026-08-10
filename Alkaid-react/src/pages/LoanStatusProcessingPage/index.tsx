import { Form } from 'antd';
import { useState } from 'react';
import LoanActionModal from './components/LoanActionModal';
import LoanDetailDrawer from './components/LoanDetailDrawer';
import LoanRepaymentPlanModal from './components/LoanRepaymentPlanModal';
import LoanResultList from './components/LoanResultList';
import LoanSearchForm from './components/LoanSearchForm';
import LoanVoucherModal from './components/LoanVoucherModal';
import LoanWorkflowModal from './components/LoanWorkflowModal';
import { useLoanStatusProcessing } from './hooks/useLoanStatusProcessing';
import type { LoanAction, LoanActionValues, LoanSearchValues, LoanVoucher } from './types';
import './styles.css';
export default function LoanStatusProcessingPage() {
  const [form] = Form.useForm<LoanSearchValues>();
  const state = useLoanStatusProcessing();
  const [selectedRowKey, setSelectedRowKey] = useState<string | null>(null);
  const [action, setAction] = useState<LoanAction | null>(null);
  const [voucher, setVoucher] = useState<LoanVoucher | null>(null);
  const [planVoucher, setPlanVoucher] = useState<LoanVoucher | null>(null);
  const selected = state.records.find((item) => item.rowKey === selectedRowKey) ?? null;
  const closeAction = () => setAction(null);
  const closeDrawer = () => {
    setAction(null);
    setVoucher(null);
    setPlanVoucher(null);
    setSelectedRowKey(null);
  };
  const search = async (v: LoanSearchValues) => {
    closeDrawer();
    await state.search(v);
  };
  const execute = async (v: LoanActionValues) => {
    if (selected && action && (await state.execute(selected, action, v))) {
      closeAction();
      setVoucher(null);
    }
  };
  const resume = async () => {
    if (selected && (await state.resume(selected))) closeAction();
  };
  const queryPlan = async (current: LoanVoucher) => {
    if (!selected) return;
    const result = await state.queryRepaymentPlan(selected, current.voucherNo);
    if (result) setPlanVoucher(result);
  };
  const interrupted =
    selected &&
    action &&
    state.interrupted?.cardNo === selected.cardNo &&
    state.interrupted.action === action
      ? state.interrupted
      : null;
  return (
    <div className="loan-status-page">
      <LoanSearchForm form={form} busy={state.busy} onSubmit={(v) => void search(v)} />
      <LoanResultList
        records={state.records}
        busy={state.busy}
        onOpen={(record) => setSelectedRowKey(record.rowKey)}
      />
      <LoanDetailDrawer
        record={selected}
        busy={state.busy}
        onClose={closeDrawer}
        onAction={setAction}
        onVoucherOpen={setVoucher}
        onPlanOpen={(current) => void queryPlan(current)}
      />
      <LoanVoucherModal
        record={selected}
        voucher={voucher}
        open={!action}
        busy={state.busy}
        onClose={() => setVoucher(null)}
        onAction={setAction}
      />
      <LoanRepaymentPlanModal
        record={selected}
        voucher={planVoucher}
        onClose={() => setPlanVoucher(null)}
      />
      <LoanActionModal
        card={selected}
        voucher={voucher}
        action={action}
        interrupted={interrupted}
        onClose={closeAction}
        onSubmit={(v) => void execute(v)}
        onResume={() => void resume()}
      />
      <LoanWorkflowModal activity={state.activity} />
    </div>
  );
}
