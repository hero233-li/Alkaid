import { useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react';
import {
  Button,
  ColorPicker,
  Dropdown,
  Input,
  InputNumber,
  Modal,
  Select,
  Tooltip,
  Typography,
  type MenuProps,
} from 'antd';
import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  ArrowLeft,
  Bold,
  Columns3,
  CornerDownLeft,
  ChevronDown,
  ArrowDownAZ,
  ArrowUpAZ,
  FileDown,
  FileUp,
  Filter,
  ClipboardPaste,
  Copy,
  Eraser,
  Italic,
  ListChecks,
  Merge,
  PaintBucket,
  PanelLeft,
  PanelTop,
  Pencil,
  Plus,
  Redo2,
  Rows3,
  Save,
  Scissors,
  Search,
  Sheet,
  Square,
  SplitSquareHorizontal,
  Sigma,
  Strikethrough,
  Trash2,
  Undo2,
  Underline,
  WrapText,
} from 'lucide-react';
import {
  createDefaultSpreadsheetWorkbook,
  validateSpreadsheetCellValue,
  type SpreadsheetCellStyle,
  type SpreadsheetDataValidation,
  type SpreadsheetHorizontalAlignment,
  type SpreadsheetMergeRange,
  type SpreadsheetNumberFormat,
  type SpreadsheetSheet,
  type SpreadsheetVerticalAlignment,
  type SpreadsheetWorkbook,
} from './model';
import { downloadSpreadsheetXlsx, importSpreadsheetXlsx } from './spreadsheetXlsx';
import { evaluateGridCell, translateFormulaReferences } from './tableFormula';

const DEFAULT_FILE_NAME = '未命名在线表格';

interface CellPosition {
  row: number;
  column: number;
}

interface CellRange {
  startRow: number;
  startColumn: number;
  endRow: number;
  endColumn: number;
}

interface SpreadsheetDesignerProps {
  onBack: () => void;
  onSave: (fileName: string, workbook: SpreadsheetWorkbook) => void;
  initialFileName?: string;
  initialWorkbook?: SpreadsheetWorkbook;
}

type SpreadsheetRibbonTab =
  'home' | 'format' | 'alignment' | 'number' | 'data' | 'insert' | 'cell' | 'file';
type SpreadsheetSelectionMode = 'cell' | 'row' | 'column';

function cloneWorkbook(workbook: SpreadsheetWorkbook): SpreadsheetWorkbook {
  return JSON.parse(JSON.stringify(workbook)) as SpreadsheetWorkbook;
}

function columnLabel(index: number) {
  let value = index + 1;
  let label = '';
  while (value > 0) {
    value -= 1;
    label = String.fromCharCode(65 + (value % 26)) + label;
    value = Math.floor(value / 26);
  }
  return label;
}

function normalizeRange(anchor: CellPosition, focus: CellPosition): CellRange {
  return {
    startRow: Math.min(anchor.row, focus.row),
    startColumn: Math.min(anchor.column, focus.column),
    endRow: Math.max(anchor.row, focus.row),
    endColumn: Math.max(anchor.column, focus.column),
  };
}

function rangeContains(range: CellRange, row: number, column: number) {
  return (
    row >= range.startRow &&
    row <= range.endRow &&
    column >= range.startColumn &&
    column <= range.endColumn
  );
}

function mergeContains(merge: SpreadsheetMergeRange, row: number, column: number) {
  return rangeContains(merge, row, column);
}

function rangesEqual(left: CellRange, right: CellRange) {
  return (
    left.startRow === right.startRow &&
    left.startColumn === right.startColumn &&
    left.endRow === right.endRow &&
    left.endColumn === right.endColumn
  );
}

function positiveModulo(value: number, divisor: number) {
  return ((value % divisor) + divisor) % divisor;
}

export default function SpreadsheetDesigner({
  onBack,
  onSave,
  initialFileName,
  initialWorkbook,
}: SpreadsheetDesignerProps) {
  const [modalApi, modalContextHolder] = Modal.useModal();
  const [fileName, setFileName] = useState(
    () => initialFileName?.replace(/\.sheet\.json$/i, '') || DEFAULT_FILE_NAME,
  );
  const [workbook, setWorkbook] = useState<SpreadsheetWorkbook>(() =>
    cloneWorkbook(initialWorkbook || createDefaultSpreadsheetWorkbook()),
  );
  const [past, setPast] = useState<SpreadsheetWorkbook[]>([]);
  const [future, setFuture] = useState<SpreadsheetWorkbook[]>([]);
  const [anchor, setAnchor] = useState<CellPosition>({ row: 0, column: 0 });
  const [focus, setFocus] = useState<CellPosition>({ row: 0, column: 0 });
  const [selectionMode, setSelectionMode] = useState<SpreadsheetSelectionMode>('cell');
  const [formulaEditingTarget, setFormulaEditingTarget] = useState<CellPosition | null>(null);
  const [editingCell, setEditingCell] = useState<CellPosition | null>(null);
  const [dragging, setDragging] = useState(false);
  const [fillDragging, setFillDragging] = useState(false);
  const [fillPreview, setFillPreview] = useState<CellRange | null>(null);
  const [filterDialogOpen, setFilterDialogOpen] = useState(false);
  const [filterDraft, setFilterDraft] = useState('');
  const [findDialogOpen, setFindDialogOpen] = useState(false);
  const [findDraft, setFindDraft] = useState('');
  const [validationDialogOpen, setValidationDialogOpen] = useState(false);
  const [validationDraft, setValidationDraft] = useState<SpreadsheetDataValidation>({
    type: 'list',
    allowBlank: true,
    options: [],
  });
  const [xlsxBusy, setXlsxBusy] = useState(false);
  const [ribbonTab, setRibbonTab] = useState<SpreadsheetRibbonTab>('home');
  const inputRefs = useRef(new Map<string, HTMLInputElement>());
  const xlsxInputRef = useRef<HTMLInputElement>(null);
  const fillOriginRef = useRef<CellRange | null>(null);
  const fillTargetRef = useRef<CellRange | null>(null);
  const formulaTargetRef = useRef<CellPosition | null>(null);
  const formulaReferenceRef = useRef<{ anchor: CellPosition; prefix: string } | null>(null);
  const internalClipboardRef = useRef('');
  const sheet = workbook.sheets.find((item) => item.id === workbook.activeSheetId)!;
  const selection = useMemo(() => normalizeRange(anchor, focus), [anchor, focus]);
  const activeCellName = `${columnLabel(focus.column)}${focus.row + 1}`;
  const activeValue = sheet.cells[focus.row]?.[focus.column] || '';
  const freezeRowTarget = selectionMode === 'column' ? 1 : Math.max(1, selection.endRow + 1);
  const freezeColumnTarget = selectionMode === 'row' ? 1 : Math.max(1, selection.endColumn + 1);
  const activeValidation = sheet.validations[`${focus.row}:${focus.column}`];
  const filteredRows = (() => {
    const hidden = new Set<number>();
    const filters = Object.entries(sheet.filters).filter(([, value]) => value.trim());
    if (!filters.length) return hidden;
    for (let row = 1; row < sheet.rowCount; row += 1) {
      const matches = filters.every(([column, value]) =>
        (sheet.cells[row]?.[Number(column)] || '')
          .toLocaleLowerCase()
          .includes(value.trim().toLocaleLowerCase()),
      );
      if (!matches) hidden.add(row);
    }
    return hidden;
  })();

  useEffect(() => {
    const stopDragging = () => {
      setDragging(false);
      formulaReferenceRef.current = null;
    };
    window.addEventListener('mouseup', stopDragging);
    return () => window.removeEventListener('mouseup', stopDragging);
  }, []);

  const commitWorkbook = (update: (draft: SpreadsheetWorkbook) => void) => {
    setWorkbook((current) => {
      const next = cloneWorkbook(current);
      update(next);
      setPast((history) => [...history.slice(-49), cloneWorkbook(current)]);
      setFuture([]);
      return next;
    });
  };

  const updateSheet = (draft: SpreadsheetWorkbook, update: (sheet: SpreadsheetSheet) => void) => {
    const draftSheet = draft.sheets.find((item) => item.id === draft.activeSheetId);
    if (draftSheet) update(draftSheet);
  };

  const updateCell = (row: number, column: number, value: string) => {
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        draftSheet.cells[row][column] = value;
      }),
    );
  };

  const setFormulaTarget = (target: CellPosition | null) => {
    formulaTargetRef.current = target;
    setFormulaEditingTarget(target);
    if (!target) formulaReferenceRef.current = null;
  };

  const updateFormulaValue = (target: CellPosition, value: string) => {
    updateCell(target.row, target.column, value);
    setFormulaTarget(value.startsWith('=') ? target : null);
  };

  const beginFormulaReference = (
    row: number,
    column: number,
    event: ReactMouseEvent<HTMLInputElement>,
  ) => {
    const target = formulaTargetRef.current;
    if (!target || (target.row === row && target.column === column)) return false;
    const formula = sheet.cells[target.row]?.[target.column] || '';
    if (!formula.startsWith('=')) return false;
    event.preventDefault();
    formulaReferenceRef.current = { anchor: { row, column }, prefix: formula };
    setDragging(true);
    updateCell(target.row, target.column, `${formula}${columnLabel(column)}${row + 1}`);
    return true;
  };

  const updateFormulaReference = (row: number, column: number) => {
    const target = formulaTargetRef.current;
    const reference = formulaReferenceRef.current;
    if (!target || !reference) return false;
    const range = normalizeRange(reference.anchor, { row, column });
    const start = `${columnLabel(range.startColumn)}${range.startRow + 1}`;
    const end = `${columnLabel(range.endColumn)}${range.endRow + 1}`;
    updateCell(
      target.row,
      target.column,
      `${reference.prefix}${start === end ? start : `${start}:${end}`}`,
    );
    return true;
  };

  const applyToSelection = (callback: (row: number, column: number) => void) => {
    for (let row = selection.startRow; row <= selection.endRow; row += 1) {
      for (let column = selection.startColumn; column <= selection.endColumn; column += 1) {
        callback(row, column);
      }
    }
  };

  const undo = () => {
    const previous = past[past.length - 1];
    if (!previous) return;
    setFuture((history) => [cloneWorkbook(workbook), ...history].slice(0, 50));
    setWorkbook(cloneWorkbook(previous));
    setPast((history) => history.slice(0, -1));
  };

  const redo = () => {
    const next = future[0];
    if (!next) return;
    setPast((history) => [...history, cloneWorkbook(workbook)].slice(-50));
    setWorkbook(cloneWorkbook(next));
    setFuture((history) => history.slice(1));
  };

  const clearSelection = () => {
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        applyToSelection((row, column) => {
          draftSheet.cells[row][column] = '';
        });
      }),
    );
  };

  const applyStyle = (style: Partial<SpreadsheetCellStyle>) => {
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        applyToSelection((row, column) => {
          const key = `${row}:${column}`;
          draftSheet.styles[key] = { ...draftSheet.styles[key], ...style };
        });
      }),
    );
  };

  const toggleStyle = (key: 'bold' | 'italic' | 'underline' | 'strike' | 'wrap' | 'border') => {
    const activeStyle = sheet.styles[`${focus.row}:${focus.column}`] || {};
    applyStyle({ [key]: !activeStyle[key] });
  };

  const setAlignment = (horizontal: SpreadsheetHorizontalAlignment) => {
    applyStyle({ horizontal });
  };

  const setVerticalAlignment = (vertical: SpreadsheetVerticalAlignment) => {
    applyStyle({ vertical });
  };

  const setNumberFormat = (numberFormat: SpreadsheetNumberFormat) => {
    applyStyle({ numberFormat });
  };

  const adjustFontSize = (delta: number) => {
    const activeStyle = sheet.styles[`${focus.row}:${focus.column}`] || {};
    applyStyle({ fontSize: Math.max(8, Math.min(72, (activeStyle.fontSize || 14) + delta)) });
  };

  const adjustDecimalPlaces = (delta: number) => {
    const activeStyle = sheet.styles[`${focus.row}:${focus.column}`] || {};
    applyStyle({
      decimalPlaces: Math.max(0, Math.min(8, (activeStyle.decimalPlaces || 0) + delta)),
    });
  };

  const adjustIndent = (delta: number) => {
    const activeStyle = sheet.styles[`${focus.row}:${focus.column}`] || {};
    applyStyle({ indent: Math.max(0, Math.min(8, (activeStyle.indent || 0) + delta)) });
  };

  const clearFormatting = () => {
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        applyToSelection((row, column) => delete draftSheet.styles[`${row}:${column}`]);
      }),
    );
  };

  const formatCellValue = (value: string, style: SpreadsheetCellStyle) => {
    if (!value.trim() || !style.numberFormat || style.numberFormat === 'general') return value;
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return value;
    const decimalPlaces = style.decimalPlaces ?? (style.numberFormat === 'currency' ? 2 : 0);
    if (style.numberFormat === 'percent') {
      return `${(numeric * 100).toLocaleString('zh-CN', {
        minimumFractionDigits: decimalPlaces,
        maximumFractionDigits: decimalPlaces,
      })}%`;
    }
    return numeric.toLocaleString('zh-CN', {
      style: style.numberFormat === 'currency' ? 'currency' : 'decimal',
      currency: style.numberFormat === 'currency' ? 'CNY' : undefined,
      minimumFractionDigits: decimalPlaces,
      maximumFractionDigits: decimalPlaces,
    });
  };

  const mergeSelection = () => {
    if (selection.startRow === selection.endRow && selection.startColumn === selection.endColumn)
      return;
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        draftSheet.merges = draftSheet.merges.filter(
          (merge) =>
            merge.endRow < selection.startRow ||
            merge.startRow > selection.endRow ||
            merge.endColumn < selection.startColumn ||
            merge.startColumn > selection.endColumn,
        );
        draftSheet.merges.push({ ...selection });
        for (let row = selection.startRow; row <= selection.endRow; row += 1) {
          for (let column = selection.startColumn; column <= selection.endColumn; column += 1) {
            if (row !== selection.startRow || column !== selection.startColumn) {
              draftSheet.cells[row][column] = '';
            }
          }
        }
      }),
    );
    setAnchor({ row: selection.startRow, column: selection.startColumn });
    setFocus({ row: selection.startRow, column: selection.startColumn });
  };

  const unmergeSelection = () => {
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        draftSheet.merges = draftSheet.merges.filter(
          (merge) => !mergeContains(merge, focus.row, focus.column),
        );
      }),
    );
  };

  const insertRow = () => {
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        draftSheet.cells.splice(selection.startRow, 0, Array(draftSheet.columnCount).fill(''));
        draftSheet.rowHeights.splice(selection.startRow, 0, 32);
        draftSheet.rowCount += 1;
        draftSheet.merges = [];
      }),
    );
  };

  const deleteRow = () => {
    if (sheet.rowCount <= 1) return;
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        const count = selection.endRow - selection.startRow + 1;
        draftSheet.cells.splice(selection.startRow, count);
        draftSheet.rowHeights.splice(selection.startRow, count);
        draftSheet.rowCount = draftSheet.cells.length;
        draftSheet.merges = [];
      }),
    );
    setAnchor({ row: Math.min(selection.startRow, sheet.rowCount - 2), column: focus.column });
    setFocus({ row: Math.min(selection.startRow, sheet.rowCount - 2), column: focus.column });
  };

  const insertColumn = () => {
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        draftSheet.cells.forEach((row) => row.splice(selection.startColumn, 0, ''));
        draftSheet.columnWidths.splice(selection.startColumn, 0, 112);
        draftSheet.columnCount += 1;
        draftSheet.merges = [];
      }),
    );
  };

  const deleteColumn = () => {
    if (sheet.columnCount <= 1) return;
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        const count = selection.endColumn - selection.startColumn + 1;
        draftSheet.cells.forEach((row) => row.splice(selection.startColumn, count));
        draftSheet.columnWidths.splice(selection.startColumn, count);
        draftSheet.columnCount = draftSheet.cells[0].length;
        draftSheet.merges = [];
      }),
    );
    setAnchor({ row: focus.row, column: Math.min(selection.startColumn, sheet.columnCount - 2) });
    setFocus({ row: focus.row, column: Math.min(selection.startColumn, sheet.columnCount - 2) });
  };

  const selectionText = () => {
    const rows: string[] = [];
    for (let row = selection.startRow; row <= selection.endRow; row += 1) {
      rows.push(sheet.cells[row].slice(selection.startColumn, selection.endColumn + 1).join('\t'));
    }
    return rows.join('\n');
  };

  const copySelection = async (cut = false) => {
    const value = selectionText();
    internalClipboardRef.current = value;
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // 浏览器未授权剪贴板时仍可使用工作簿内部剪贴板。
    }
    if (cut) clearSelection();
  };

  const pasteFromClipboard = async () => {
    let value = internalClipboardRef.current;
    try {
      value = (await navigator.clipboard.readText()) || value;
    } catch {
      // 浏览器未授权读取时使用工作簿内部剪贴板。
    }
    if (value) pasteSelection(value);
  };

  const findNext = () => {
    const keyword = findDraft.trim().toLocaleLowerCase();
    if (!keyword) return;
    const total = sheet.rowCount * sheet.columnCount;
    const currentIndex = focus.row * sheet.columnCount + focus.column;
    for (let offset = 1; offset <= total; offset += 1) {
      const index = (currentIndex + offset) % total;
      const row = Math.floor(index / sheet.columnCount);
      const column = index % sheet.columnCount;
      const result = evaluateGridCell(sheet.cells, row, column).value;
      if (!result.toLocaleLowerCase().includes(keyword)) continue;
      const target = { row, column };
      setAnchor(target);
      setFocus(target);
      setSelectionMode('cell');
      window.requestAnimationFrame(() => inputRefs.current.get(`${row}:${column}`)?.focus());
      return;
    }
  };

  const transposeSelection = () => {
    const height = selection.endRow - selection.startRow + 1;
    const width = selection.endColumn - selection.startColumn + 1;
    if (
      selection.startRow + width > sheet.rowCount ||
      selection.startColumn + height > sheet.columnCount
    ) {
      modalApi.warning({ title: '无法转置', content: '转置后的区域超出了当前工作表范围。' });
      return;
    }
    const values = Array.from({ length: height }, (_, row) =>
      sheet.cells[selection.startRow + row].slice(selection.startColumn, selection.endColumn + 1),
    );
    const sourceStyles = { ...sheet.styles };
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        applyToSelection((row, column) => {
          draftSheet.cells[row][column] = '';
          delete draftSheet.styles[`${row}:${column}`];
        });
        for (let row = 0; row < width; row += 1) {
          for (let column = 0; column < height; column += 1) {
            const targetRow = selection.startRow + row;
            const targetColumn = selection.startColumn + column;
            draftSheet.cells[targetRow][targetColumn] = values[column][row];
            const sourceStyle =
              sourceStyles[`${selection.startRow + column}:${selection.startColumn + row}`];
            if (sourceStyle) draftSheet.styles[`${targetRow}:${targetColumn}`] = sourceStyle;
          }
        }
      }),
    );
    setAnchor({ row: selection.startRow, column: selection.startColumn });
    setFocus({
      row: selection.startRow + width - 1,
      column: selection.startColumn + height - 1,
    });
  };

  const fillSelection = (direction: 'down' | 'right') => {
    const sourceRow = selection.startRow;
    const sourceColumn = selection.startColumn;
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        for (let row = selection.startRow; row <= selection.endRow; row += 1) {
          for (let column = selection.startColumn; column <= selection.endColumn; column += 1) {
            if (direction === 'down' && row === sourceRow) continue;
            if (direction === 'right' && column === sourceColumn) continue;
            const originRow = direction === 'down' ? sourceRow : row;
            const originColumn = direction === 'right' ? sourceColumn : column;
            draftSheet.cells[row][column] = translateFormulaReferences(
              sheet.cells[originRow][originColumn],
              row - originRow,
              column - originColumn,
            );
            const sourceStyle = sheet.styles[`${originRow}:${originColumn}`];
            if (sourceStyle) draftSheet.styles[`${row}:${column}`] = { ...sourceStyle };
          }
        }
      }),
    );
  };

  const pasteSelection = (clipboardValue: string) => {
    const values = clipboardValue
      .replace(/\r/g, '')
      .split('\n')
      .map((row) => row.split('\t'));
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        values.forEach((row, rowOffset) =>
          row.forEach((value, columnOffset) => {
            const targetRow = selection.startRow + rowOffset;
            const targetColumn = selection.startColumn + columnOffset;
            if (targetRow < draftSheet.rowCount && targetColumn < draftSheet.columnCount) {
              draftSheet.cells[targetRow][targetColumn] = value;
            }
          }),
        );
      }),
    );
  };

  const applyFill = (target: CellRange) => {
    const origin = fillOriginRef.current;
    if (!origin || rangesEqual(origin, target)) return;
    const sourceHeight = origin.endRow - origin.startRow + 1;
    const sourceWidth = origin.endColumn - origin.startColumn + 1;
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        const sourceCells = sheet.cells.map((row) => [...row]);
        const sourceStyles = { ...sheet.styles };
        for (let row = target.startRow; row <= target.endRow; row += 1) {
          for (let column = target.startColumn; column <= target.endColumn; column += 1) {
            if (rangeContains(origin, row, column)) continue;
            const sourceRow = origin.startRow + positiveModulo(row - origin.startRow, sourceHeight);
            const sourceColumn =
              origin.startColumn + positiveModulo(column - origin.startColumn, sourceWidth);
            const sourceValue = sourceCells[sourceRow]?.[sourceColumn] || '';
            draftSheet.cells[row][column] = translateFormulaReferences(
              sourceValue,
              row - sourceRow,
              column - sourceColumn,
            );
            const sourceStyle = sourceStyles[`${sourceRow}:${sourceColumn}`];
            const targetKey = `${row}:${column}`;
            if (sourceStyle) draftSheet.styles[targetKey] = { ...sourceStyle };
            else delete draftSheet.styles[targetKey];
          }
        }
      }),
    );
    setAnchor({ row: target.startRow, column: target.startColumn });
    setFocus({ row: target.endRow, column: target.endColumn });
  };

  useEffect(() => {
    if (!fillDragging) return undefined;
    const finishFill = () => {
      const target = fillTargetRef.current;
      if (target) applyFill(target);
      fillOriginRef.current = null;
      fillTargetRef.current = null;
      setFillDragging(false);
      setFillPreview(null);
    };
    window.addEventListener('mouseup', finishFill, { once: true });
    return () => window.removeEventListener('mouseup', finishFill);
  });

  const updateFillTarget = (row: number, column: number) => {
    const origin = fillOriginRef.current;
    if (!origin) return;
    const target = {
      startRow: Math.min(origin.startRow, row),
      startColumn: Math.min(origin.startColumn, column),
      endRow: Math.max(origin.endRow, row),
      endColumn: Math.max(origin.endColumn, column),
    };
    fillTargetRef.current = target;
    setFillPreview(target);
  };

  const startResize = (dimension: 'column' | 'row', index: number, event: ReactMouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    const startPoint = dimension === 'column' ? event.clientX : event.clientY;
    const startSize = dimension === 'column' ? sheet.columnWidths[index] : sheet.rowHeights[index];
    setPast((history) => [...history.slice(-49), cloneWorkbook(workbook)]);
    setFuture([]);
    const move = (moveEvent: MouseEvent) => {
      const delta = (dimension === 'column' ? moveEvent.clientX : moveEvent.clientY) - startPoint;
      const nextSize = Math.round(
        Math.max(
          dimension === 'column' ? 56 : 24,
          Math.min(dimension === 'column' ? 480 : 240, startSize + delta),
        ),
      );
      setWorkbook((current) => {
        const next = cloneWorkbook(current);
        const draftSheet = next.sheets.find((item) => item.id === next.activeSheetId)!;
        if (dimension === 'column') draftSheet.columnWidths[index] = nextSize;
        else draftSheet.rowHeights[index] = nextSize;
        return next;
      });
    };
    const finish = () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', finish);
    };
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', finish);
  };

  const resizeByKeyboard = (dimension: 'column' | 'row', index: number, delta: number) => {
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        if (dimension === 'column') {
          draftSheet.columnWidths[index] = Math.max(
            56,
            Math.min(480, draftSheet.columnWidths[index] + delta),
          );
        } else {
          draftSheet.rowHeights[index] = Math.max(
            24,
            Math.min(240, draftSheet.rowHeights[index] + delta),
          );
        }
      }),
    );
  };

  const autoFitColumn = (column: number) => {
    const width = Math.max(
      72,
      Math.min(
        360,
        Math.max(
          columnLabel(column).length,
          ...sheet.cells.map((row) => row[column]?.length || 0),
        ) *
          8 +
          28,
      ),
    );
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        draftSheet.columnWidths[column] = width;
      }),
    );
  };

  const toggleFreeze = (dimension: 'row' | 'column', count: number) => {
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        if (dimension === 'row') {
          draftSheet.freezeRows = draftSheet.freezeRows === count ? 0 : count;
        } else {
          draftSheet.freezeColumns = draftSheet.freezeColumns === count ? 0 : count;
        }
      }),
    );
  };

  const insertFunction = (name: string) => {
    const range = `${columnLabel(selection.startColumn)}${selection.startRow + 1}:${columnLabel(selection.endColumn)}${selection.endRow + 1}`;
    const active = `${columnLabel(focus.column)}${focus.row + 1}`;
    const templates: Record<string, string> = {
      IF: `=IF(${active}>=0,"是","否")`,
      ROUND: `=ROUND(${active},2)`,
      ABS: `=ABS(${active})`,
      SQRT: `=SQRT(${active})`,
      POWER: `=POWER(${active},2)`,
      AND: `=AND(${active}>0,TRUE)`,
      OR: `=OR(${active}>0,FALSE)`,
      NOT: `=NOT(${active}>0)`,
      CONCAT: `=CONCAT(${active},"")`,
    };
    const formula = templates[name] || `=${name}(${range})`;
    const hasRange =
      selection.startRow !== selection.endRow || selection.startColumn !== selection.endColumn;
    const target =
      hasRange && selection.endRow + 1 < sheet.rowCount
        ? { row: selection.endRow + 1, column: selection.startColumn }
        : focus;
    updateCell(target.row, target.column, formula);
    setAnchor(target);
    setFocus(target);
  };

  const functionItems: MenuProps['items'] = [
    'SUM',
    'AVERAGE',
    'MIN',
    'MAX',
    'COUNT',
    'COUNTA',
    'ROUND',
    'ABS',
    'SQRT',
    'POWER',
    'IF',
    'AND',
    'OR',
    'NOT',
    'CONCAT',
  ].map((name) => ({ key: name, label: name, onClick: () => insertFunction(name) }));

  const switchSheet = (sheetId: string) => {
    setWorkbook((current) => ({ ...current, activeSheetId: sheetId }));
    setAnchor({ row: 0, column: 0 });
    setFocus({ row: 0, column: 0 });
    setSelectionMode('cell');
    setFormulaTarget(null);
  };

  const addSheet = () => {
    const id = `sheet-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const names = new Set(workbook.sheets.map((item) => item.name));
    let index = workbook.sheets.length + 1;
    while (names.has(`工作表 ${index}`)) index += 1;
    const nextSheet = createDefaultSpreadsheetWorkbook(sheet.rowCount, sheet.columnCount).sheets[0];
    nextSheet.id = id;
    nextSheet.name = `工作表 ${index}`;
    commitWorkbook((draft) => {
      draft.sheets.push(nextSheet);
      draft.activeSheetId = id;
    });
    setAnchor({ row: 0, column: 0 });
    setFocus({ row: 0, column: 0 });
  };

  const renameSheet = (target: SpreadsheetSheet) => {
    let nextName = target.name;
    modalApi.confirm({
      title: '重命名工作表',
      content: (
        <Input defaultValue={target.name} onChange={(event) => (nextName = event.target.value)} />
      ),
      okText: '保存',
      cancelText: '取消',
      onOk: () => {
        const normalized = nextName
          .trim()
          .replace(/[\\/?*:[\]]/g, '-')
          .slice(0, 31);
        if (!normalized) return Promise.reject(new Error('请输入工作表名称'));
        if (workbook.sheets.some((item) => item.id !== target.id && item.name === normalized))
          return Promise.reject(new Error('工作表名称不能重复'));
        commitWorkbook((draft) => {
          const draftSheet = draft.sheets.find((item) => item.id === target.id);
          if (draftSheet) draftSheet.name = normalized;
        });
      },
    });
  };

  const deleteActiveSheet = () => {
    if (workbook.sheets.length <= 1) return;
    modalApi.confirm({
      title: `删除“${sheet.name}”？`,
      content: '该工作表中的数据、公式和格式都会被删除。',
      okText: '删除工作表',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: () => {
        const currentIndex = workbook.sheets.findIndex((item) => item.id === sheet.id);
        const nextId = workbook.sheets[currentIndex === 0 ? 1 : currentIndex - 1].id;
        commitWorkbook((draft) => {
          draft.sheets = draft.sheets.filter((item) => item.id !== sheet.id);
          draft.activeSheetId = nextId;
        });
        setAnchor({ row: 0, column: 0 });
        setFocus({ row: 0, column: 0 });
      },
    });
  };

  const sortByActiveColumn = (direction: 'ascending' | 'descending') => {
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        const sourceCells = draftSheet.cells.map((row) => [...row]);
        const rows = Array.from({ length: draftSheet.rowCount - 1 }, (_, offset) => offset + 1);
        rows.sort((left, right) => {
          const leftValue = evaluateGridCell(sourceCells, left, focus.column).value;
          const rightValue = evaluateGridCell(sourceCells, right, focus.column).value;
          if (!leftValue && rightValue) return 1;
          if (leftValue && !rightValue) return -1;
          const leftNumber = Number(leftValue);
          const rightNumber = Number(rightValue);
          const result =
            Number.isFinite(leftNumber) && Number.isFinite(rightNumber)
              ? leftNumber - rightNumber
              : leftValue.localeCompare(rightValue, 'zh-CN', { numeric: true });
          return direction === 'ascending' ? result : -result;
        });
        const styles = { ...draftSheet.styles };
        const validations = { ...draftSheet.validations };
        const heights = [...draftSheet.rowHeights];
        rows.forEach((sourceRow, offset) => {
          const targetRow = offset + 1;
          draftSheet.cells[targetRow] = [...sourceCells[sourceRow]];
          draftSheet.rowHeights[targetRow] = heights[sourceRow];
          for (let column = 0; column < draftSheet.columnCount; column += 1) {
            const targetKey = `${targetRow}:${column}`;
            const sourceKey = `${sourceRow}:${column}`;
            if (styles[sourceKey]) draftSheet.styles[targetKey] = { ...styles[sourceKey] };
            else delete draftSheet.styles[targetKey];
            if (validations[sourceKey])
              draftSheet.validations[targetKey] = { ...validations[sourceKey] };
            else delete draftSheet.validations[targetKey];
          }
        });
        draftSheet.merges = draftSheet.merges.filter((merge) => merge.endRow === 0);
      }),
    );
  };

  const applyFilter = () => {
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        if (filterDraft.trim()) draftSheet.filters[String(focus.column)] = filterDraft.trim();
        else delete draftSheet.filters[String(focus.column)];
      }),
    );
    setFilterDialogOpen(false);
  };

  const clearFilters = () =>
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        draftSheet.filters = {};
      }),
    );

  const applyValidation = () => {
    const nextValidation = { ...validationDraft };
    if (nextValidation.type === 'list') {
      nextValidation.options = (nextValidation.options || [])
        .map((item) => item.trim())
        .filter(Boolean);
      if (!nextValidation.options.length) return;
    }
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        applyToSelection((row, column) => {
          draftSheet.validations[`${row}:${column}`] = nextValidation;
        });
      }),
    );
    setValidationDialogOpen(false);
  };

  const clearValidation = () => {
    commitWorkbook((draft) =>
      updateSheet(draft, (draftSheet) => {
        applyToSelection((row, column) => delete draftSheet.validations[`${row}:${column}`]);
      }),
    );
    setValidationDialogOpen(false);
  };

  const openValidationDialog = () => {
    const current = sheet.validations[`${focus.row}:${focus.column}`];
    setValidationDraft(
      current
        ? { ...current, options: current.options ? [...current.options] : undefined }
        : { type: 'list', allowBlank: true, options: [] },
    );
    setValidationDialogOpen(true);
  };

  const importXlsx = async (file?: File) => {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      modalApi.error({ title: '文件过大', content: '.xlsx 文件不能超过 10 MB。' });
      return;
    }
    setXlsxBusy(true);
    try {
      const imported = await importSpreadsheetXlsx(await file.arrayBuffer());
      setPast((history) => [...history.slice(-49), cloneWorkbook(workbook)]);
      setFuture([]);
      setWorkbook(imported);
      setFileName(file.name.replace(/\.xlsx$/i, ''));
      setAnchor({ row: 0, column: 0 });
      setFocus({ row: 0, column: 0 });
      modalApi.success({
        title: '导入完成',
        content: `已导入 ${imported.sheets.length} 个工作表。`,
      });
    } catch {
      modalApi.error({ title: '导入失败', content: '无法读取该 .xlsx 文件，请确认文件未损坏。' });
    } finally {
      setXlsxBusy(false);
    }
  };

  const exportXlsx = async () => {
    setXlsxBusy(true);
    try {
      await downloadSpreadsheetXlsx(fileName, workbook);
    } catch {
      modalApi.error({ title: '导出失败', content: '生成 .xlsx 文件时发生错误。' });
    } finally {
      setXlsxBusy(false);
    }
  };

  const moveFocus = (rowOffset: number, columnOffset: number, extend = false) => {
    const next = {
      row: Math.max(0, Math.min(sheet.rowCount - 1, focus.row + rowOffset)),
      column: Math.max(0, Math.min(sheet.columnCount - 1, focus.column + columnOffset)),
    };
    setFocus(next);
    setSelectionMode('cell');
    if (!extend) setAnchor(next);
    window.requestAnimationFrame(() =>
      inputRefs.current.get(`${next.row}:${next.column}`)?.focus(),
    );
  };

  const requestSave = () => {
    if (fileName.trim() && fileName.trim() !== DEFAULT_FILE_NAME) {
      onSave(fileName.trim(), workbook);
      return;
    }
    let nextName = '';
    modalApi.confirm({
      title: '保存在线表格',
      content: (
        <Input
          autoFocus
          placeholder="请输入工作簿名称"
          onChange={(event) => (nextName = event.target.value)}
        />
      ),
      okText: '创建工作簿',
      cancelText: '取消',
      onOk: () => {
        if (!nextName.trim()) return Promise.reject(new Error('请输入工作簿名称'));
        setFileName(nextName.trim());
        onSave(nextName.trim(), workbook);
      },
    });
  };

  const handleBack = () => {
    modalApi.confirm({
      title: '是否离开在线表格？',
      content: '离开后将丢弃当前工作簿及所有尚未保存的修改。',
      okText: '丢弃并离开',
      okButtonProps: { danger: true },
      cancelText: '继续编辑',
      onOk: onBack,
    });
  };

  return (
    <div
      className="spreadsheet-designer"
      onKeyDown={(event) => {
        const shortcut = event.metaKey || event.ctrlKey;
        if (shortcut && event.key.toLocaleLowerCase() === 's') {
          event.preventDefault();
          requestSave();
        } else if (shortcut && event.key.toLocaleLowerCase() === 'z') {
          event.preventDefault();
          if (event.shiftKey) redo();
          else undo();
        } else if (shortcut && event.key.toLocaleLowerCase() === 'y') {
          event.preventDefault();
          redo();
        } else if (event.key === 'Delete' || event.key === 'Backspace') {
          if ((event.target as HTMLElement).tagName !== 'INPUT') clearSelection();
        }
      }}
      onCopy={(event) => {
        if (!(event.target as HTMLElement).classList.contains('spreadsheet-cell')) return;
        event.clipboardData.setData('text/plain', selectionText());
        event.preventDefault();
      }}
      onCut={(event) => {
        if (!(event.target as HTMLElement).classList.contains('spreadsheet-cell')) return;
        event.clipboardData.setData('text/plain', selectionText());
        event.preventDefault();
        clearSelection();
      }}
      onPaste={(event) => {
        if (!(event.target as HTMLElement).classList.contains('spreadsheet-cell')) return;
        event.preventDefault();
        pasteSelection(event.clipboardData.getData('text/plain'));
      }}
    >
      {modalContextHolder}
      <Modal
        title={`筛选 ${columnLabel(focus.column)} 列`}
        open={filterDialogOpen}
        okText="应用筛选"
        cancelText="取消"
        onOk={applyFilter}
        onCancel={() => setFilterDialogOpen(false)}
      >
        <Typography.Paragraph type="secondary">
          首行作为表头；仅显示当前列中包含指定内容的数据行。留空并应用可清除本列筛选。
        </Typography.Paragraph>
        <Input
          autoFocus
          aria-label="筛选内容"
          placeholder="输入要包含的内容"
          value={filterDraft}
          onChange={(event) => setFilterDraft(event.target.value)}
        />
      </Modal>
      <Modal
        title="查找单元格"
        open={findDialogOpen}
        okText="查找下一个"
        cancelText="关闭"
        onOk={findNext}
        onCancel={() => setFindDialogOpen(false)}
      >
        <Input
          autoFocus
          allowClear
          aria-label="查找内容"
          placeholder="输入文本或计算结果"
          value={findDraft}
          onChange={(event) => setFindDraft(event.target.value)}
          onPressEnter={findNext}
        />
      </Modal>
      <Modal
        title="数据验证"
        open={validationDialogOpen}
        okText="应用到选区"
        cancelText="取消"
        footer={(_, { OkBtn, CancelBtn }) => (
          <>
            <Button danger onClick={clearValidation}>
              清除验证
            </Button>
            <CancelBtn />
            <OkBtn />
          </>
        )}
        onOk={applyValidation}
        onCancel={() => setValidationDialogOpen(false)}
      >
        <div className="spreadsheet-validation-form">
          <label>
            <span>验证类型</span>
            <Select
              aria-label="验证类型"
              value={validationDraft.type}
              options={[
                { value: 'list', label: '下拉列表' },
                { value: 'wholeNumber', label: '整数' },
                { value: 'decimal', label: '小数' },
                { value: 'date', label: '日期' },
                { value: 'textLength', label: '文本长度' },
              ]}
              onChange={(type) => setValidationDraft((current) => ({ ...current, type }))}
            />
          </label>
          {validationDraft.type === 'list' && (
            <label>
              <span>可选值</span>
              <Input
                aria-label="数据验证可选值"
                placeholder="例如：未开始,进行中,已完成"
                value={(validationDraft.options || []).join(',')}
                onChange={(event) =>
                  setValidationDraft((current) => ({
                    ...current,
                    options: event.target.value.split(','),
                  }))
                }
              />
            </label>
          )}
          {['wholeNumber', 'decimal', 'textLength'].includes(validationDraft.type) && (
            <div className="spreadsheet-validation-range">
              <label>
                <span>最小值</span>
                <InputNumber
                  aria-label="数据验证最小值"
                  value={validationDraft.minimum}
                  onChange={(value) =>
                    setValidationDraft((current) => ({
                      ...current,
                      minimum: value === null ? undefined : value,
                    }))
                  }
                />
              </label>
              <label>
                <span>最大值</span>
                <InputNumber
                  aria-label="数据验证最大值"
                  value={validationDraft.maximum}
                  onChange={(value) =>
                    setValidationDraft((current) => ({
                      ...current,
                      maximum: value === null ? undefined : value,
                    }))
                  }
                />
              </label>
            </div>
          )}
          <Button
            type={validationDraft.allowBlank ? 'primary' : 'default'}
            onClick={() =>
              setValidationDraft((current) => ({ ...current, allowBlank: !current.allowBlank }))
            }
          >
            {validationDraft.allowBlank ? '允许空值' : '不允许空值'}
          </Button>
        </div>
      </Modal>
      <header className="spreadsheet-header">
        <Button type="text" icon={<ArrowLeft size={18} />} onClick={handleBack}>
          离开
        </Button>
        <span className="spreadsheet-header-mark">
          <Sheet size={22} />
        </span>
        <div className="spreadsheet-header-title">
          <Typography.Text strong>在线表格</Typography.Text>
          <Input
            variant="borderless"
            value={fileName}
            aria-label="在线表格文件名称"
            suffix=".sheet.json"
            onChange={(event) => setFileName(event.target.value.replace(/\.sheet\.json$/i, ''))}
          />
        </div>
        <Button type="primary" icon={<Save size={17} />} onClick={requestSave}>
          保存工作簿
        </Button>
      </header>

      <nav className="spreadsheet-ribbon-tabs" aria-label="在线表格菜单">
        {(
          [
            ['home', '开始'],
            ['format', '格式'],
            ['alignment', '对齐'],
            ['number', '数字'],
            ['data', '数据'],
            ['insert', '插入'],
            ['cell', '单元格'],
            ['file', '文件'],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            className={ribbonTab === value ? 'is-active' : ''}
            onClick={() => setRibbonTab(value)}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="spreadsheet-ribbon" role="toolbar" aria-label="在线表格工具栏">
        {ribbonTab === 'home' && (
          <>
            <div className="spreadsheet-ribbon-group">
              <span>历史</span>
              <Tooltip title="撤销">
                <Button
                  aria-label="撤销"
                  icon={<Undo2 size={17} />}
                  disabled={!past.length}
                  onClick={undo}
                />
              </Tooltip>
              <Tooltip title="重做">
                <Button
                  aria-label="重做"
                  icon={<Redo2 size={17} />}
                  disabled={!future.length}
                  onClick={redo}
                />
              </Tooltip>
            </div>
            <div className="spreadsheet-ribbon-group">
              <span>剪贴板</span>
              <Tooltip title="复制选区">
                <Button
                  aria-label="复制选区"
                  icon={<Copy size={17} />}
                  onClick={() => void copySelection()}
                />
              </Tooltip>
              <Tooltip title="剪切选区">
                <Button
                  aria-label="剪切选区"
                  icon={<Scissors size={17} />}
                  onClick={() => void copySelection(true)}
                />
              </Tooltip>
              <Tooltip title="粘贴到当前单元格">
                <Button
                  aria-label="粘贴选区"
                  icon={<ClipboardPaste size={17} />}
                  onClick={() => void pasteFromClipboard()}
                />
              </Tooltip>
            </div>
            <div className="spreadsheet-ribbon-group">
              <span>公式</span>
              <Dropdown menu={{ items: functionItems }} trigger={['click']}>
                <Button icon={<Sigma size={17} />}>
                  插入函数 <ChevronDown size={14} />
                </Button>
              </Dropdown>
              <Button icon={<Sigma size={17} />} onClick={() => insertFunction('SUM')}>
                自动求和
              </Button>
            </div>
            <div className="spreadsheet-ribbon-group">
              <span>查找</span>
              <Button icon={<Search size={17} />} onClick={() => setFindDialogOpen(true)}>
                查找
              </Button>
            </div>
          </>
        )}
        {ribbonTab === 'format' && (
          <>
            <div className="spreadsheet-ribbon-group">
              <span>字体</span>
              <Select
                size="small"
                aria-label="字体"
                value={sheet.styles[`${focus.row}:${focus.column}`]?.fontFamily || 'inherit'}
                style={{ width: 112 }}
                options={[
                  { label: '默认字体', value: 'inherit' },
                  { label: '宋体', value: 'SimSun' },
                  { label: '微软雅黑', value: 'Microsoft YaHei' },
                  { label: '等宽字体', value: 'monospace' },
                ]}
                onChange={(fontFamily) => applyStyle({ fontFamily })}
              />
              <InputNumber
                size="small"
                aria-label="字号"
                min={8}
                max={72}
                value={sheet.styles[`${focus.row}:${focus.column}`]?.fontSize || 14}
                onChange={(fontSize) => fontSize && applyStyle({ fontSize })}
              />
              <Button aria-label="增大字号" onClick={() => adjustFontSize(1)}>
                A+
              </Button>
              <Button aria-label="减小字号" onClick={() => adjustFontSize(-1)}>
                A-
              </Button>
            </div>
            <div className="spreadsheet-ribbon-group">
              <span>字形</span>
              <Button
                aria-label="粗体"
                icon={<Bold size={17} />}
                onClick={() => toggleStyle('bold')}
              />
              <Button
                aria-label="斜体"
                icon={<Italic size={17} />}
                onClick={() => toggleStyle('italic')}
              />
              <Button
                aria-label="下划线"
                icon={<Underline size={17} />}
                onClick={() => toggleStyle('underline')}
              />
              <Button
                aria-label="删除线"
                icon={<Strikethrough size={17} />}
                onClick={() => toggleStyle('strike')}
              />
              <Button
                aria-label="单元格边框"
                icon={<Square size={17} />}
                onClick={() => toggleStyle('border')}
              />
            </div>
            <div className="spreadsheet-ribbon-group spreadsheet-color-group">
              <span>颜色</span>
              <Tooltip title="文字颜色">
                <ColorPicker
                  aria-label="文字颜色"
                  value={sheet.styles[`${focus.row}:${focus.column}`]?.textColor || '#1f2937'}
                  onChangeComplete={(color) => applyStyle({ textColor: color.toHexString() })}
                />
              </Tooltip>
              <Tooltip title="填充颜色">
                <ColorPicker
                  aria-label="填充颜色"
                  value={sheet.styles[`${focus.row}:${focus.column}`]?.fillColor || '#ffffff'}
                  onChangeComplete={(color) => applyStyle({ fillColor: color.toHexString() })}
                >
                  <Button aria-label="填充颜色" icon={<PaintBucket size={17} />} />
                </ColorPicker>
              </Tooltip>
            </div>
          </>
        )}
        {ribbonTab === 'alignment' && (
          <>
            <div className="spreadsheet-ribbon-group">
              <span>对齐</span>
              <Button
                aria-label="左对齐"
                icon={<AlignLeft size={17} />}
                onClick={() => setAlignment('left')}
              />
              <Button
                aria-label="居中"
                icon={<AlignCenter size={17} />}
                onClick={() => setAlignment('center')}
              />
              <Button
                aria-label="右对齐"
                icon={<AlignRight size={17} />}
                onClick={() => setAlignment('right')}
              />
              <Button aria-label="顶端对齐" onClick={() => setVerticalAlignment('top')}>
                上
              </Button>
              <Button aria-label="垂直居中" onClick={() => setVerticalAlignment('middle')}>
                中
              </Button>
              <Button aria-label="底端对齐" onClick={() => setVerticalAlignment('bottom')}>
                下
              </Button>
              <Button aria-label="减少缩进" onClick={() => adjustIndent(-1)}>
                −缩进
              </Button>
              <Button aria-label="增加缩进" onClick={() => adjustIndent(1)}>
                +缩进
              </Button>
              <Button
                aria-label="自动换行"
                icon={<WrapText size={17} />}
                onClick={() => toggleStyle('wrap')}
              />
            </div>
          </>
        )}
        {ribbonTab === 'number' && (
          <>
            <div className="spreadsheet-ribbon-group">
              <span>数字格式</span>
              <Button onClick={() => setNumberFormat('general')}>常规</Button>
              <Button onClick={() => setNumberFormat('number')}>数字</Button>
              <Button onClick={() => setNumberFormat('percent')}>%</Button>
              <Button onClick={() => setNumberFormat('currency')}>¥</Button>
              <Button aria-label="增加小数位" onClick={() => adjustDecimalPlaces(1)}>
                .0+
              </Button>
              <Button aria-label="减少小数位" onClick={() => adjustDecimalPlaces(-1)}>
                .0−
              </Button>
            </div>
            <div className="spreadsheet-ribbon-group">
              <span>清除</span>
              <Button icon={<Eraser size={17} />} onClick={clearFormatting}>
                清除格式
              </Button>
            </div>
          </>
        )}
        {ribbonTab === 'data' && (
          <>
            <div className="spreadsheet-ribbon-group">
              <span>排序</span>
              <Button
                icon={<ArrowUpAZ size={17} />}
                onClick={() => sortByActiveColumn('ascending')}
              >
                升序
              </Button>
              <Button
                icon={<ArrowDownAZ size={17} />}
                onClick={() => sortByActiveColumn('descending')}
              >
                降序
              </Button>
            </div>
            <div className="spreadsheet-ribbon-group">
              <span>筛选</span>
              <Button
                type={Object.keys(sheet.filters).length ? 'primary' : 'default'}
                icon={<Filter size={17} />}
                onClick={() => {
                  setFilterDraft(sheet.filters[String(focus.column)] || '');
                  setFilterDialogOpen(true);
                }}
              >
                筛选当前列
              </Button>
              <Button disabled={!Object.keys(sheet.filters).length} onClick={clearFilters}>
                清除筛选
              </Button>
            </div>
            <div className="spreadsheet-ribbon-group">
              <span>规则</span>
              <Button icon={<ListChecks size={17} />} onClick={openValidationDialog}>
                数据验证
              </Button>
            </div>
          </>
        )}
        {ribbonTab === 'insert' && (
          <>
            <div className="spreadsheet-ribbon-group">
              <span>新增</span>
              <Button icon={<Rows3 size={17} />} onClick={insertRow}>
                插入行
              </Button>
              <Button icon={<Columns3 size={17} />} onClick={insertColumn}>
                插入列
              </Button>
            </div>
            <div className="spreadsheet-ribbon-group">
              <span>删除</span>
              <Button danger icon={<Trash2 size={17} />} onClick={deleteRow}>
                删除行
              </Button>
              <Button danger icon={<Trash2 size={17} />} onClick={deleteColumn}>
                删除列
              </Button>
            </div>
          </>
        )}
        {ribbonTab === 'cell' && (
          <>
            <div className="spreadsheet-ribbon-group">
              <span>合并</span>
              <Button icon={<Merge size={17} />} onClick={mergeSelection}>
                合并单元格
              </Button>
              <Button icon={<SplitSquareHorizontal size={17} />} onClick={unmergeSelection}>
                取消合并
              </Button>
            </div>
            <div className="spreadsheet-ribbon-group">
              <span>区域</span>
              <Button onClick={transposeSelection}>转置选区</Button>
              <Button onClick={() => fillSelection('down')}>向下填充</Button>
              <Button onClick={() => fillSelection('right')}>向右填充</Button>
            </div>
            <div className="spreadsheet-ribbon-group">
              <span>冻结</span>
              <Button
                type={sheet.freezeRows ? 'primary' : 'default'}
                icon={<PanelTop size={17} />}
                onClick={() => toggleFreeze('row', freezeRowTarget)}
              >
                {sheet.freezeRows
                  ? `取消冻结 ${sheet.freezeRows} 行`
                  : `冻结前 ${freezeRowTarget} 行`}
              </Button>
              <Button
                type={sheet.freezeColumns ? 'primary' : 'default'}
                icon={<PanelLeft size={17} />}
                onClick={() => toggleFreeze('column', freezeColumnTarget)}
              >
                {sheet.freezeColumns
                  ? `取消冻结 ${sheet.freezeColumns} 列`
                  : `冻结前 ${freezeColumnTarget} 列`}
              </Button>
            </div>
          </>
        )}
        {ribbonTab === 'file' && (
          <div className="spreadsheet-ribbon-group">
            <span>Excel 文件</span>
            <Button
              loading={xlsxBusy}
              icon={<FileUp size={17} />}
              onClick={() => xlsxInputRef.current?.click()}
            >
              导入 .xlsx
            </Button>
            <Button
              loading={xlsxBusy}
              icon={<FileDown size={17} />}
              onClick={() => void exportXlsx()}
            >
              导出 .xlsx
            </Button>
          </div>
        )}
        <input
          ref={xlsxInputRef}
          className="data-management-file-input"
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          onChange={(event) => {
            void importXlsx(event.target.files?.[0]);
            event.target.value = '';
          }}
        />
      </div>

      <div className="spreadsheet-formula-bar">
        <span>{activeCellName}</span>
        <span>fx</span>
        <Input
          value={activeValue}
          aria-label="公式栏"
          onFocus={() => {
            if (activeValue.startsWith('=')) setFormulaTarget({ ...focus });
          }}
          onChange={(event) => updateFormulaValue({ ...focus }, event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== 'Enter' && event.key !== 'Escape') return;
            event.preventDefault();
            setFormulaTarget(null);
            inputRefs.current.get(`${focus.row}:${focus.column}`)?.focus();
          }}
        />
      </div>
      {activeValidation?.type === 'list' && (
        <datalist id="spreadsheet-validation-options">
          {(activeValidation.options || []).map((option) => (
            <option value={option} key={option} />
          ))}
        </datalist>
      )}

      <div className="spreadsheet-grid-viewport">
        <div
          className="spreadsheet-grid"
          role="grid"
          aria-label="在线 Excel 表格"
          style={{
            gridTemplateColumns: `44px ${sheet.columnWidths.map((width) => `${width}px`).join(' ')}`,
            gridTemplateRows: `32px ${sheet.rowHeights.map((height, row) => `${filteredRows.has(row) ? 0 : height}px`).join(' ')}`,
          }}
        >
          <span className="spreadsheet-corner" />
          {Array.from({ length: sheet.columnCount }, (_, column) => {
            const frozen = column < sheet.freezeColumns;
            const left =
              44 + sheet.columnWidths.slice(0, column).reduce((sum, width) => sum + width, 0);
            return (
              <button
                type="button"
                className={`spreadsheet-column-header ${column >= selection.startColumn && column <= selection.endColumn ? 'is-selected' : ''} ${frozen ? 'is-frozen' : ''}`}
                style={{
                  gridColumn: column + 2,
                  gridRow: 1,
                  left: frozen ? left : undefined,
                  zIndex: frozen ? 7 : undefined,
                }}
                key={column}
                aria-label={`选择 ${columnLabel(column)} 列`}
                onMouseDown={(event) => {
                  event.preventDefault();
                  if (!event.shiftKey || selectionMode !== 'column') {
                    setAnchor({ row: 0, column });
                  }
                  setFocus({ row: sheet.rowCount - 1, column });
                  setSelectionMode('column');
                  setDragging(true);
                }}
                onMouseEnter={() => {
                  if (dragging && selectionMode === 'column') {
                    setFocus({ row: sheet.rowCount - 1, column });
                  }
                }}
              >
                {columnLabel(column)}
                <span
                  className="spreadsheet-column-resizer"
                  role="separator"
                  aria-label={`调整 ${columnLabel(column)} 列宽`}
                  tabIndex={0}
                  onDoubleClick={(event) => {
                    event.stopPropagation();
                    autoFitColumn(column);
                  }}
                  onMouseDown={(event) => startResize('column', column, event)}
                  onKeyDown={(event) => {
                    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
                    event.preventDefault();
                    event.stopPropagation();
                    resizeByKeyboard('column', column, event.key === 'ArrowRight' ? 8 : -8);
                  }}
                />
              </button>
            );
          })}
          {Array.from({ length: sheet.rowCount }, (_, row) => {
            const frozen = row < sheet.freezeRows;
            const top =
              32 + sheet.rowHeights.slice(0, row).reduce((sum, height) => sum + height, 0);
            return (
              <button
                type="button"
                className={`spreadsheet-row-header ${row >= selection.startRow && row <= selection.endRow ? 'is-selected' : ''} ${frozen ? 'is-frozen' : ''}`}
                style={{
                  gridColumn: 1,
                  gridRow: row + 2,
                  top: frozen ? top : undefined,
                  zIndex: frozen ? 6 : undefined,
                  display: filteredRows.has(row) ? 'none' : undefined,
                }}
                key={row}
                aria-label={`选择第 ${row + 1} 行`}
                onMouseDown={(event) => {
                  event.preventDefault();
                  if (!event.shiftKey || selectionMode !== 'row') {
                    setAnchor({ row, column: 0 });
                  }
                  setFocus({ row, column: sheet.columnCount - 1 });
                  setSelectionMode('row');
                  setDragging(true);
                }}
                onMouseEnter={() => {
                  if (dragging && selectionMode === 'row') {
                    setFocus({ row, column: sheet.columnCount - 1 });
                  }
                }}
              >
                {row + 1}
                <span
                  className="spreadsheet-row-resizer"
                  role="separator"
                  aria-label={`调整第 ${row + 1} 行高`}
                  tabIndex={0}
                  onMouseDown={(event) => startResize('row', row, event)}
                  onKeyDown={(event) => {
                    if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;
                    event.preventDefault();
                    event.stopPropagation();
                    resizeByKeyboard('row', row, event.key === 'ArrowDown' ? 4 : -4);
                  }}
                />
              </button>
            );
          })}
          {sheet.cells.map((rowValues, row) =>
            rowValues.map((rawValue, column) => {
              const merge = sheet.merges.find((item) => mergeContains(item, row, column));
              if (merge && (merge.startRow !== row || merge.startColumn !== column)) return null;
              const style = sheet.styles[`${row}:${column}`] || {};
              const selected = rangeContains(selection, row, column);
              const fillSelected = fillPreview ? rangeContains(fillPreview, row, column) : false;
              const frozenRow = row < sheet.freezeRows;
              const frozenColumn = column < sheet.freezeColumns;
              const frozenTop =
                32 + sheet.rowHeights.slice(0, row).reduce((sum, height) => sum + height, 0);
              const frozenLeft =
                44 + sheet.columnWidths.slice(0, column).reduce((sum, width) => sum + width, 0);
              const formulaResult = evaluateGridCell(sheet.cells, row, column);
              const formulaEditing =
                formulaEditingTarget?.row === row && formulaEditingTarget.column === column;
              const validation = sheet.validations[`${row}:${column}`];
              const invalid = !validateSpreadsheetCellValue(formulaResult.value, validation);
              const cellEditing = editingCell?.row === row && editingCell.column === column;
              const displayValue = formulaResult.calculated ? formulaResult.value : rawValue;
              return (
                <input
                  key={`${row}:${column}`}
                  ref={(node) => {
                    const key = `${row}:${column}`;
                    if (node) inputRefs.current.set(key, node);
                    else inputRefs.current.delete(key);
                  }}
                  className={`spreadsheet-cell ${selected ? 'is-selected' : ''} ${fillSelected ? 'is-fill-preview' : ''} ${invalid ? 'is-invalid' : ''} ${frozenRow || frozenColumn ? 'is-frozen' : ''} ${focus.row === row && focus.column === column ? 'is-active' : ''}`}
                  aria-label={`${columnLabel(column)}${row + 1} 单元格`}
                  list={
                    validation?.type === 'list' && focus.row === row && focus.column === column
                      ? 'spreadsheet-validation-options'
                      : undefined
                  }
                  value={
                    (formulaEditing && rawValue.startsWith('=')) || cellEditing
                      ? rawValue
                      : formatCellValue(displayValue, style)
                  }
                  title={
                    invalid
                      ? '当前值不符合数据验证规则'
                      : formulaResult.calculated
                        ? rawValue
                        : undefined
                  }
                  style={{
                    gridColumn: `${column + 2} / span ${merge ? merge.endColumn - merge.startColumn + 1 : 1}`,
                    gridRow: `${row + 2} / span ${merge ? merge.endRow - merge.startRow + 1 : 1}`,
                    textAlign: style.horizontal || 'left',
                    fontWeight: style.bold ? 700 : 400,
                    fontStyle: style.italic ? 'italic' : 'normal',
                    textDecoration:
                      [style.underline ? 'underline' : '', style.strike ? 'line-through' : '']
                        .filter(Boolean)
                        .join(' ') || undefined,
                    fontFamily: style.fontFamily || undefined,
                    fontSize: style.fontSize ? `${style.fontSize}px` : undefined,
                    color: style.textColor || undefined,
                    backgroundColor: style.fillColor || undefined,
                    boxShadow: style.border ? 'inset 0 0 0 1px #64748b' : undefined,
                    paddingLeft: style.indent ? `${10 + style.indent * 12}px` : undefined,
                    paddingTop:
                      style.vertical === 'top' ? 2 : style.vertical === 'bottom' ? 10 : undefined,
                    whiteSpace: style.wrap ? 'normal' : 'nowrap',
                    position: frozenRow || frozenColumn ? 'sticky' : undefined,
                    top: frozenRow ? frozenTop : undefined,
                    left: frozenColumn ? frozenLeft : undefined,
                    zIndex:
                      frozenRow && frozenColumn ? 6 : frozenRow || frozenColumn ? 5 : undefined,
                    display: filteredRows.has(row) ? 'none' : undefined,
                  }}
                  onMouseDown={(event) => {
                    if (beginFormulaReference(row, column, event)) return;
                    if (event.shiftKey) setFocus({ row, column });
                    else {
                      setAnchor({ row, column });
                      setFocus({ row, column });
                    }
                    setSelectionMode('cell');
                    setDragging(true);
                  }}
                  onMouseEnter={() => {
                    if (fillDragging) updateFillTarget(row, column);
                    else if (updateFormulaReference(row, column)) return;
                    else if (dragging) setFocus({ row, column });
                  }}
                  onDoubleClick={(event) => {
                    event.currentTarget.value = rawValue;
                    event.currentTarget.select();
                  }}
                  onFocus={() => setEditingCell({ row, column })}
                  onBlur={() => setEditingCell(null)}
                  onChange={(event) => updateFormulaValue({ row, column }, event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      setFormulaTarget(null);
                      moveFocus(event.shiftKey ? -1 : 1, 0);
                    } else if (event.key === 'Tab') {
                      event.preventDefault();
                      moveFocus(0, event.shiftKey ? -1 : 1);
                    } else if (event.key === 'ArrowUp' && !event.altKey) {
                      event.preventDefault();
                      moveFocus(-1, 0, event.shiftKey);
                    } else if (event.key === 'ArrowDown' && !event.altKey) {
                      event.preventDefault();
                      moveFocus(1, 0, event.shiftKey);
                    } else if (
                      event.key === 'ArrowLeft' &&
                      !event.altKey &&
                      event.currentTarget.selectionStart === 0
                    ) {
                      event.preventDefault();
                      moveFocus(0, -1, event.shiftKey);
                    } else if (
                      event.key === 'ArrowRight' &&
                      !event.altKey &&
                      event.currentTarget.selectionStart === event.currentTarget.value.length
                    ) {
                      event.preventDefault();
                      moveFocus(0, 1, event.shiftKey);
                    } else if ((event.key === 'Delete' || event.key === 'Backspace') && !rawValue) {
                      event.preventDefault();
                      clearSelection();
                    }
                  }}
                />
              );
            }),
          )}
          <span
            className="spreadsheet-fill-handle-layer"
            style={{
              gridColumn: selection.endColumn + 2,
              gridRow: selection.endRow + 2,
            }}
          >
            <button
              type="button"
              aria-label="拖拽填充"
              title="拖拽填充公式或内容"
              onMouseDown={(event) => {
                event.preventDefault();
                event.stopPropagation();
                fillOriginRef.current = { ...selection };
                fillTargetRef.current = { ...selection };
                setFillPreview({ ...selection });
                setFillDragging(true);
              }}
              onKeyDown={(event) => {
                const next = { ...selection };
                if (event.key === 'ArrowDown')
                  next.endRow = Math.min(sheet.rowCount - 1, selection.endRow + 1);
                else if (event.key === 'ArrowUp')
                  next.startRow = Math.max(0, selection.startRow - 1);
                else if (event.key === 'ArrowRight')
                  next.endColumn = Math.min(sheet.columnCount - 1, selection.endColumn + 1);
                else if (event.key === 'ArrowLeft')
                  next.startColumn = Math.max(0, selection.startColumn - 1);
                else return;
                event.preventDefault();
                event.stopPropagation();
                fillOriginRef.current = { ...selection };
                applyFill(next);
                fillOriginRef.current = null;
              }}
            />
          </span>
        </div>
      </div>

      <footer className="spreadsheet-footer">
        <div className="spreadsheet-sheet-tabs" role="tablist" aria-label="工作表">
          {workbook.sheets.map((item) => (
            <button
              type="button"
              role="tab"
              aria-selected={item.id === workbook.activeSheetId}
              className={item.id === workbook.activeSheetId ? 'is-active' : ''}
              key={item.id}
              title="双击可重命名"
              onClick={() => switchSheet(item.id)}
              onDoubleClick={() => renameSheet(item)}
            >
              {item.name}
            </button>
          ))}
          <button type="button" aria-label="新增工作表" onClick={addSheet}>
            <Plus size={15} />
          </button>
          <button type="button" aria-label="重命名当前工作表" onClick={() => renameSheet(sheet)}>
            <Pencil size={14} />
          </button>
          <button
            type="button"
            aria-label="删除当前工作表"
            disabled={workbook.sheets.length <= 1}
            onClick={deleteActiveSheet}
          >
            <Trash2 size={15} />
          </button>
        </div>
        <span>
          <CornerDownLeft size={14} />
          {filteredRows.size ? `已筛除 ${filteredRows.size} 行 · ` : ''}Enter / Tab 换格 · 拖拽多选
        </span>
      </footer>
    </div>
  );
}
