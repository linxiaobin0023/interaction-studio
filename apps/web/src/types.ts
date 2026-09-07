export type Placement = {
  center_x: number;
  center_y: number;
  width_ratio: number;
  rotation_degrees: number;
};
export type Request = {
  case_id: string;
  placement: Placement;
  product_revision?: "v1" | "v2";
  product_view_id: string;
  core_inset_px: number;
  contact_radius_px: number;
  occlusion_polygons: [number, number][][];
};
export type Case = {
  case_id: string;
  interaction: "MOUTH" | "NEAR_MOUTH" | "HAND_HELD";
  pose_zone: string;
  width: number;
  height: number;
  sha256: string;
  suggestion: {
    placement: Placement;
    anchor_method: string;
    product_revision?: "v1" | "v2";
    product_view_id: string;
    residual: { yaw: number; pitch: number; within_gate: boolean };
  };
};
export type Catalog = {
  cases: Case[];
  product_views: { view_id: string; yaw: number; pitch: number }[];
  provenance: { dataset_manifest_sha256: string };
};
export const labels = {
  MOUTH: "嘴部含咬",
  NEAR_MOUTH: "靠近嘴部",
  HAND_HELD: "手持交互",
};
export function initial(c: Case): Request {
  return {
    case_id: c.case_id,
    placement: { ...c.suggestion.placement },
    product_view_id: c.suggestion.product_view_id,
    product_revision: c.suggestion.product_revision ?? "v2",
    core_inset_px: 4,
    contact_radius_px: 12,
    occlusion_polygons: [],
  };
}
export type Event = {
  sequence_no: number;
  action: string;
  occurred_at: string;
  before: Partial<Request>;
  after: Request;
  event_hash: string;
  previous_hash: string | null;
};
export type Draft = {
  case_id: string;
  resource_version: number;
  manifest_sha256: string;
  case_base_sha256: string;
  parameters: Request;
};
export type DraftResponse = {
  draft: Draft;
  events: Event[];
  history_verified: boolean;
};
export type Template = {
  id: string;
  name: string;
  version: number;
  interaction: Case["interaction"];
  manifest_sha256: string;
  parameters: Request;
  content_sha256: string;
};
