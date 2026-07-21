import { useEffect, useMemo, useRef, useState } from 'react';
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
  VerificationContextProof,
  VerificationJobDetail,
  VerificationJobSubmission,
  VerificationOperation,
  VerificationQuickAction,
  VerificationSearchSubmission,
  VerificationTask,
  VerificationWorkflowActivity,
} from '../types';

function extractTaskContext(detail: VerificationJobDetail): {
  task: VerificationTask | null;
  proof: VerificationContextProof | null;
} {
  const value = detail.result.task;
  if (value === null) return { task: null, proof: null };
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('核实审批 Job 结果缺少 task');
  }
  const proof = detail.result.contextProof;
  if (!proof || typeof proof !== 'object' || Array.isArray(proof)) {
    throw new Error('核实审批 Job 结果缺少 contextProof');
  }
  return { task: value as VerificationTask, proof: proof as VerificationContextProof };
}

export function useVerificationApproval() {
  const [task, setTask] = useState<VerificationTask | null>(null);
  const [contextProof, setContextProof] = useState<VerificationContextProof | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [searching, setSearching] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [activity, setActivity] = useState<VerificationWorkflowActivity | null>(null);
  const [pendingAction, setPendingAction] = useState<VerificationActionDefinition | null>(null);
  const runningRef = useRef(false);
  const pollControllerRef = useRef<AbortController | null>(null);
  const allCompleted = useMemo(() => allVerificationItemsCompleted(task), [task]);

  useEffect(
    () => () => {
      pollControllerRef.current?.abort();
    },
    [],
  );

  async function runWorkflow(
    operation: VerificationOperation,
    label: string,
    submit: () => Promise<VerificationJobSubmission>,
  ) {
    if (runningRef.current) {
      throw new Error('已有核实审批任务正在执行，请稍候');
    }
    runningRef.current = true;
    const controller = new AbortController();
    pollControllerRef.current = controller;
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
      return await pollVerificationJob(
        submitted.id,
        (detail) => {
          setActivity({
            jobId: detail.id,
            operation,
            label,
            status: detail.status,
            progress: detail.progress,
          });
        },
        { signal: controller.signal },
      );
    } finally {
      runningRef.current = false;
      if (pollControllerRef.current === controller) pollControllerRef.current = null;
      setActivity(null);
    }
  }

  const search = async (submission: VerificationSearchSubmission) => {
    setSearching(true);
    try {
      const detail = await runWorkflow('search', '正在查询核实审批任务', () =>
        searchVerificationTask(submission),
      );
      const next = extractTaskContext(detail);
      setTask(next.task);
      setContextProof(next.proof);
      setHasSearched(true);
    } catch (error) {
      if (!isCancelled(error)) {
        message.error(error instanceof Error ? error.message : '核实审批查询失败');
      }
    } finally {
      setSearching(false);
    }
  };

  const claim = async () => {
    if (!task || !contextProof || updating) return;
    await updateTask(
      'claim',
      '正在领取核实审批任务',
      () => claimVerificationTask(task, contextProof),
      '任务领取成功',
    );
  };

  const returnToPool = async () => {
    if (!task || !contextProof || updating) return;
    await updateTask(
      'return',
      '正在退回核实审批任务',
      () => returnVerificationTask(task, contextProof),
      '任务已退回任务池',
    );
  };

  async function refreshFromContext(context: VerificationTask, proof: VerificationContextProof) {
    const detail = await runWorkflow('refresh', '正在刷新核实审批状态', () =>
      refreshVerificationTask(context, proof),
    );
    const refreshed = extractTaskContext(detail);
    if (!refreshed.task || !refreshed.proof) throw new Error('刷新结果缺少核实审批任务');
    setTask(refreshed.task);
    setContextProof(refreshed.proof);
    return refreshed;
  }

  const refresh = async () => {
    if (!task || !contextProof || updating || refreshing) return;
    setRefreshing(true);
    try {
      await refreshFromContext(task, contextProof);
      message.success('核实审批状态已刷新');
    } catch (error) {
      if (!isCancelled(error)) {
        message.error(error instanceof Error ? error.message : '核实审批刷新失败');
      }
    } finally {
      setRefreshing(false);
    }
  };

  const setItemCompleted = async (itemId: string, completed: boolean) => {
    if (!task || !contextProof || updating) return;
    await updateTask(
      'item-update',
      completed ? '正在完成核实项' : '正在取消核实项完成状态',
      () => updateVerificationItem(task, contextProof, itemId, completed ? 'completed' : 'pending'),
      completed ? '核实项已完成' : '核实项已恢复为未完成',
      true,
    );
  };

  const openAction = (action: VerificationQuickAction) => {
    const definition = verificationQuickActions.find((item) => item.key === action) ?? null;
    setPendingAction(definition);
  };

  const confirmAction = async () => {
    if (!pendingAction || !task || !contextProof || updating) return;
    const action = pendingAction;
    const succeeded = await updateTask(
      'action',
      `正在执行${action.label}`,
      () => submitVerificationAction(task, contextProof, action.key),
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
      const updated = extractTaskContext(detail);
      if (!updated.task || !updated.proof) throw new Error('核实审批操作结果缺少 task');
      setTask(updated.task);
      setContextProof(updated.proof);
      message.success(successMessage);
      if (refreshAfter) {
        try {
          await refreshFromContext(updated.task, updated.proof);
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
      if (!isCancelled(error)) {
        message.error(error instanceof Error ? error.message : '核实审批操作失败');
      }
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
      setContextProof(null);
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

function isCancelled(error: unknown) {
  return error instanceof Error && (error.name === 'AbortError' || error.name === 'CanceledError');
}
