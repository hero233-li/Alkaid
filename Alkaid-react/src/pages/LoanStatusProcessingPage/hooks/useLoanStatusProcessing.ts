import { useEffect, useRef, useState } from 'react';
import { message, Modal } from 'antd';
import { pollLoanJob, submitLoanAction, submitLoanSearch } from '../api/loanStatus';
import { loanActionLabel } from '../config/loanStatusConfig';
import type {
  LoanAction,
  LoanActionValues,
  LoanActivity,
  LoanCardRecord,
  LoanInterruptedFlow,
  LoanJob,
  LoanResultRecord,
  LoanSearchValues,
  LoanVoucher,
} from '../types';
const numberValue = (value: unknown) => {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
};
const loanStatus = (value: unknown): LoanResultRecord['loanStatus'] =>
  value === '已生效' || value === '已结束' || value === '未签署' ? value : '未签署';
const normalizeVoucher = (voucher: LoanVoucher): LoanVoucher => {
  const nextRepaymentDate = voucher.nextRepaymentDate || voucher.dueDate || '-';
  const status = voucher.status === '正常' ? '使用中' : voucher.status;
  const outstandingAmount = numberValue(voucher.outstandingAmount);
  const repaymentPlan =
    Array.isArray(voucher.repaymentPlan) && voucher.repaymentPlan.length
      ? voucher.repaymentPlan.map((item) => ({
          ...item,
          status:
            item.status === '使用中' || item.status === '已结清' || item.status === '逾期'
              ? item.status
              : '使用中',
          principal: numberValue(item.principal),
          interest: numberValue(item.interest),
          totalAmount: numberValue(item.totalAmount),
        }))
      : [
          {
            installmentNo: 1,
            repaymentDate: nextRepaymentDate,
            principal: outstandingAmount,
            interest: 0,
            totalAmount: outstandingAmount,
            status,
          },
        ];
  return {
    ...voucher,
    status,
    nextRepaymentDate,
    drawAmount: numberValue(voucher.drawAmount),
    outstandingAmount,
    overdueAmount: numberValue(voucher.overdueAmount),
    repaidPrincipal: numberValue(voucher.repaidPrincipal),
    repaidInterest: numberValue(voucher.repaidInterest),
    outstandingPrincipal: Number.isFinite(Number(voucher.outstandingPrincipal))
      ? Number(voucher.outstandingPrincipal)
      : outstandingAmount,
    outstandingInterest: numberValue(voucher.outstandingInterest),
    repaymentPlan,
  };
};
const toResultRows = (cards: LoanCardRecord[]): LoanResultRecord[] =>
  cards.reduce<LoanResultRecord[]>((rows, card) => {
    const common = {
      environment: card.environment,
      customerNo: card.customerNo,
      customerName: card.customerName,
      certificateNo: card.certificateNo,
      phone: card.phone,
      cardNo: card.cardNo,
      balance: numberValue(card.balance),
      cardStatus: card.status,
      freezeStatus: card.freezeStatus,
      quotaNo: card.quotaNo,
      signDate: '-',
      organizationNo: '-',
      relationshipManager: '-',
      accountingDate: '-',
      graceDays: 0,
      coreRate: 0,
      generalAccountingDate: '-',
      parameterAccountingDate: '-',
    };
    if (!card.loans.length) {
      rows.push({
        ...common,
        rowKey: `${card.cardNo}:none`,
        contractNo: '',
        loanStatus: '无关联合同信息',
        freezeStatus: '-',
        overdueStatus: '-',
        debt: 0,
        overdueDebt: 0,
        creditLimit: 0,
        usedCredit: 0,
        availableCredit: 0,
        vouchers: [],
      });
      return rows;
    }
    rows.push(
      ...card.loans.map<LoanResultRecord>((loan) => {
        const status = loanStatus(loan.status);
        const creditLimit = numberValue(loan.creditLimit);
        const usedCredit = numberValue(loan.usedCredit);
        const vouchers = Array.isArray(loan.vouchers) ? loan.vouchers.map(normalizeVoucher) : [];
        return {
          ...common,
          rowKey: loan.contractNo,
          contractNo: loan.contractNo,
          quotaNo: loan.quotaNo || card.quotaNo || '-',
          signDate: status === '未签署' ? '-' : loan.signDate || '-',
          organizationNo: loan.organizationNo || '-',
          relationshipManager: loan.relationshipManager || '-',
          accountingDate: loan.accountingDate || '-',
          graceDays: numberValue(loan.graceDays),
          coreRate: numberValue(loan.coreRate),
          generalAccountingDate: loan.generalAccountingDate || '-',
          parameterAccountingDate: loan.parameterAccountingDate || '-',
          loanStatus: status,
          freezeStatus: status === '未签署' ? '-' : loan.freezeStatus === '是' ? '是' : '否',
          overdueStatus: status === '未签署' ? '-' : loan.overdueStatus === '是' ? '是' : '否',
          debt: numberValue(loan.debt),
          overdueDebt: numberValue(loan.overdueDebt),
          creditLimit,
          usedCredit,
          availableCredit: Number.isFinite(Number(loan.availableCredit))
            ? Number(loan.availableCredit)
            : Math.max(0, creditLimit - usedCredit),
          vouchers,
        };
      }),
    );
    return rows;
  }, []);
export function useLoanStatusProcessing() {
  const [records, setRecords] = useState<LoanResultRecord[]>([]);
  const [activity, setActivity] = useState<LoanActivity | null>(null);
  const [interrupted, setInterrupted] = useState<LoanInterruptedFlow | null>(null);
  const lastSearch = useRef<LoanSearchValues | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  useEffect(() => () => controllerRef.current?.abort(), []);
  const poll = (id: number, label: string, signal: AbortSignal) =>
    pollLoanJob(
      id,
      (j) =>
        setActivity({
          jobId: id,
          label,
          status: j.status,
          progress: j.progress,
          currentStep: j.currentStep,
        }),
      { signal },
    );
  const start = (label: string) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setActivity({ label, status: 'submitting', progress: 0 });
    return controller;
  };
  const finish = (controller: AbortController) => {
    if (controllerRef.current === controller) {
      controllerRef.current = null;
      setActivity(null);
    }
  };
  const run = async (
    controller: AbortController,
    label: string,
    submitter: () => Promise<{ id: number; status: LoanJob['status']; progress: number }>,
  ) => {
    const s = await submitter();
    return poll(s.id, label, controller.signal);
  };
  const update = (card: LoanCardRecord) =>
    setRecords((current) => {
      const index = current.findIndex((item) => item.cardNo === card.cardNo);
      const next = current.filter((item) => item.cardNo !== card.cardNo);
      next.splice(index < 0 ? next.length : index, 0, ...toResultRows([card]));
      return next;
    });
  const refresh = async () => {
    const searchValues = lastSearch.current;
    if (!searchValues) return;
    const controller = start('正在刷新贷款状态');
    try {
      const j = await run(controller, '正在刷新贷款状态', () => submitLoanSearch(searchValues));
      setRecords(toResultRows(j.result.cards ?? []));
    } catch (e) {
      if (!isCancelled(e))
        message.warning(
          e instanceof Error ? `操作已完成，但刷新失败：${e.message}` : '操作已完成，但刷新失败',
        );
    } finally {
      finish(controller);
    }
  };
  const search = async (v: LoanSearchValues) => {
    const controller = start('正在查询贷款合同');
    lastSearch.current = v;
    setRecords([]);
    try {
      const j = await run(controller, '正在查询贷款合同', () => submitLoanSearch(v));
      setRecords(toResultRows(j.result.cards ?? []));
    } catch (e) {
      if (!isCancelled(e)) message.error(e instanceof Error ? e.message : '查询失败');
    } finally {
      finish(controller);
    }
  };
  const execute = async (card: LoanResultRecord, action: LoanAction, v: LoanActionValues) => {
    const label = `正在${loanActionLabel(action)}`;
    const controller = start(label);
    try {
      const j = await run(controller, label, () => submitLoanAction(card.contractNo, action, v));
      const result = j.result.actionResult;
      if (!result) throw new Error('贷款操作结果缺少 actionResult');
      update(result.card);
      if (action === 'contract-sign') Modal.success({ title: result.message });
      else message.success(result.message);
      setInterrupted(null);
      await refresh();
      return true;
    } catch (e) {
      if (!isCancelled(e)) message.error(e instanceof Error ? e.message : '操作失败');
      return false;
    } finally {
      finish(controller);
    }
  };
  const resume = async (_card?: LoanResultRecord) => false;
  const queryRepaymentPlan = async (
    card: LoanResultRecord,
    voucherNo: string,
  ): Promise<LoanVoucher | null> => {
    const searchValues = lastSearch.current;
    if (!searchValues) return card.vouchers.find((item) => item.voucherNo === voucherNo) ?? null;
    const controller = start('正在查询还款计划');
    try {
      const j = await run(controller, '正在查询还款计划', () => submitLoanSearch(searchValues));
      const rows = toResultRows(j.result.cards ?? []);
      setRecords(rows);
      return (
        rows
          .find((item) => item.contractNo === card.contractNo)
          ?.vouchers.find((item) => item.voucherNo === voucherNo) ?? null
      );
    } catch (e) {
      if (!isCancelled(e)) message.error(e instanceof Error ? e.message : '还款计划查询失败');
      return null;
    } finally {
      finish(controller);
    }
  };
  return {
    records,
    activity,
    busy: Boolean(activity),
    interrupted,
    search,
    execute,
    resume,
    queryRepaymentPlan,
  };
}
function isCancelled(error: unknown) {
  return error instanceof Error && (error.name === 'AbortError' || error.name === 'CanceledError');
}
