import type { ComputationDef } from '../../api/backendRequests';

export type SchemaMap = Record<string, { name: string; type: string }[]>;

export const getFieldType = (schemas: SchemaMap, dataset: string | undefined, col: string): string | undefined => {
  if (!dataset || !schemas[dataset]) return undefined;
  const entry = schemas[dataset]?.find((f) => f.name === col);
  return entry?.type;
};

export const sparkTypeToCat = (t?: string): 'number' | 'string' | 'boolean' | 'other' => {
  const s = (t || '').toLowerCase();
  if (!s) return 'other';
  if (s === 'string' || s.startsWith('varchar') || s.startsWith('char')) return 'string';
  if (s === 'boolean') return 'boolean';
  if (
    s === 'byte' ||
    s === 'short' ||
    s === 'int' ||
    s === 'integer' ||
    s === 'long' ||
    s === 'float' ||
    s === 'double' ||
    s.startsWith('decimal')
  )
    return 'number';
  return 'other';
};

export const validateDefinition = (
  defObj: unknown,
  dataset: string | undefined,
  schemas: SchemaMap
): string[] => {
  const errs: string[] = [];
  if (!defObj || typeof defObj !== 'object' || Array.isArray(defObj)) {
    errs.push('Definition must be a JSON object.');
    return errs;
  }
  const obj = defObj as Record<string, unknown>;

  // select
  if (Object.prototype.hasOwnProperty.call(obj, 'select')) {
    const sel = obj.select as unknown;
    if (!Array.isArray(sel)) errs.push('select must be an array of column names.');
    else (sel as unknown[]).forEach((c, i) => {
      if (typeof c !== 'string') errs.push(`select[${i}] must be a string.`);
      else if (dataset && schemas[dataset] && !getFieldType(schemas, dataset, c)) errs.push(`select column not found: ${c}`);
    });
  }

  // where
  if (Object.prototype.hasOwnProperty.call(obj, 'where')) {
    const where = obj.where as unknown;
    if (!Array.isArray(where)) errs.push('where must be an array of conditions.');
    else (where as unknown[]).forEach((w, i) => {
      if (!w || typeof w !== 'object' || Array.isArray(w)) {
        errs.push(`where[${i}] must be an object.`);
        return;
      }
      const wObj = w as Record<string, unknown>;
      const col = wObj.col as unknown;
      const op = wObj.op as unknown;
      const value = wObj.value as unknown;
      if (typeof col !== 'string') errs.push(`where[${i}].col must be a string.`);
      const t = typeof col === 'string' ? getFieldType(schemas, dataset, col) : undefined;
      if (dataset && schemas[dataset] && typeof col === 'string' && !t) errs.push(`where column not found: ${col}`);
      if (typeof op !== 'string') errs.push(`where[${i}].op must be a string.`);
      const typeCat = sparkTypeToCat(t);
      // operator compatibility
      const strOps = new Set(['==', '!=', 'contains']);
      const numOps = new Set(['>', '>=', '<', '<=', '==', '!=']);
      const boolOps = new Set(['==', '!=']);
      if (typeof op === 'string') {
        if (typeCat === 'string' && !strOps.has(op)) errs.push(`where[${i}]: op ${op} not valid for string`);
        if (typeCat === 'number' && !numOps.has(op)) errs.push(`where[${i}]: op ${op} not valid for number`);
        if (typeCat === 'boolean' && !boolOps.has(op)) errs.push(`where[${i}]: op ${op} not valid for boolean`);
      }
      // value type checks (soft)
      if (typeCat === 'number' && typeof value !== 'number') errs.push(`where[${i}].value should be a number for column ${String(col)}`);
      if (typeCat === 'boolean' && typeof value !== 'boolean') errs.push(`where[${i}].value should be a boolean for column ${String(col)}`);
      if (typeCat === 'string' && op === 'contains' && typeof value !== 'string') errs.push(`where[${i}].value should be a string for contains`);
    });
  }

  // orderBy
  if (Object.prototype.hasOwnProperty.call(obj, 'orderBy')) {
    const order = obj.orderBy as unknown;
    if (!Array.isArray(order)) errs.push('orderBy must be an array of { col, dir }');
    else (order as unknown[]).forEach((o, i) => {
      if (!o || typeof o !== 'object' || Array.isArray(o)) {
        errs.push(`orderBy[${i}] must be an object.`);
        return;
      }
      const oObj = o as Record<string, unknown>;
      const col = oObj.col as unknown;
      const dir = oObj.dir as unknown;
      if (typeof col !== 'string') errs.push(`orderBy[${i}].col must be a string.`);
      else if (dataset && schemas[dataset] && !getFieldType(schemas, dataset, col)) errs.push(`orderBy column not found: ${String(col)}`);
      if (dir !== undefined) {
        if (typeof dir !== 'string' || !['asc', 'desc'].includes(dir.toLowerCase())) errs.push(`orderBy[${i}].dir must be 'asc' or 'desc'`);
      }
    });
  }

  // limit
  if (Object.prototype.hasOwnProperty.call(obj, 'limit')) {
    const lim = (obj as Record<string, unknown>).limit as unknown;
    if (typeof lim !== 'number' || !Number.isInteger(lim) || lim <= 0) errs.push('limit must be a positive integer.');
  }
  return errs;
};

export type OnEditChange = (updater: (prev: ComputationDef) => ComputationDef) => void;
