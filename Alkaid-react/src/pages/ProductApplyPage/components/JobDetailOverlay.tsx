import { DetailOverlay, type DetailPresentation } from '../../../components/common';
import type { ProductApplicationResult } from '../model/types';
import JobDetailContent from './JobDetailContent';

interface JobDetailOverlayProps {
  result: ProductApplicationResult | null;
  onClose: () => void;
  presentation?: DetailPresentation;
}

export default function JobDetailOverlay({
  result,
  onClose,
  presentation = 'drawer',
}: JobDetailOverlayProps) {
  return (
    <DetailOverlay
      presentation={presentation}
      title="执行详情"
      width={720}
      open={Boolean(result)}
      onClose={onClose}
    >
      {result ? <JobDetailContent result={result} /> : null}
    </DetailOverlay>
  );
}
