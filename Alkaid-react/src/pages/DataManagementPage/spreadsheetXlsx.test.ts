import { describe, expect, it } from 'vitest';
import { createDefaultSpreadsheetWorkbook } from './model';
import { importSpreadsheetXlsx, writeSpreadsheetXlsx } from './spreadsheetXlsx';

describe('online spreadsheet xlsx bridge', () => {
  it('round-trips multiple sheets, formulas, merges, dimensions and Alioth settings', async () => {
    const workbook = createDefaultSpreadsheetWorkbook(4, 4);
    const first = workbook.sheets[0];
    first.name = '预算';
    first.cells[0][0] = '项目';
    first.cells[1][0] = '收入';
    first.cells[1][1] = '100';
    first.cells[1][2] = '=B2*2';
    first.styles['1:1'] = {
      horizontal: 'right',
      bold: true,
      italic: true,
      numberFormat: 'currency',
      decimalPlaces: 2,
    };
    first.columnWidths[0] = 180;
    first.rowHeights[0] = 44;
    first.freezeRows = 1;
    first.filters['0'] = '收入';
    first.validations['1:1'] = {
      type: 'wholeNumber',
      allowBlank: false,
      minimum: 0,
      maximum: 1_000,
    };
    first.merges.push({ startRow: 2, startColumn: 0, endRow: 2, endColumn: 2 });
    const second = createDefaultSpreadsheetWorkbook(3, 3).sheets[0];
    second.id = 'sheet-2';
    second.name = '明细';
    second.cells[0][0] = '客户';
    workbook.sheets.push(second);

    const xlsx = await writeSpreadsheetXlsx(workbook);
    const restored = await importSpreadsheetXlsx(xlsx);

    expect(restored.sheets.map((sheet) => sheet.name)).toEqual(['预算', '明细']);
    expect(restored.sheets[0].cells[1].slice(0, 3)).toEqual(['收入', '100', '=B2*2']);
    expect(restored.sheets[0].merges[0]).toEqual(first.merges[0]);
    expect(restored.sheets[0].columnWidths[0]).toBe(180);
    expect(restored.sheets[0].rowHeights[0]).toBe(44);
    expect(restored.sheets[0].freezeRows).toBe(1);
    expect(restored.sheets[0].filters).toEqual({ '0': '收入' });
    expect(restored.sheets[0].validations['1:1']).toEqual(first.validations['1:1']);
    expect(restored.sheets[0].styles['1:1']).toMatchObject({
      horizontal: 'right',
      bold: true,
      italic: true,
      numberFormat: 'currency',
    });
  });
});
