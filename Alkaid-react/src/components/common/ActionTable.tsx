import type { ReactNode } from 'react';
import { Card, Table, type CardProps, type TableProps } from 'antd';

export interface ActionColumnOptions {
  title?: ReactNode;
  width?: number | string;
  fixed?: 'left' | 'right';
}

export interface ActionTableProps<TRecord extends object> {
  title?: ReactNode;
  contained?: boolean;
  rowKey: NonNullable<TableProps<TRecord>['rowKey']>;
  dataSource: TRecord[];
  columns: NonNullable<TableProps<TRecord>['columns']>;
  renderActions?: (record: TRecord) => ReactNode;
  actionColumn?: ActionColumnOptions;
  cardProps?: Omit<CardProps, 'title' | 'children'>;
  tableProps?: Omit<TableProps<TRecord>, 'rowKey' | 'dataSource' | 'columns'>;
}

export default function ActionTable<TRecord extends object>({
  title,
  contained = true,
  rowKey,
  dataSource,
  columns,
  renderActions,
  actionColumn,
  cardProps,
  tableProps,
}: ActionTableProps<TRecord>) {
  const resolvedColumns: NonNullable<TableProps<TRecord>['columns']> = renderActions
    ? [
        ...columns,
        {
          title: actionColumn?.title ?? '操作',
          key: '__actions',
          width: actionColumn?.width,
          fixed: actionColumn?.fixed,
          render: (_, record) => renderActions(record),
        },
      ]
    : columns;

  const table = (
    <Table<TRecord>
      {...tableProps}
      rowKey={rowKey}
      dataSource={dataSource}
      columns={resolvedColumns}
    />
  );

  return contained ? <Card {...cardProps} title={title}>{table}</Card> : table;
}
