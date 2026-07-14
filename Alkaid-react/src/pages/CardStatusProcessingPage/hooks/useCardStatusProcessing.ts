import { useEffect, useRef, useState } from 'react';
import { message } from 'antd';
import { pollCardJob, submitCardAction, submitCardSearch } from '../api/cardStatus';
import { cardActionLabel } from '../config/cardStatusConfig';
import type { CardAction, CardActionValues, CardActivity, CardJob, CardRecord, CardSearchValues } from '../types';

export function useCardStatusProcessing() {
  const [records, setRecords] = useState<CardRecord[]>([]);
  const [activity, setActivity] = useState<CardActivity | null>(null);
  const [password, setPassword] = useState('');
  const controllerRef = useRef<AbortController | null>(null);
  useEffect(() => () => controllerRef.current?.abort(), []);

  const run = async (label: string, submitter: () => Promise<{ id: number; status: CardJob['status']; progress: number }>) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setActivity({ label, status: 'submitting', progress: 0 });
    const submitted = await submitter();
    return pollCardJob(
      submitted.id,
      (job) => setActivity({ jobId: submitted.id, label, status: job.status, progress: job.progress, currentStep: job.currentStep }),
      { signal: controller.signal },
    );
  };
  const update = (card: CardRecord) => setRecords((current) => current.map((item) => item.cardNo === card.cardNo ? card : item));
  const search = async (values: CardSearchValues) => {
    setRecords([]);
    try {
      const job = await run('正在查询客户卡片', () => submitCardSearch(values));
      setRecords((job.result.cards as CardRecord[]) ?? []);
    } catch (error) {
      if (!isCancelled(error)) message.error(error instanceof Error ? error.message : '查询失败');
    } finally { setActivity(null); }
  };
  const execute = async (card: CardRecord, action: CardAction, values: CardActionValues) => {
    try {
      const job = await run(`正在${cardActionLabel(action)}`, () => submitCardAction(card.cardNo, action, values));
      const result = job.result.actionResult as { card: CardRecord; message: string; password?: string };
      update(result.card); message.success(result.message); if (result.password) setPassword(result.password);
      return true;
    } catch (error) {
      if (!isCancelled(error)) message.error(error instanceof Error ? error.message : '操作失败');
      return false;
    } finally { setActivity(null); }
  };
  return { records, activity, busy: Boolean(activity), password, setPassword, search, execute };
}

function isCancelled(error: unknown) {
  return error instanceof Error && (error.name === 'AbortError' || error.name === 'CanceledError');
}
