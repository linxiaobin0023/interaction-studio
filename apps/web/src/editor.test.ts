import { test } from "node:test";
import assert from "node:assert/strict";
import {
  applyTemplate,
  change,
  equal,
  point,
  redo,
  undo,
  type History,
} from "./editor.ts";
import type { Request } from "./types.ts";
const base: Request = {
  case_id: "DEV_MOUTH_001",
  placement: {
    center_x: 0.5,
    center_y: 0.5,
    width_ratio: 0.13,
    rotation_degrees: 0,
  },
  product_view_id: "FRONT_00",
  core_inset_px: 4,
  contact_radius_px: 12,
  occlusion_polygons: [],
};
test("undo/redo restores exact parameters without mutating snapshots", () => {
  const original = structuredClone(base);
  const start: History = { past: [], present: original, future: [] };
  const changed = change(start, {
    ...original,
    placement: { ...original.placement, center_x: 0.7 },
  });
  assert.equal(start.present.placement.center_x, 0.5);
  assert.deepEqual(undo(changed).present, original);
  assert.deepEqual(redo(undo(changed)).present, changed.present);
});
test("new change after undo clears abandoned redo history", () => {
  const first = change(
    { past: [], present: base, future: [] },
    { ...base, contact_radius_px: 20 },
  );
  const second = change(undo(first), { ...base, core_inset_px: 8 });
  assert.equal(second.future.length, 0);
  assert.equal(redo(second), second);
});
test("repeated identical value does not create an undo entry", () => {
  const start: History = { past: [], present: base, future: [] };
  assert.equal(change(start, structuredClone(base)), start);
});
test("pointer coordinates account for artboard position, dimensions and bounds", () => {
  const bounds = { left: 100, top: 200, width: 800, height: 600 };
  assert.deepEqual(point(500, 500, bounds), [0.5, 0.5]);
  assert.deepEqual(point(-50, 900, bounds), [0, 1]);
});
test("template application keeps selected case and separates mutable polygons", () => {
  const template = {
    ...base,
    case_id: "DEV_MOUTH_002",
    occlusion_polygons: [
      [
        [0.1, 0.1],
        [0.2, 0.1],
        [0.2, 0.2],
      ] as [number, number][],
    ],
  };
  const applied = applyTemplate(base, template);
  assert.equal(applied.case_id, base.case_id);
  applied.occlusion_polygons[0][0][0] = 0.9;
  assert.equal(template.occlusion_polygons[0][0][0], 0.1);
  assert.ok(!equal(applied, base));
});

test("occlusion rejects collinear or incomplete outlines", async () => {
  const { validPolygon } = await import("./editor.ts");
  assert.equal(
    validPolygon([
      [0.1, 0.1],
      [0.2, 0.2],
      [0.3, 0.3],
    ]),
    false,
  );
  assert.equal(
    validPolygon([
      [0, 0],
      [1, 0],
    ]),
    false,
  );
  assert.equal(
    validPolygon([
      [0.1, 0.1],
      [0.4, 0.1],
      [0.4, 0.4],
    ]),
    true,
  );
});
