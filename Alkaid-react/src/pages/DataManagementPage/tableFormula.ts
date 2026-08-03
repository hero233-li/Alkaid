import type { MarkdownTableGrid } from './model';

export interface FormulaResult {
  value: string;
  calculated: boolean;
}

type FormulaValue = number | string | boolean;

interface FormulaRange {
  range: FormulaValue[];
}

type ParsedValue = FormulaValue | FormulaRange;

const isRange = (value: ParsedValue): value is FormulaRange =>
  typeof value === 'object' && value !== null && 'range' in value;

const columnIndex = (label: string) => {
  let value = 0;
  for (const character of label.toUpperCase()) value = value * 26 + character.charCodeAt(0) - 64;
  return value - 1;
};

const columnLabel = (index: number) => {
  let value = index + 1;
  let label = '';
  while (value > 0) {
    value -= 1;
    label = String.fromCharCode(65 + (value % 26)) + label;
    value = Math.floor(value / 26);
  }
  return label;
};

const cellPosition = (reference: string) => {
  const match = /^\$?([A-Z]+)\$?(\d+)$/i.exec(reference.trim());
  if (!match) return null;
  return { row: Number(match[2]) - 1, column: columnIndex(match[1]) };
};

const asNumber = (value: ParsedValue) => {
  if (isRange(value)) throw new Error('VALUE');
  if (typeof value === 'boolean') return value ? 1 : 0;
  if (value === '') return 0;
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) throw new Error('VALUE');
  return numeric;
};

const asBoolean = (value: ParsedValue): boolean => {
  if (isRange(value)) return value.range.some((item) => asBoolean(item));
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return value !== 0;
  return value.trim() !== '' && value.toUpperCase() !== 'FALSE';
};

const scalar = (value: ParsedValue): FormulaValue => {
  if (isRange(value)) throw new Error('VALUE');
  return value;
};

const flatten = (values: ParsedValue[]) =>
  values.flatMap((value) => (isRange(value) ? value.range : [value]));

const numericValues = (values: ParsedValue[]) =>
  flatten(values)
    .filter((value) => value !== '' && typeof value !== 'boolean')
    .map(Number)
    .filter(Number.isFinite);

class FormulaParser {
  private index = 0;

  constructor(
    private readonly expression: string,
    private readonly resolveCell: (reference: string) => FormulaValue,
    private readonly resolveRange: (start: string, end: string) => FormulaValue[],
  ) {}

  parse() {
    const value = this.comparison();
    this.skipSpaces();
    if (this.index !== this.expression.length) throw new Error('ERROR');
    return scalar(value);
  }

  private comparison(): ParsedValue {
    let value = this.sum();
    while (true) {
      this.skipSpaces();
      const operator = /^(<=|>=|<>|=|<|>)/.exec(this.expression.slice(this.index))?.[0];
      if (!operator) return value;
      this.index += operator.length;
      const right = this.sum();
      const leftValue = scalar(value);
      const rightValue = scalar(right);
      if (operator === '=') value = leftValue === rightValue;
      else if (operator === '<>') value = leftValue !== rightValue;
      else {
        const leftNumber = asNumber(leftValue);
        const rightNumber = asNumber(rightValue);
        if (operator === '<') value = leftNumber < rightNumber;
        else if (operator === '>') value = leftNumber > rightNumber;
        else if (operator === '<=') value = leftNumber <= rightNumber;
        else value = leftNumber >= rightNumber;
      }
    }
  }

  private sum(): ParsedValue {
    let value = this.product();
    while (true) {
      this.skipSpaces();
      const operator = this.expression[this.index];
      if (operator !== '+' && operator !== '-') return value;
      this.index += 1;
      const next = this.product();
      value =
        operator === '+' ? asNumber(value) + asNumber(next) : asNumber(value) - asNumber(next);
    }
  }

  private product(): ParsedValue {
    let value = this.power();
    while (true) {
      this.skipSpaces();
      const operator = this.expression[this.index];
      if (operator !== '*' && operator !== '/') return value;
      this.index += 1;
      const next = asNumber(this.power());
      if (operator === '/' && next === 0) throw new Error('DIV0');
      value = operator === '*' ? asNumber(value) * next : asNumber(value) / next;
    }
  }

  private power(): ParsedValue {
    let value = this.unary();
    this.skipSpaces();
    if (this.expression[this.index] === '^') {
      this.index += 1;
      value = Math.pow(asNumber(value), asNumber(this.power()));
    }
    return value;
  }

  private unary(): ParsedValue {
    this.skipSpaces();
    if (this.expression[this.index] === '+' || this.expression[this.index] === '-') {
      const sign = this.expression[this.index] === '-' ? -1 : 1;
      this.index += 1;
      return sign * asNumber(this.unary());
    }
    return this.primary();
  }

  private primary(): ParsedValue {
    this.skipSpaces();
    if (this.expression.slice(this.index).toUpperCase().startsWith('#REF!')) {
      throw new Error('REF');
    }
    if (this.expression[this.index] === '(') {
      this.index += 1;
      const value = this.comparison();
      this.skipSpaces();
      if (this.expression[this.index] !== ')') throw new Error('ERROR');
      this.index += 1;
      return value;
    }
    if (this.expression[this.index] === '"') return this.stringLiteral();
    const numberMatch = /^(?:\d+(?:\.\d*)?|\.\d+)/.exec(this.expression.slice(this.index));
    if (numberMatch) {
      this.index += numberMatch[0].length;
      let value = Number(numberMatch[0]);
      this.skipSpaces();
      if (this.expression[this.index] === '%') {
        this.index += 1;
        value /= 100;
      }
      return value;
    }
    const referenceMatch = /^\$?[A-Z]+\$?\d+/i.exec(this.expression.slice(this.index));
    if (referenceMatch) {
      const start = referenceMatch[0];
      this.index += start.length;
      this.skipSpaces();
      if (this.expression[this.index] === ':') {
        this.index += 1;
        this.skipSpaces();
        const endMatch = /^\$?[A-Z]+\$?\d+/i.exec(this.expression.slice(this.index));
        if (!endMatch) throw new Error('REF');
        this.index += endMatch[0].length;
        return { range: this.resolveRange(start, endMatch[0]) };
      }
      return this.resolveCell(start);
    }
    const identifierMatch = /^[A-Z_]+/i.exec(this.expression.slice(this.index));
    if (!identifierMatch) throw new Error('ERROR');
    const name = identifierMatch[0].toUpperCase();
    this.index += identifierMatch[0].length;
    if (name === 'TRUE') return true;
    if (name === 'FALSE') return false;
    this.skipSpaces();
    if (this.expression[this.index] !== '(') throw new Error('NAME');
    this.index += 1;
    const args: ParsedValue[] = [];
    this.skipSpaces();
    if (this.expression[this.index] !== ')') {
      while (true) {
        args.push(this.comparison());
        this.skipSpaces();
        if (this.expression[this.index] !== ',') break;
        this.index += 1;
      }
    }
    if (this.expression[this.index] !== ')') throw new Error('ERROR');
    this.index += 1;
    return this.callFunction(name, args);
  }

  private stringLiteral() {
    this.index += 1;
    let value = '';
    while (this.index < this.expression.length) {
      const character = this.expression[this.index];
      if (character === '"') {
        if (this.expression[this.index + 1] === '"') {
          value += '"';
          this.index += 2;
          continue;
        }
        this.index += 1;
        return value;
      }
      value += character;
      this.index += 1;
    }
    throw new Error('ERROR');
  }

  private callFunction(name: string, args: ParsedValue[]): FormulaValue {
    const numbers = numericValues(args);
    if (name === 'SUM') return numbers.reduce((sum, value) => sum + value, 0);
    if (name === 'AVERAGE')
      return numbers.length ? numbers.reduce((a, b) => a + b, 0) / numbers.length : 0;
    if (name === 'MIN') return numbers.length ? Math.min(...numbers) : 0;
    if (name === 'MAX') return numbers.length ? Math.max(...numbers) : 0;
    if (name === 'COUNT') return numbers.length;
    if (name === 'COUNTA')
      return flatten(args).filter((value) => String(value).trim() !== '').length;
    if (name === 'ROUND')
      return (
        Math.round(asNumber(args[0] ?? 0) * 10 ** asNumber(args[1] ?? 0)) /
        10 ** asNumber(args[1] ?? 0)
      );
    if (name === 'ABS') return Math.abs(asNumber(args[0] ?? 0));
    if (name === 'SQRT') return Math.sqrt(asNumber(args[0] ?? 0));
    if (name === 'POWER') return Math.pow(asNumber(args[0] ?? 0), asNumber(args[1] ?? 0));
    if (name === 'IF')
      return asBoolean(args[0] ?? false) ? scalar(args[1] ?? true) : scalar(args[2] ?? false);
    if (name === 'AND') return args.every(asBoolean);
    if (name === 'OR') return args.some(asBoolean);
    if (name === 'NOT') return !asBoolean(args[0] ?? false);
    if (name === 'CONCAT') return flatten(args).join('');
    throw new Error('NAME');
  }

  private skipSpaces() {
    while (/\s/.test(this.expression[this.index] || '')) this.index += 1;
  }
}

const formatValue = (value: FormulaValue) => {
  if (typeof value === 'boolean') return value ? 'TRUE' : 'FALSE';
  if (typeof value === 'number') return String(Math.round(value * 1_000_000_000) / 1_000_000_000);
  return value;
};

export function evaluateGridCell(
  grid: MarkdownTableGrid,
  row: number,
  column: number,
  visiting = new Set<string>(),
): FormulaResult {
  const raw = grid[row]?.[column] || '';
  if (!raw.startsWith('=')) return { value: raw, calculated: false };
  const key = `${row}:${column}`;
  if (visiting.has(key)) return { value: '#CYCLE!', calculated: true };
  const nextVisiting = new Set(visiting).add(key);

  const resolveCell = (reference: string): FormulaValue => {
    const position = cellPosition(reference);
    if (
      !position ||
      position.row < 0 ||
      position.column < 0 ||
      position.row >= grid.length ||
      position.column >= (grid[position.row]?.length || 0)
    )
      throw new Error('REF');
    const result = evaluateGridCell(grid, position.row, position.column, nextVisiting);
    if (result.value.startsWith('#')) throw new Error(result.value);
    if (result.value.trim() !== '' && Number.isFinite(Number(result.value)))
      return Number(result.value);
    return result.value;
  };

  const resolveRange = (startReference: string, endReference: string) => {
    const start = cellPosition(startReference);
    const end = cellPosition(endReference);
    if (!start || !end) throw new Error('REF');
    const values: FormulaValue[] = [];
    for (
      let currentRow = Math.min(start.row, end.row);
      currentRow <= Math.max(start.row, end.row);
      currentRow += 1
    ) {
      for (
        let currentColumn = Math.min(start.column, end.column);
        currentColumn <= Math.max(start.column, end.column);
        currentColumn += 1
      ) {
        values.push(resolveCell(`${columnLabel(currentColumn)}${currentRow + 1}`));
      }
    }
    return values;
  };

  try {
    const value = new FormulaParser(raw.slice(1), resolveCell, resolveRange).parse();
    return { value: formatValue(value), calculated: true };
  } catch (error) {
    const reason = error instanceof Error ? error.message : 'ERROR';
    if (reason === 'DIV0') return { value: '#DIV/0!', calculated: true };
    if (reason === '#CYCLE!') return { value: '#CYCLE!', calculated: true };
    if (reason === 'REF') return { value: '#REF!', calculated: true };
    if (reason === 'VALUE') return { value: '#VALUE!', calculated: true };
    if (reason === 'NAME') return { value: '#NAME?', calculated: true };
    return { value: '#ERROR!', calculated: true };
  }
}

export function translateFormulaReferences(formula: string, rowDelta: number, columnDelta: number) {
  if (!formula.startsWith('=')) return formula;
  return formula.replace(/(\$?)([A-Z]+)(\$?)(\d+)/gi, (_, lockColumn, label, lockRow, row) => {
    const nextColumn = columnIndex(label) + (lockColumn ? 0 : columnDelta);
    const nextRow = Number(row) - 1 + (lockRow ? 0 : rowDelta);
    if (nextColumn < 0 || nextRow < 0) return '#REF!';
    return `${lockColumn}${columnLabel(nextColumn)}${lockRow}${nextRow + 1}`;
  });
}
