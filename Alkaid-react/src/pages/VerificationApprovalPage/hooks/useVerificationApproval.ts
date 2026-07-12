import { useMemo, useState } from 'react';
import { message } from 'antd';
import {
  claimVerificationTask,
  returnVerificationTask,
  searchVerificationTask,
  submitVerificationAction,
  updateVerificationItem,
} from '../api/verificationApproval';
import { verificationQuickActions } from '../config/verificationApprovalConfig';
import { allVerificationItemsCompleted } from '../model/taskModel';
import type {
  VerificationActionDefinition,
  VerificationQuickAction,
  VerificationSearchSubmission,
  VerificationTask,
} from '../types';

export function useVerificationApproval() {
  const [task, setTask] = useState<VerificationTask | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [searching, setSearching] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [pendingAction, setPendingAction] = useState<VerificationActionDefinition | null>(null);
  const allCompleted = useMemo(() => allVerificationItemsCompleted(task), [task]);

  const search = async (submission: VerificationSearchSubmission) => {
    setSearching(true);
    try {
      setTask(await searchVerificationTask(submission));
      setHasSearched(true);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '核实审批查询失败');
    } finally {
      setSearching(false);
    }
  };

  const claim = async () => {
    if (!task || updating) return;
    await updateTask(() => claimVerificationTask(task.id), '任务领取成功');
  };

  const returnToPool = async () => {
    if (!task || updating) return;
    await updateTask(() => returnVerificationTask(task.id), '任务已退回任务池');
  };

  const setItemCompleted = async (itemId: string, completed: boolean) => {
    if (!task || updating) return;
    await updateTask(
      () => updateVerificationItem(task.id, itemId, completed ? 'completed' : 'pending'),
      completed ? '核实项已完成' : '核实项已恢复为未完成',
    );
  };

  const openAction = (action: VerificationQuickAction) => {
    const definition = verificationQuickActions.find((item) => item.key === action) ?? null;
    setPendingAction(definition);
  };

  const confirmAction = async () => {
    if (!pendingAction || !task || updating) return;
    const action = pendingAction;
    const succeeded = await updateTask(
      () => submitVerificationAction(task.id, action.key),
      `${action.label}操作已完成`,
    );
    if (succeeded) setPendingAction(null);
  };

  const updateTask = async (
    operation: () => Promise<VerificationTask>,
    successMessage: string,
  ) => {
    setUpdating(true);
    try {
      setTask(await operation());
      message.success(successMessage);
      return true;
    } catch (error) {
      message.error(error instanceof Error ? error.message : '核实审批操作失败');
      return false;
    } finally {
      setUpdating(false);
    }
  };

  return {
    task,
    hasSearched,
    searching,
    updating,
    pendingAction,
    allCompleted,
    search,
    clear: () => {
      setTask(null);
      setHasSearched(false);
    },
    claim,
    returnToPool,
    setItemCompleted,
    openAction,
    closeAction: () => setPendingAction(null),
    confirmAction,
  };
}
