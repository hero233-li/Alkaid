import { useEffect, useRef, useState } from 'react';
import { message } from 'antd';
import { pollCardJob, submitCardAction, submitCardSearch } from '../api/cardStatus';
import { cardActionLabel } from '../config/cardStatusConfig';
import type {
  CardAction,
  CardActionValues,
  CardActivity,
  CardJob,
  CardRecord,
  CardSearchValues,
} from '../types';

export function useCardStatusProcessing() {
  const [records, setRecords] = useState<CardRecord[]>([]);
  const [activity, setActivity] = useState<CardActivity | null>(null);
  const [password, setPassword] = useState('');
  const controllerRef = useRef<AbortController | null>(null);
  useEffect(() => () => controllerRef.current?.abort(), []);

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
    submitter: () => Promise<{ id: number; status: CardJob['status']; progress: number }>,
  ) => {
    const submitted = await submitter();
    return pollCardJob(
      submitted.id,
      (job) =>
        setActivity({
          jobId: submitted.id,
          label,
          status: job.status,
          progress: job.progress,
          currentStep: job.currentStep,
        }),
      { signal: controller.signal },
    );
  };
  const update = (card: CardRecord) =>
    setRecords((current) => current.map((item) => (item.cardNo === card.cardNo ? card : item)));
  const search = async (values: CardSearchValues) => {
    const controller = start('正在查询客户卡片');
    setRecords([]);
    try {
      const job = await run(controller, '正在查询客户卡片', () => submitCardSearch(values));
      setRecords(job.result.cards ?? []);
    } catch (error) {
      if (!isCancelled(error)) message.error(error instanceof Error ? error.message : '查询失败');
    } finally {
      finish(controller);
    }
  };
  const execute = async (card: CardRecord, action: CardAction, values: CardActionValues) => {
    const label = `正在${cardActionLabel(action)}`;
    const controller = start(label);
    try {
      const job = await run(controller, label, () => submitCardAction(card.cardNo, action, values));
      const result = job.result.actionResult;
      if (!result) throw new Error('卡片操作结果缺少 actionResult');
      update(result.card);
      message.success(result.message);
      if (result.password) setPassword(result.password);
      return true;
    } catch (error) {
      if (!isCancelled(error)) message.error(error instanceof Error ? error.message : '操作失败');
      return false;
    } finally {
      finish(controller);
    }
  };
  return { records, activity, busy: Boolean(activity), password, setPassword, search, execute };
}

function isCancelled(error: unknown) {
  return error instanceof Error && (error.name === 'AbortError' || error.name === 'CanceledError');
}
