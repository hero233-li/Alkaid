import type {
  VerificationTask,
} from '../types';

export function allVerificationItemsCompleted(task: VerificationTask | null) {
  return Boolean(task?.items.length && task.items.every((item) => item.status === 'completed'));
}
