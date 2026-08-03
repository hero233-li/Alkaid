import { describe, expect, it } from 'vitest';
import { evaluateGridCell, translateFormulaReferences } from './tableFormula';

describe('online spreadsheet formula engine', () => {
  it('calculates references, ranges and nested functions', () => {
    const grid = [
      ['10', '20', '=A1+B1', '=SUM(A1:C1)'],
      ['4', '=AVERAGE(A1:B1)', '=ROUND(10/3,2)', '=POWER(A2,2)'],
    ];

    expect(evaluateGridCell(grid, 0, 2).value).toBe('30');
    expect(evaluateGridCell(grid, 0, 3).value).toBe('60');
    expect(evaluateGridCell(grid, 1, 1).value).toBe('15');
    expect(evaluateGridCell(grid, 1, 2).value).toBe('3.33');
    expect(evaluateGridCell(grid, 1, 3).value).toBe('16');
  });

  it('supports logical, text and statistical functions', () => {
    const grid = [
      ['80', '合格', '=IF(A1>=60,"通过","未通过")'],
      ['20', '', '=CONCAT(B1,"-",C1)'],
      ['=COUNT(A1:A2)', '=COUNTA(B1:B2)', '=AND(A1>A2,NOT(FALSE))'],
    ];

    expect(evaluateGridCell(grid, 0, 2).value).toBe('通过');
    expect(evaluateGridCell(grid, 1, 2).value).toBe('合格-通过');
    expect(evaluateGridCell(grid, 2, 0).value).toBe('2');
    expect(evaluateGridCell(grid, 2, 1).value).toBe('1');
    expect(evaluateGridCell(grid, 2, 2).value).toBe('TRUE');
  });

  it('reports spreadsheet errors', () => {
    const grid = [['=1/0', '=B1', '=UNKNOWN(1)', '=Z99']];

    expect(evaluateGridCell(grid, 0, 0).value).toBe('#DIV/0!');
    expect(evaluateGridCell(grid, 0, 1).value).toBe('#CYCLE!');
    expect(evaluateGridCell(grid, 0, 2).value).toBe('#NAME?');
    expect(evaluateGridCell(grid, 0, 3).value).toBe('#REF!');
  });

  it('moves relative references while preserving absolute references during fill', () => {
    expect(translateFormulaReferences('=A1+$B1+C$2+$D$4', 2, 1)).toBe('=B3+$B3+D$2+$D$4');
    expect(translateFormulaReferences('=SUM(A1:B2)', 1, 2)).toBe('=SUM(C2:D3)');
  });
});
