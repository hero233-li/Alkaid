import { act, renderHook } from '@testing-library/react';
import { message } from 'antd';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from '../api/verificationApproval';
import type { VerificationTask } from '../types';
import { useVerificationApproval } from './useVerificationApproval';

vi.mock('antd', () => ({
  message: { success: vi.fn(), warning: vi.fn(), error: vi.fn() },
}));
vi.mock('../api/verificationApproval');

const baseTask: VerificationTask = {
  id: 'VERIFY-1',
  contractNo: 'HT-1',
  ownershipStatus: 'claimed',
  taskStatus: '待核实',
  node: '核实',
  tellerNo: 'T1',
  organizationNo: 'ORG1',
  productName: '产品 B',
  items: [{ id: 'identity', title: '身份核实', status: 'pending' }],
};

const submission = (id: number) => ({
  id,
  status: 'pending' as const,
  stage: 'pending',
  progress: 0,
});
const detail = (id: number, task: VerificationTask) => ({
  id,
  status: 'success' as const,
  stage: 'completed',
  progress: 100,
  result: {
    task,
    contextProof: { sourceJobId: id, version: 1, digest: 'a'.repeat(64) },
  },
});

describe('useVerificationApproval', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.searchVerificationTask).mockResolvedValue(submission(1));
    vi.mocked(api.updateVerificationItem).mockResolvedValue(submission(2));
    vi.mocked(api.refreshVerificationTask).mockResolvedValue(submission(3));
    vi.mocked(api.pollVerificationJob)
      .mockResolvedValueOnce(detail(1, baseTask))
      .mockResolvedValueOnce(
        detail(2, { ...baseTask, items: [{ ...baseTask.items[0], status: 'completed' }] }),
      )
      .mockResolvedValueOnce(
        detail(3, {
          ...baseTask,
          taskStatus: '已刷新',
          items: [{ ...baseTask.items[0], status: 'completed' }],
        }),
      );
  });

  it('automatically refreshes with the complete returned context after an item update', async () => {
    const { result } = renderHook(() => useVerificationApproval());

    await act(() =>
      result.current.search({
        environment: 'UAT1',
        category: '合同核实',
        contractNo: 'HT-1',
      }),
    );
    await act(() => result.current.setItemCompleted('identity', true));

    expect(api.refreshVerificationTask).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 'VERIFY-1',
        items: [expect.objectContaining({ status: 'completed' })],
      }),
      expect.objectContaining({ sourceJobId: 2, version: 1 }),
    );
    expect(result.current.task?.taskStatus).toBe('已刷新');
  });

  it('keeps the successful item result when the following automatic refresh fails', async () => {
    vi.mocked(api.pollVerificationJob)
      .mockReset()
      .mockResolvedValueOnce(detail(1, baseTask))
      .mockResolvedValueOnce(
        detail(2, {
          ...baseTask,
          items: [{ ...baseTask.items[0], status: 'completed' }],
        }),
      )
      .mockRejectedValueOnce(new Error('刷新接口暂不可用'));
    const { result } = renderHook(() => useVerificationApproval());

    await act(() =>
      result.current.search({
        environment: 'UAT1',
        category: '合同核实',
        contractNo: 'HT-1',
      }),
    );
    await act(() => result.current.setItemCompleted('identity', true));

    expect(result.current.task?.items[0].status).toBe('completed');
    expect(message.warning).toHaveBeenCalledWith(expect.stringContaining('刷新接口暂不可用'));
  });
});
