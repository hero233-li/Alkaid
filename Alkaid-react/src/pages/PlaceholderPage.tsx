import { Card, Empty, Typography } from 'antd';

interface PlaceholderPageProps {
  title: string;
}

export default function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <div className="page-surface">
      <Typography.Title level={3}>{title}</Typography.Title>
      <Card>
        <Empty description="待实现" />
      </Card>
    </div>
  );
}
