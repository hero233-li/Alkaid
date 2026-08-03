import {
  createDefaultSpreadsheetWorkbook,
  type SpreadsheetCellStyle,
  type SpreadsheetSheet,
  type SpreadsheetWorkbook,
} from './model';

const METADATA_SHEET_NAME = '__AliothMetadata';
const MAX_IMPORT_ROWS = 1_000;
const MAX_IMPORT_COLUMNS = 100;

type XlsxModule = typeof import('xlsx');

function normalizeSheetName(name: string, index: number) {
  return name.replace(/[\\/?*:[\]]/g, '-').slice(0, 31) || `工作表 ${index + 1}`;
}

function cellText(cell: import('xlsx').CellObject | undefined) {
  if (!cell) return '';
  if (cell.f) return `=${cell.f}`;
  if (cell.v instanceof Date) return cell.v.toISOString().slice(0, 10);
  return cell.v === undefined || cell.v === null ? '' : String(cell.v);
}

function spreadsheetColor(value?: string) {
  if (!value) return undefined;
  return `#${value.slice(-6)}`;
}

function importSheet(
  XLSX: XlsxModule,
  name: string,
  source: import('xlsx').WorkSheet,
  index: number,
): SpreadsheetSheet {
  const range = XLSX.utils.decode_range(source['!ref'] || 'A1');
  const rowCount = Math.max(30, Math.min(MAX_IMPORT_ROWS, range.e.r + 1));
  const columnCount = Math.max(12, Math.min(MAX_IMPORT_COLUMNS, range.e.c + 1));
  const cells = Array.from({ length: rowCount }, (_, row) =>
    Array.from({ length: columnCount }, (_, column) =>
      cellText(source[XLSX.utils.encode_cell({ r: row, c: column })]),
    ),
  );
  const styles: Record<string, SpreadsheetCellStyle> = {};
  for (let row = 0; row < rowCount; row += 1) {
    for (let column = 0; column < columnCount; column += 1) {
      const cell = source[XLSX.utils.encode_cell({ r: row, c: column })] as
        | (import('xlsx').CellObject & {
            s?: {
              alignment?: {
                horizontal?: string;
                vertical?: string;
                wrapText?: boolean;
                indent?: number;
              };
              font?: {
                bold?: boolean;
                italic?: boolean;
                underline?: boolean;
                strike?: boolean;
                name?: string;
                sz?: number;
                color?: { rgb?: string };
              };
              fill?: { fgColor?: { rgb?: string } };
              border?: object;
            };
          })
        | undefined;
      if (!cell?.s) continue;
      const horizontal = cell.s.alignment?.horizontal;
      const numberFormat = typeof cell.z === 'string' ? cell.z : '';
      styles[`${row}:${column}`] = {
        horizontal:
          horizontal === 'center' || horizontal === 'right' || horizontal === 'left'
            ? horizontal
            : undefined,
        wrap: cell.s.alignment?.wrapText,
        bold: cell.s.font?.bold,
        italic: cell.s.font?.italic,
        underline: cell.s.font?.underline,
        strike: cell.s.font?.strike,
        fontFamily: cell.s.font?.name,
        fontSize: cell.s.font?.sz,
        textColor: spreadsheetColor(cell.s.font?.color?.rgb),
        fillColor: spreadsheetColor(cell.s.fill?.fgColor?.rgb),
        border: Boolean(cell.s.border && Object.keys(cell.s.border).length),
        indent: cell.s.alignment?.indent,
        vertical:
          cell.s.alignment?.vertical === 'top' || cell.s.alignment?.vertical === 'bottom'
            ? cell.s.alignment.vertical
            : cell.s.alignment?.vertical === 'center'
              ? 'middle'
              : undefined,
        numberFormat: numberFormat.includes('%')
          ? 'percent'
          : /[$¥￥]/.test(numberFormat)
            ? 'currency'
            : numberFormat && numberFormat !== 'General'
              ? 'number'
              : undefined,
      };
    }
  }
  return {
    id: `sheet-${Date.now()}-${index}`,
    name: normalizeSheetName(name, index),
    rowCount,
    columnCount,
    cells,
    styles,
    merges: (source['!merges'] || []).map((merge) => ({
      startRow: merge.s.r,
      startColumn: merge.s.c,
      endRow: merge.e.r,
      endColumn: merge.e.c,
    })),
    columnWidths: Array.from({ length: columnCount }, (_, column) => {
      const definition = source['!cols']?.[column];
      return Math.max(56, Math.min(480, definition?.wpx || (definition?.wch || 14) * 8));
    }),
    rowHeights: Array.from({ length: rowCount }, (_, row) =>
      Math.max(24, Math.min(240, source['!rows']?.[row]?.hpx || 32)),
    ),
    freezeRows: 0,
    freezeColumns: 0,
    filters: {},
    validations: {},
  };
}

export async function importSpreadsheetXlsx(data: ArrayBuffer): Promise<SpreadsheetWorkbook> {
  const XLSX = await import('xlsx');
  const sourceWorkbook = XLSX.read(data, {
    type: 'array',
    cellDates: true,
    cellFormula: true,
    cellStyles: true,
  });
  const names = sourceWorkbook.SheetNames.filter((name) => name !== METADATA_SHEET_NAME);
  if (!names.length) return createDefaultSpreadsheetWorkbook();
  const sheets = names.map((name, index) =>
    importSheet(XLSX, name, sourceWorkbook.Sheets[name], index),
  );
  const metadataCell = sourceWorkbook.Sheets[METADATA_SHEET_NAME]?.A1;
  if (typeof metadataCell?.v === 'string') {
    try {
      const metadata = JSON.parse(metadataCell.v) as Record<
        string,
        Pick<
          SpreadsheetSheet,
          'freezeRows' | 'freezeColumns' | 'filters' | 'validations' | 'styles'
        >
      >;
      sheets.forEach((sheet) => {
        const settings = metadata[sheet.name];
        if (settings) Object.assign(sheet, settings);
      });
    } catch {
      // 普通 Excel 文件没有 Alioth 元数据时，按通用工作簿导入。
    }
  }
  return {
    format: 'alioth-spreadsheet',
    version: 1,
    activeSheetId: sheets[0].id,
    sheets,
  };
}

export async function writeSpreadsheetXlsx(workbook: SpreadsheetWorkbook) {
  const XLSX = await import('xlsx');
  const target = XLSX.utils.book_new();
  workbook.sheets.forEach((sheet, sheetIndex) => {
    const worksheet: import('xlsx').WorkSheet = {};
    let lastRow = 0;
    let lastColumn = 0;
    sheet.cells.forEach((row, rowIndex) =>
      row.forEach((raw, columnIndex) => {
        if (!raw) return;
        lastRow = Math.max(lastRow, rowIndex);
        lastColumn = Math.max(lastColumn, columnIndex);
        const address = XLSX.utils.encode_cell({ r: rowIndex, c: columnIndex });
        const style = sheet.styles[`${rowIndex}:${columnIndex}`];
        const cell: import('xlsx').CellObject & { s?: object } = raw.startsWith('=')
          ? { t: 'n', f: raw.slice(1) }
          : raw.trim() !== '' && Number.isFinite(Number(raw))
            ? { t: 'n', v: Number(raw) }
            : { t: 's', v: raw };
        if (style) {
          const border = { style: 'thin', color: { rgb: '64748B' } };
          cell.s = {
            alignment: {
              horizontal: style.horizontal,
              vertical: style.vertical === 'middle' ? 'center' : style.vertical,
              wrapText: style.wrap,
              indent: style.indent,
            },
            font: {
              bold: style.bold,
              italic: style.italic,
              underline: style.underline,
              strike: style.strike,
              name: style.fontFamily === 'inherit' ? undefined : style.fontFamily,
              sz: style.fontSize,
              color: style.textColor ? { rgb: style.textColor.replace('#', '') } : undefined,
            },
            fill: style.fillColor
              ? { patternType: 'solid', fgColor: { rgb: style.fillColor.replace('#', '') } }
              : undefined,
            border: style.border
              ? { top: border, right: border, bottom: border, left: border }
              : undefined,
          };
          const decimals = Math.max(0, Math.min(8, style.decimalPlaces || 0));
          if (style.numberFormat === 'number')
            cell.z = `#,##0${decimals ? `.${'0'.repeat(decimals)}` : ''}`;
          if (style.numberFormat === 'percent')
            cell.z = `0${decimals ? `.${'0'.repeat(decimals)}` : ''}%`;
          if (style.numberFormat === 'currency')
            cell.z = `¥#,##0${decimals ? `.${'0'.repeat(decimals)}` : ''}`;
        }
        worksheet[address] = cell;
      }),
    );
    worksheet['!ref'] = XLSX.utils.encode_range({
      s: { r: 0, c: 0 },
      e: { r: lastRow, c: lastColumn },
    });
    worksheet['!cols'] = sheet.columnWidths.map((width) => ({ wpx: width }));
    worksheet['!rows'] = sheet.rowHeights.map((height) => ({ hpx: height }));
    worksheet['!merges'] = sheet.merges.map((merge) => ({
      s: { r: merge.startRow, c: merge.startColumn },
      e: { r: merge.endRow, c: merge.endColumn },
    }));
    if (Object.keys(sheet.filters).length) {
      worksheet['!autofilter'] = {
        ref: XLSX.utils.encode_range({ s: { r: 0, c: 0 }, e: { r: lastRow, c: lastColumn } }),
      };
    }
    XLSX.utils.book_append_sheet(target, worksheet, normalizeSheetName(sheet.name, sheetIndex));
  });
  const metadata = Object.fromEntries(
    workbook.sheets.map((sheet) => [
      normalizeSheetName(sheet.name, 0),
      {
        freezeRows: sheet.freezeRows,
        freezeColumns: sheet.freezeColumns,
        filters: sheet.filters,
        validations: sheet.validations,
        styles: sheet.styles,
      },
    ]),
  );
  XLSX.utils.book_append_sheet(
    target,
    XLSX.utils.aoa_to_sheet([[JSON.stringify(metadata)]]),
    METADATA_SHEET_NAME,
  );
  target.Workbook = {
    Sheets: target.SheetNames.map((name) => ({ Hidden: name === METADATA_SHEET_NAME ? 2 : 0 })),
  };
  return XLSX.write(target, { bookType: 'xlsx', type: 'array', cellStyles: true }) as ArrayBuffer;
}

export async function downloadSpreadsheetXlsx(fileName: string, workbook: SpreadsheetWorkbook) {
  const data = await writeSpreadsheetXlsx(workbook);
  const blob = new Blob([data], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `${fileName.replace(/\.sheet\.json$/i, '').replace(/\.xlsx$/i, '') || '在线表格'}.xlsx`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
