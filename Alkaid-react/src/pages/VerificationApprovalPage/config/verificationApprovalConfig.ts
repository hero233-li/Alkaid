import type { VerificationActionDefinition } from '../types';

export const verificationQuickActions: VerificationActionDefinition[] = [
  {
    key: 'complete',
    label: '一键完成',
    title: '确认一键完成？',
    description: '确认后，当前任务下的全部核实项将标记为完成。',
  },
  {
    key: 'supplement',
    label: '一键补件',
    title: '确认发起一键补件？',
    description: '确认后，任务将进入待补件状态。',
  },
  {
    key: 'submit',
    label: '一键提交',
    title: '确认提交当前任务？',
    description: '全部核实项完成后，可将任务提交到下一节点。',
  },
  {
    key: 'approval-submit',
    label: '一键审批提交',
    title: '确认一键审批提交？',
    description: '确认后，将以审批通过结果提交当前任务。',
  },
];
