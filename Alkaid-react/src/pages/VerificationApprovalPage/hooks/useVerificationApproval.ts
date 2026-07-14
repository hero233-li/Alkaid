import { useMemo, useRef, useState } from 'react';
import { message } from 'antd';
import {
  claimVerificationTask,
  pollVerificationJob,
  refreshVerificationTask,
  returnVerificationTask,
  searchVerificationTask,
  submitVerificationAction,
  updateVerificationItem,
} from '../api/verificationApproval';
import { verificationQuickActions } from '../config/verificationApprovalConfig';
import { allVerificationItemsCompleted } from '../model/taskModel';
import type {
  VerificationActionDefinition,
  VerificationJobDetail,
  VerificationJobSubmission,
  VerificationOperation,
  VerificationQuickAction,
  VerificationSearchSubmission,
  VerificationTask,
  VerificationWorkflowActivity,
} from '../types';

function extractTask(detail: VerificationJobDetail): VerificationTask | null {
  const value = detail.result.task;
  if (value === null) return null;
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('核实审批 Job 结果缺少 task');
  }
  return value as VerificationTask;
}

export function useVerificationApproval() {
  const [task, setTask] = useState<VerificationTask | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [searching, setSearching] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [activity, setActivity] = useState<VerificationWorkflowActivity | null>(null);
  const [pendingAction, setPendingAction] = useState<VerificationActionDefinition | null>(null);
  const runningRef = useRef(false);
  const allCompleted = useMemo(() => allVerificationItemsCompleted(task), [task]);

  async function runWorkflow(
    operation: VerificationOperation,
    label: string,
    submit: () => Promise<VerificationJobSubmission>,
  ) {
    if (runningRef.current) {
      throw new Error('已有核实审批任务正在执行，请稍候');
    }
    runningRef.current = true;
    setActivity({ operation, label, status: 'submitting', progress: 0 });
    try {
      const submitted = await submit();
      setActivity({
        jobId: submitted.id,
        operation,
        label,
        status: submitted.status,
        progress: submitted.progress,
      });
      return await pollVerificationJob(submitted.id, (detail) => {
        setActivity({
          jobId: detail.id,
          operation,
          label,
          status: detail.status,
          progress: detail.progress,
        });
      });
    } finally {
      runningRef.current = false;
      setActivity(null);
    }
  }

  const search = async (submission: VerificationSearchSubmission) => {
    setSearching(true);
    try {
      const detail = await runWorkflow(
        'search',
        '正在查询核实审批任务',
        () => searchVerificationTask(submission),
      );
      setTask(extractTask(detail));
      setHasSearched(true);
    } catch (error) {
      message.error(error instanceof Error ? error.message : '核实审批查询失败');
    } finally {
      setSearching(false);
    }
  };

  const claim = async () => {
    if (!task || updating) return;
    await updateTask('claim', '正在领取核实审批任务', () => claimVerificationTask(task), '任务领取成功');
  };

  const returnToPool = async () => {
    if (!task || updating) return;
    await updateTask(
      'return',
      '正在退回核实审批任务',
      () => returnVerificationTask(task),
      '任务已退回任务池',
    );
  };

  async function refreshFromContext(context: VerificationTask) {
    const detail = await runWorkflow(
      'refresh',
      '正在刷新核实审批状态',
      () => refreshVerificationTask(context),
    );
    const refreshed = extractTask(detail);
    if (!refreshed) throw new Error('刷新结果缺少核实审批任务');
    setTask(refreshed);
    return refreshed;
  }

  const refresh = async () => {
    if (!task || updating || refreshing) return;
    setRefreshing(true);
    try {
      await refreshFromContext(task);
      message.success('核实审批状态已刷新');
    } catch (error) {
      message.error(error instanceof Error ? error.message : '核实审批刷新失败');
    } finally {
      setRefreshing(false);
    }
  };

  const setItemCompleted = async (itemId: string, completed: boolean) => {
    if (!task || updating) return;
    await updateTask(
      'item-update',
      completed ? '正在完成核实项' : '正在取消核实项完成状态',
      () => updateVerificationItem(task, itemId, completed ? 'completed' : 'pending'),
      completed ? '核实项已完成' : '核实项已恢复为未完成',
      true,
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
      'action',
      `正在执行${action.label}`,
      () => submitVerificationAction(task, action.key),
      `${action.label}操作已完成`,
    );
    if (succeeded) setPendingAction(null);
  };

  async function updateTask(
    operation: VerificationOperation,
    label: string,
    submit: () => Promise<VerificationJobSubmission>,
    successMessage: string,
    refreshAfter = false,
  ) {
    setUpdating(true);
    try {
      const detail = await runWorkflow(operation, label, submit);
      const updatedTask = extractTask(detail);
      if (!updatedTask) throw new Error('核实审批操作结果缺少 task');
      setTask(updatedTask);
      message.success(successMessage);
      if (refreshAfter) {
        try {
          await refreshFromContext(updatedTask);
        } catch (refreshError) {
          message.warning(
            refreshError instanceof Error
              ? `操作已完成，但自动刷新失败：${refreshError.message}`
              : '操作已完成，但自动刷新失败',
          );
        }
      }
      return true;
    } catch (error) {
      message.error(error instanceof Error ? error.message : '核实审批操作失败');
      return false;
    } finally {
      setUpdating(false);
    }
  }

  return {
    task,
    hasSearched,
    searching,
    refreshing,
    updating,
    activity,
    pendingAction,
    allCompleted,
    search,
    clear: () => {
      setTask(null);
      setHasSearched(false);
    },
    claim,
    returnToPool,
    refresh,
    setItemCompleted,
    openAction,
    closeAction: () => setPendingAction(null),
    confirmAction,
  };
}
