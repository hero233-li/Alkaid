import { useMemo, useState } from 'react';
import { Button, Checkbox, Input, Modal, Rate, Select, Tooltip, Typography } from 'antd';
import {
  ArrowLeft,
  ArrowUpDown,
  Barcode,
  CalendarDays,
  CircleDot,
  Clock3,
  CreditCard,
  Database,
  DollarSign,
  Filter,
  Hash,
  Link,
  ListChecks,
  Mail,
  MapPin,
  Paperclip,
  Percent,
  Pencil,
  Phone,
  Plus,
  Rows3,
  Save,
  Search,
  Settings2,
  Star,
  Trash2,
  Type,
  WrapText,
} from 'lucide-react';
import {
  createDefaultMultidimensionalTableData,
  type MultidimensionalField,
  type MultidimensionalFieldType,
  type MultidimensionalTableData,
  type MultidimensionalTableView,
  type MultidimensionalViewFilter,
} from './model';

const DEFAULT_FILE_NAME = '未命名多维表格';

const FIELD_TYPE_OPTIONS: Array<{ label: string; value: MultidimensionalFieldType }> = [
  { label: '文本', value: 'text' },
  { label: '富文本', value: 'richText' },
  { label: '数字', value: 'number' },
  { label: '日期', value: 'date' },
  { label: '时间', value: 'time' },
  { label: '单选', value: 'select' },
  { label: '多选', value: 'multiSelect' },
  { label: '图片和附件', value: 'attachment' },
  { label: '评分', value: 'rating' },
  { label: '复选框', value: 'checkbox' },
  { label: '百分比', value: 'percentage' },
  { label: '货币', value: 'currency' },
  { label: '进度', value: 'progress' },
  { label: '超链接', value: 'hyperlink' },
  { label: '电话', value: 'phone' },
  { label: '邮箱', value: 'email' },
  { label: '身份证', value: 'idCard' },
  { label: '地址', value: 'address' },
  { label: '条码', value: 'barcode' },
];

interface MultidimensionalTableDesignerProps {
  onBack: () => void;
  onSave: (fileName: string, data: MultidimensionalTableData) => void;
  initialFileName?: string;
  initialData?: MultidimensionalTableData;
}

function createFieldId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `field-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function createViewId() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `view-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function FieldTypeIcon({ type }: { type: MultidimensionalFieldType }) {
  const size = 15;
  if (type === 'number') return <Hash size={size} />;
  if (type === 'date') return <CalendarDays size={size} />;
  if (type === 'time') return <Clock3 size={size} />;
  if (type === 'select') return <CircleDot size={size} />;
  if (type === 'multiSelect') return <ListChecks size={size} />;
  if (type === 'attachment') return <Paperclip size={size} />;
  if (type === 'rating') return <Star size={size} />;
  if (type === 'percentage' || type === 'progress') return <Percent size={size} />;
  if (type === 'currency') return <DollarSign size={size} />;
  if (type === 'hyperlink') return <Link size={size} />;
  if (type === 'phone') return <Phone size={size} />;
  if (type === 'email') return <Mail size={size} />;
  if (type === 'idCard') return <CreditCard size={size} />;
  if (type === 'address') return <MapPin size={size} />;
  if (type === 'barcode') return <Barcode size={size} />;
  return <Type size={size} />;
}

export default function MultidimensionalTableDesigner({
  onBack,
  onSave,
  initialFileName,
  initialData,
}: MultidimensionalTableDesignerProps) {
  const [modalApi, modalContextHolder] = Modal.useModal();
  const [fileName, setFileName] = useState(
    () => initialFileName?.replace(/\.(?:md|markdown)$/i, '') || DEFAULT_FILE_NAME,
  );
  const [fields, setFields] = useState<MultidimensionalField[]>(
    () => initialData?.fields || createDefaultMultidimensionalTableData().fields,
  );
  const [records, setRecords] = useState<string[][]>(
    () => initialData?.records || createDefaultMultidimensionalTableData().records,
  );
  const [tableName, setTableName] = useState(
    () => initialData?.tableName || createDefaultMultidimensionalTableData().tableName,
  );
  const [views, setViews] = useState<MultidimensionalTableView[]>(
    () => initialData?.views || createDefaultMultidimensionalTableData().views,
  );
  const [activeViewId, setActiveViewId] = useState(
    () => initialData?.activeViewId || createDefaultMultidimensionalTableData().activeViewId,
  );
  const [editingViewId, setEditingViewId] = useState<string | null>(null);
  const [viewNameDraft, setViewNameDraft] = useState('');
  const [selectedRows, setSelectedRows] = useState<Set<number>>(new Set());
  const [fieldDialogOpen, setFieldDialogOpen] = useState(false);
  const [editingFieldId, setEditingFieldId] = useState<string | null>(null);
  const [fieldName, setFieldName] = useState('');
  const [fieldType, setFieldType] = useState<MultidimensionalFieldType>('text');
  const [fieldOptions, setFieldOptions] = useState('未开始, 进行中, 已完成');
  const [filterDialogOpen, setFilterDialogOpen] = useState(false);
  const [filterFieldId, setFilterFieldId] = useState('');
  const [filterOperator, setFilterOperator] =
    useState<MultidimensionalViewFilter['operator']>('contains');
  const [filterValue, setFilterValue] = useState('');
  const [sortDialogOpen, setSortDialogOpen] = useState(false);
  const [sortFieldId, setSortFieldId] = useState('');
  const [sortDirection, setSortDirection] = useState<'ascending' | 'descending'>('ascending');
  const activeView = views.find((view) => view.id === activeViewId) || views[0];
  const query = activeView?.query || '';

  const visibleRecords = useMemo(() => {
    const keyword = query.trim().toLocaleLowerCase();
    const result = records
      .map((record, index) => ({ record, index }))
      .filter(({ record }) => {
        if (keyword && !record.join(' ').toLocaleLowerCase().includes(keyword)) return false;
        return (activeView?.filters || []).every((filter) => {
          const fieldIndex = fields.findIndex((field) => field.id === filter.fieldId);
          const value = record[fieldIndex] || '';
          if (filter.operator === 'notEmpty') return Boolean(value.trim());
          if (filter.operator === 'equals') return value === filter.value;
          return value.toLocaleLowerCase().includes(filter.value.toLocaleLowerCase());
        });
      });
    if (!activeView?.sort) return result;
    const fieldIndex = fields.findIndex((field) => field.id === activeView.sort?.fieldId);
    const field = fields[fieldIndex];
    if (fieldIndex < 0) return result;
    const numericField = ['number', 'percentage', 'currency', 'progress', 'rating'].includes(
      field.type,
    );
    return [...result].sort((left, right) => {
      const leftValue = left.record[fieldIndex] || '';
      const rightValue = right.record[fieldIndex] || '';
      const comparison = numericField
        ? (Number(leftValue) || 0) - (Number(rightValue) || 0)
        : leftValue.localeCompare(rightValue, 'zh-CN', { numeric: true });
      return activeView.sort?.direction === 'descending' ? -comparison : comparison;
    });
  }, [activeView, fields, query, records]);

  const updateCell = (rowIndex: number, columnIndex: number, value: string) => {
    setRecords((current) =>
      current.map((record, currentRow) =>
        currentRow === rowIndex
          ? fields.map((_, currentColumn) =>
              currentColumn === columnIndex ? value : record[currentColumn] || '',
            )
          : record,
      ),
    );
  };

  const addRecord = () => {
    setRecords((current) => [...current, fields.map(() => '')]);
  };

  const removeSelectedRecords = () => {
    if (!selectedRows.size) return;
    setRecords((current) => current.filter((_, index) => !selectedRows.has(index)));
    setSelectedRows(new Set());
  };

  const openNewField = () => {
    setEditingFieldId(null);
    setFieldName('');
    setFieldType('text');
    setFieldOptions('未开始, 进行中, 已完成');
    setFieldDialogOpen(true);
  };

  const openFieldSettings = (field: MultidimensionalField) => {
    setEditingFieldId(field.id);
    setFieldName(field.name);
    setFieldType(field.type);
    setFieldOptions(field.options?.join(', ') || '未开始, 进行中, 已完成');
    setFieldDialogOpen(true);
  };

  const saveField = () => {
    const nextField: MultidimensionalField = {
      id: editingFieldId || createFieldId(),
      name: fieldName.trim() || '未命名字段',
      type: fieldType,
      options:
        fieldType === 'select' || fieldType === 'multiSelect'
          ? fieldOptions
              .split(/[,，]/)
              .map((option) => option.trim())
              .filter(Boolean)
          : undefined,
    };
    if (editingFieldId) {
      setFields((current) =>
        current.map((field) => (field.id === editingFieldId ? nextField : field)),
      );
    } else {
      setFields((current) => [...current, nextField]);
      setRecords((current) => current.map((record) => [...record, '']));
    }
    setFieldDialogOpen(false);
  };

  const removeEditingField = () => {
    const fieldIndex = fields.findIndex((field) => field.id === editingFieldId);
    if (fieldIndex < 0 || fields.length <= 1) return;
    setFields((current) => current.filter((field) => field.id !== editingFieldId));
    setRecords((current) =>
      current.map((record) => record.filter((_, columnIndex) => columnIndex !== fieldIndex)),
    );
    setFieldDialogOpen(false);
  };

  const buildTableData = (): MultidimensionalTableData => ({
    tableName: tableName.trim() || '数据表',
    fields,
    records,
    views,
    activeViewId,
  });

  const addView = () => {
    const usedNames = new Set(views.map((view) => view.name));
    let suffix = views.length + 1;
    let name = `表格视图 (${suffix})`;
    while (usedNames.has(name)) {
      suffix += 1;
      name = `表格视图 (${suffix})`;
    }
    const view = { id: createViewId(), name, query: '', filters: [], wrapText: false };
    setViews((current) => [...current, view]);
    setActiveViewId(view.id);
    setEditingViewId(view.id);
    setViewNameDraft(view.name);
  };

  const startRenamingView = (view: MultidimensionalTableView) => {
    setEditingViewId(view.id);
    setViewNameDraft(view.name);
  };

  const finishRenamingView = () => {
    if (!editingViewId) return;
    const resolvedName = viewNameDraft.trim() || '未命名视图';
    setViews((current) =>
      current.map((view) => (view.id === editingViewId ? { ...view, name: resolvedName } : view)),
    );
    setEditingViewId(null);
  };

  const removeView = (view: MultidimensionalTableView) => {
    if (views.length <= 1) return;
    modalApi.confirm({
      title: `删除视图“${view.name}”？`,
      content: '只会删除该视图配置，数据表中的字段和记录不会被删除。',
      okText: '删除视图',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: () => {
        const remaining = views.filter((item) => item.id !== view.id);
        setViews(remaining);
        if (activeViewId === view.id) setActiveViewId(remaining[0].id);
        if (editingViewId === view.id) setEditingViewId(null);
      },
    });
  };

  const updateActiveViewQuery = (value: string) => {
    setViews((current) =>
      current.map((view) => (view.id === activeViewId ? { ...view, query: value } : view)),
    );
  };

  const updateActiveView = (update: Partial<MultidimensionalTableView>) => {
    setViews((current) =>
      current.map((view) => (view.id === activeViewId ? { ...view, ...update } : view)),
    );
  };

  const openFilterDialog = () => {
    const fieldId = filterFieldId || fields[0]?.id || '';
    const existing = activeView?.filters.find((filter) => filter.fieldId === fieldId);
    setFilterFieldId(fieldId);
    setFilterOperator(existing?.operator || 'contains');
    setFilterValue(existing?.value || '');
    setFilterDialogOpen(true);
  };

  const applyFilter = () => {
    if (!filterFieldId) return;
    const nextFilter: MultidimensionalViewFilter = {
      fieldId: filterFieldId,
      operator: filterOperator,
      value: filterOperator === 'notEmpty' ? '' : filterValue,
    };
    updateActiveView({
      filters: [
        ...(activeView?.filters || []).filter((filter) => filter.fieldId !== filterFieldId),
        nextFilter,
      ],
    });
    setFilterDialogOpen(false);
  };

  const clearFilters = () => {
    updateActiveView({ filters: [] });
    setFilterDialogOpen(false);
  };

  const openSortDialog = () => {
    setSortFieldId(activeView?.sort?.fieldId || fields[0]?.id || '');
    setSortDirection(activeView?.sort?.direction || 'ascending');
    setSortDialogOpen(true);
  };

  const applySort = () => {
    if (!sortFieldId) return;
    updateActiveView({ sort: { fieldId: sortFieldId, direction: sortDirection } });
    setSortDialogOpen(false);
  };

  const clearSort = () => {
    updateActiveView({ sort: undefined });
    setSortDialogOpen(false);
  };

  const requestSave = () => {
    if (fileName.trim() && fileName.trim() !== DEFAULT_FILE_NAME) {
      onSave(fileName.trim(), buildTableData());
      return;
    }
    let nextName = '';
    modalApi.confirm({
      title: '保存多维表格',
      content: (
        <Input
          autoFocus
          placeholder="请输入文件名称"
          onChange={(event) => {
            nextName = event.target.value;
          }}
        />
      ),
      okText: '创建文件',
      cancelText: '取消',
      onOk: () => {
        const resolvedName = nextName.trim();
        if (!resolvedName) return Promise.reject(new Error('请输入文件名称'));
        setFileName(resolvedName);
        onSave(resolvedName, buildTableData());
      },
    });
  };

  const handleBack = () => {
    modalApi.confirm({
      title: '是否离开多维表格设计？',
      content: '离开后将丢弃当前文件及所有尚未保存的字段和记录。',
      okText: '丢弃并离开',
      okButtonProps: { danger: true },
      cancelText: '继续编辑',
      onOk: onBack,
    });
  };

  const renderCell = (field: MultidimensionalField, rowIndex: number, columnIndex: number) => {
    const value = records[rowIndex]?.[columnIndex] || '';
    if (['number', 'percentage', 'currency', 'progress'].includes(field.type)) {
      return (
        <input
          className="multidimensional-cell-input"
          type="number"
          min={field.type === 'percentage' || field.type === 'progress' ? 0 : undefined}
          max={field.type === 'percentage' || field.type === 'progress' ? 100 : undefined}
          value={value}
          aria-label={`${rowIndex + 1} ${field.name}`}
          placeholder={
            field.type === 'percentage' || field.type === 'progress'
              ? '0–100'
              : field.type === 'currency'
                ? '0.00'
                : undefined
          }
          onChange={(event) => updateCell(rowIndex, columnIndex, event.target.value)}
        />
      );
    }
    if (field.type === 'date' || field.type === 'time') {
      return (
        <input
          className="multidimensional-cell-input"
          type={field.type}
          value={value}
          aria-label={`${rowIndex + 1} ${field.name}`}
          onChange={(event) => updateCell(rowIndex, columnIndex, event.target.value)}
        />
      );
    }
    if (field.type === 'select') {
      return (
        <Select
          allowClear
          variant="borderless"
          value={value || undefined}
          aria-label={`${rowIndex + 1} ${field.name}`}
          options={(field.options || []).map((option) => ({ label: option, value: option }))}
          onChange={(nextValue) => updateCell(rowIndex, columnIndex, nextValue || '')}
        />
      );
    }
    if (field.type === 'multiSelect') {
      return (
        <Select
          allowClear
          mode="multiple"
          variant="borderless"
          value={value ? value.split(',').filter(Boolean) : []}
          aria-label={`${rowIndex + 1} ${field.name}`}
          options={(field.options || []).map((option) => ({ label: option, value: option }))}
          onChange={(nextValue) => updateCell(rowIndex, columnIndex, nextValue.join(','))}
        />
      );
    }
    if (field.type === 'rating') {
      return (
        <Rate
          value={Number(value) || 0}
          aria-label={`${rowIndex + 1} ${field.name}`}
          onChange={(nextValue) => updateCell(rowIndex, columnIndex, String(nextValue))}
        />
      );
    }
    if (field.type === 'checkbox') {
      return (
        <Checkbox
          checked={value === 'true'}
          aria-label={`${rowIndex + 1} ${field.name}`}
          onChange={(event) => updateCell(rowIndex, columnIndex, String(event.target.checked))}
        />
      );
    }
    if (activeView?.wrapText || field.type === 'richText') {
      return (
        <textarea
          className="multidimensional-cell-input is-textarea"
          rows={field.type === 'richText' ? 3 : 2}
          value={value}
          aria-label={`${rowIndex + 1} ${field.name}`}
          placeholder={field.type === 'attachment' ? '文件名或链接' : ''}
          onChange={(event) => updateCell(rowIndex, columnIndex, event.target.value)}
        />
      );
    }
    return (
      <input
        className="multidimensional-cell-input"
        type={
          field.type === 'email'
            ? 'email'
            : field.type === 'phone'
              ? 'tel'
              : field.type === 'hyperlink'
                ? 'url'
                : 'text'
        }
        value={value}
        aria-label={`${rowIndex + 1} ${field.name}`}
        placeholder={field.type === 'attachment' ? '文件名或链接' : ''}
        onChange={(event) => updateCell(rowIndex, columnIndex, event.target.value)}
      />
    );
  };

  return (
    <div className="multidimensional-designer">
      {modalContextHolder}
      <header className="multidimensional-designer-header">
        <Button type="text" icon={<ArrowLeft size={18} />} onClick={handleBack}>
          离开
        </Button>
        <span className="multidimensional-designer-mark">
          <Database size={22} />
        </span>
        <div className="multidimensional-designer-title">
          <Typography.Text strong>多维表格设计</Typography.Text>
          <Input
            variant="borderless"
            value={fileName}
            maxLength={120}
            aria-label="多维表格文件名称"
            suffix=".md"
            onChange={(event) => setFileName(event.target.value.replace(/\.(?:md|markdown)$/i, ''))}
          />
        </div>
        <Button type="primary" icon={<Save size={17} />} onClick={requestSave}>
          保存多维表格
        </Button>
      </header>

      <div className="multidimensional-body">
        <aside className="multidimensional-sidebar">
          <div className="multidimensional-table-source">
            <Database size={16} />
            <Input
              variant="borderless"
              value={tableName}
              maxLength={60}
              aria-label="数据表名称"
              onChange={(event) => setTableName(event.target.value)}
              onBlur={() => !tableName.trim() && setTableName('数据表')}
            />
            <Tooltip title="新增关联表格视图">
              <Button
                type="text"
                size="small"
                aria-label="新增表格视图"
                icon={<Plus size={17} />}
                onClick={addView}
              />
            </Tooltip>
          </div>
          <div className="multidimensional-view-list" aria-label="数据表关联视图">
            {views.map((view) => (
              <div
                className={`multidimensional-view-item ${view.id === activeViewId ? 'is-active' : ''}`}
                key={view.id}
              >
                {editingViewId === view.id ? (
                  <div className="multidimensional-view-editor">
                    <Rows3 size={16} />
                    <Input
                      autoFocus
                      size="small"
                      value={viewNameDraft}
                      aria-label="编辑表格视图名称"
                      onChange={(event) => setViewNameDraft(event.target.value)}
                      onBlur={finishRenamingView}
                      onPressEnter={finishRenamingView}
                    />
                  </div>
                ) : (
                  <button
                    type="button"
                    className="multidimensional-view-main"
                    aria-label={`打开视图 ${view.name}`}
                    onClick={() => setActiveViewId(view.id)}
                    onDoubleClick={() => startRenamingView(view)}
                  >
                    <Rows3 size={16} />
                    <span title={view.name}>{view.name}</span>
                  </button>
                )}
                {editingViewId !== view.id && (
                  <span className="multidimensional-view-actions">
                    <Tooltip title="重命名视图">
                      <Button
                        type="text"
                        size="small"
                        aria-label={`重命名视图 ${view.name}`}
                        icon={<Pencil size={14} />}
                        onClick={() => startRenamingView(view)}
                      />
                    </Tooltip>
                    <Tooltip title={views.length <= 1 ? '至少保留一个视图' : '删除视图'}>
                      <Button
                        type="text"
                        size="small"
                        danger
                        disabled={views.length <= 1}
                        aria-label={`删除视图 ${view.name}`}
                        icon={<Trash2 size={14} />}
                        onClick={() => removeView(view)}
                      />
                    </Tooltip>
                  </span>
                )}
              </div>
            ))}
          </div>
        </aside>

        <main className="multidimensional-content">
          <div className="multidimensional-toolbar" role="toolbar" aria-label="多维表格工具栏">
            <Button type="text" icon={<Plus size={17} />} onClick={addRecord}>
              添加记录
            </Button>
            <Button type="text" icon={<Settings2 size={17} />} onClick={openNewField}>
              字段管理
            </Button>
            <Button
              type={activeView?.filters.length ? 'primary' : 'text'}
              icon={<Filter size={17} />}
              onClick={openFilterDialog}
            >
              筛选{activeView?.filters.length ? ` (${activeView.filters.length})` : ''}
            </Button>
            <Button
              type={activeView?.sort ? 'primary' : 'text'}
              icon={<ArrowUpDown size={17} />}
              onClick={openSortDialog}
            >
              排序
            </Button>
            <Button
              type={activeView?.wrapText ? 'primary' : 'text'}
              icon={<WrapText size={17} />}
              onClick={() => updateActiveView({ wrapText: !activeView?.wrapText })}
            >
              {activeView?.wrapText ? '取消换行' : '自动换行'}
            </Button>
            <Input
              allowClear
              value={query}
              prefix={<Search size={15} />}
              placeholder="查找记录"
              onChange={(event) => updateActiveViewQuery(event.target.value)}
            />
            <Tooltip
              title={selectedRows.size ? `删除 ${selectedRows.size} 条记录` : '请先选择记录'}
            >
              <Button
                type="text"
                danger
                aria-label="删除选中记录"
                icon={<Trash2 size={17} />}
                disabled={!selectedRows.size}
                onClick={removeSelectedRecords}
              />
            </Tooltip>
          </div>

          <div className="multidimensional-grid-viewport">
            <div
              className={`multidimensional-grid ${activeView?.wrapText ? 'is-wrap' : ''}`}
              role="grid"
              aria-label="多维表格设计器"
              style={{
                gridTemplateColumns: `48px repeat(${fields.length}, minmax(160px, 1fr)) 46px`,
              }}
            >
              <div className="multidimensional-header-cell is-checkbox">
                <Checkbox
                  checked={records.length > 0 && selectedRows.size === records.length}
                  indeterminate={selectedRows.size > 0 && selectedRows.size < records.length}
                  onChange={(event) =>
                    setSelectedRows(
                      event.target.checked ? new Set(records.map((_, index) => index)) : new Set(),
                    )
                  }
                />
              </div>
              {fields.map((field) => (
                <button
                  type="button"
                  className="multidimensional-header-cell"
                  key={field.id}
                  onClick={() => openFieldSettings(field)}
                >
                  <FieldTypeIcon type={field.type} />
                  <span>{field.name}</span>
                </button>
              ))}
              <button
                type="button"
                className="multidimensional-header-cell is-add"
                aria-label="添加字段"
                onClick={openNewField}
              >
                <Plus size={18} />
              </button>

              {visibleRecords.map(({ index: rowIndex }) => (
                <div className="multidimensional-record-row" role="row" key={rowIndex}>
                  <div className="multidimensional-row-number">
                    <Checkbox
                      checked={selectedRows.has(rowIndex)}
                      aria-label={`选择第 ${rowIndex + 1} 条记录`}
                      onChange={(event) => {
                        setSelectedRows((current) => {
                          const next = new Set(current);
                          if (event.target.checked) next.add(rowIndex);
                          else next.delete(rowIndex);
                          return next;
                        });
                      }}
                    />
                    <span>{rowIndex + 1}</span>
                  </div>
                  {fields.map((field, columnIndex) => (
                    <div className="multidimensional-cell" role="gridcell" key={field.id}>
                      {renderCell(field, rowIndex, columnIndex)}
                    </div>
                  ))}
                  <div className="multidimensional-cell is-tail" />
                </div>
              ))}
              <button type="button" className="multidimensional-add-row" onClick={addRecord}>
                <Plus size={17} />
                添加记录
              </button>
            </div>
          </div>
          <footer className="multidimensional-footer">
            当前视图：{visibleRecords.length} 条 · 数据表总数：{records.length} 条
          </footer>
        </main>
      </div>

      <Modal
        title={`筛选视图“${activeView?.name || ''}”`}
        open={filterDialogOpen}
        okText="应用筛选"
        cancelText="取消"
        onOk={applyFilter}
        onCancel={() => setFilterDialogOpen(false)}
        footer={(_, { OkBtn, CancelBtn }) => (
          <>
            <Button danger disabled={!activeView?.filters.length} onClick={clearFilters}>
              清除全部筛选
            </Button>
            <CancelBtn />
            <OkBtn />
          </>
        )}
      >
        <div className="multidimensional-view-form">
          <label>
            <span>字段</span>
            <Select
              aria-label="筛选字段"
              value={filterFieldId}
              options={fields.map((field) => ({ label: field.name, value: field.id }))}
              onChange={(fieldId) => {
                const existing = activeView?.filters.find((filter) => filter.fieldId === fieldId);
                setFilterFieldId(fieldId);
                setFilterOperator(existing?.operator || 'contains');
                setFilterValue(existing?.value || '');
              }}
            />
          </label>
          <label>
            <span>条件</span>
            <Select
              aria-label="筛选条件"
              value={filterOperator}
              options={[
                { label: '包含', value: 'contains' },
                { label: '等于', value: 'equals' },
                { label: '不为空', value: 'notEmpty' },
              ]}
              onChange={setFilterOperator}
            />
          </label>
          {filterOperator !== 'notEmpty' && (
            <label>
              <span>筛选值</span>
              <Input
                value={filterValue}
                aria-label="筛选值"
                onChange={(event) => setFilterValue(event.target.value)}
              />
            </label>
          )}
        </div>
      </Modal>

      <Modal
        title={`排序视图“${activeView?.name || ''}”`}
        open={sortDialogOpen}
        okText="应用排序"
        cancelText="取消"
        onOk={applySort}
        onCancel={() => setSortDialogOpen(false)}
        footer={(_, { OkBtn, CancelBtn }) => (
          <>
            <Button danger disabled={!activeView?.sort} onClick={clearSort}>
              清除排序
            </Button>
            <CancelBtn />
            <OkBtn />
          </>
        )}
      >
        <div className="multidimensional-view-form">
          <label>
            <span>排序字段</span>
            <Select
              aria-label="排序字段"
              value={sortFieldId}
              options={fields.map((field) => ({ label: field.name, value: field.id }))}
              onChange={setSortFieldId}
            />
          </label>
          <label>
            <span>排序方式</span>
            <Select
              aria-label="排序方式"
              value={sortDirection}
              options={[
                { label: '升序', value: 'ascending' },
                { label: '降序', value: 'descending' },
              ]}
              onChange={setSortDirection}
            />
          </label>
        </div>
      </Modal>

      <Modal
        title={editingFieldId ? '字段设置' : '添加字段'}
        open={fieldDialogOpen}
        okText={editingFieldId ? '保存' : '添加'}
        cancelText="取消"
        okButtonProps={{ disabled: !fieldName.trim() }}
        onOk={saveField}
        onCancel={() => setFieldDialogOpen(false)}
        footer={(_, { OkBtn, CancelBtn }) => (
          <>
            {editingFieldId && fields.length > 1 && (
              <Button danger className="multidimensional-delete-field" onClick={removeEditingField}>
                删除字段
              </Button>
            )}
            <CancelBtn />
            <OkBtn />
          </>
        )}
      >
        <div className="multidimensional-field-form">
          <label>
            <span>字段名称</span>
            <Input
              autoFocus
              value={fieldName}
              placeholder="例如：负责人"
              onChange={(event) => setFieldName(event.target.value)}
            />
          </label>
          <label>
            <span>字段类型</span>
            <Select
              showSearch
              optionFilterProp="label"
              value={fieldType}
              options={FIELD_TYPE_OPTIONS}
              onChange={setFieldType}
            />
          </label>
          {(fieldType === 'select' || fieldType === 'multiSelect') && (
            <label>
              <span>选项（使用逗号分隔）</span>
              <Input
                value={fieldOptions}
                onChange={(event) => setFieldOptions(event.target.value)}
              />
            </label>
          )}
        </div>
      </Modal>
    </div>
  );
}
