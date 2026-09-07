import type { Request } from "./types.ts";
export type History = { past: Request[]; present: Request; future: Request[] };
export const equal = (a: unknown, b: unknown) =>
  JSON.stringify(a) === JSON.stringify(b);
export function change(history: History, next: Request): History {
  if (equal(history.present, next)) return history;
  return {
    past: [...history.past, history.present].slice(-100),
    present: next,
    future: [],
  };
}
export function undo(history: History): History {
  if (!history.past.length) return history;
  return {
    past: history.past.slice(0, -1),
    present: history.past.at(-1)!,
    future: [history.present, ...history.future],
  };
}
export function redo(history: History): History {
  if (!history.future.length) return history;
  return {
    past: [...history.past, history.present],
    present: history.future[0],
    future: history.future.slice(1),
  };
}
export function point(
  x: number,
  y: number,
  bounds: { left: number; top: number; width: number; height: number },
): [number, number] {
  return [
    Math.max(0, Math.min(1, (x - bounds.left) / bounds.width)),
    Math.max(0, Math.min(1, (y - bounds.top) / bounds.height)),
  ];
}
export function applyTemplate(current: Request, template: Request): Request {
  return { ...structuredClone(template), case_id: current.case_id };
}

export function validPolygon(points: [number, number][]): boolean {
  if (points.length < 3) return false;
  const area = points.reduce((sum, p, i) => {
    const q = points[(i + 1) % points.length];
    return sum + p[0] * q[1] - q[0] * p[1];
  }, 0);
  return Math.abs(area) >= 1e-8;
}
