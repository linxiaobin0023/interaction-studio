import { useEffect, useState } from "react";
import { api, errorText } from "./api";

export type Job = {
  id: string;
  case_id: string;
  state: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED";
  created_at: string;
  error_code: string | null;
  review_version: number;
};
export type QualityMetric = {
  passed: number;
  reviewed: number;
  rate: number | null;
};
export type Summary = {
  counts: Record<Job["state"], number>;
  pending_review: number;
  queue: Job[];
  recent_failures: Job[];
  quality: Record<string, QualityMetric>;
  technical_pass_rate: number | null;
  attempt1_pass_rate: number | null;
  average_manual_seconds: number | null;
};
export const dimensionNames: Record<string, string> = {
  product: "Product · 商品",
  interaction: "Interaction · 交互",
  identity: "Identity · 身份",
  scene: "Scene · 场景",
  overall: "Overall · 整体",
};
export const jobStates: Record<Job["state"], string> = {
  QUEUED: "排队中",
  RUNNING: "处理中",
  SUCCEEDED: "已完成",
  FAILED: "处理失败",
};
export const failureNames: Record<string, string> = {
  PRODUCT_RESIDUAL_EXCEEDED: "商品视角不匹配",
  PLACEMENT_CLIPS_PRODUCT: "商品超出画面",
  VISIBLE_PRODUCT_CORE_EMPTY: "商品核心被完全遮挡",
  JOB_SOURCE_CHANGED: "任务素材已变化",
  WORKER_RETRY_EXHAUSTED: "工作进程多次中断",
};

export function useRemote<T>(path: string, interval = 0) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    setLoading(true);
    setData(undefined);
    setError("");
    async function read() {
      try {
        const value = await api<T>(path, { signal: controller.signal });
        if (!controller.signal.aborted) {
          setData(value);
          setError("");
        }
      } catch (e) {
        if (!controller.signal.aborted) setError(errorText(e));
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
          if (interval) timer = setTimeout(read, interval);
        }
      }
    }
    void read();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [path, interval, revision]);
  return { data, error, loading, refresh: () => setRevision((v) => v + 1) };
}

export const pages = {
  dashboard: "生产概览",
  cases: "案例中心",
  studio: "生成工作台",
  review: "质量评审",
  assets: "素材中心",
  preflight: "Preflight 中心",
  algorithms: "算法与模板",
  workflows: "模型与工作流",
  "test-runs": "批量测试中心",
  analytics: "效果分析",
  trace: "过程追踪 / Replay",
};
export type Page = keyof typeof pages;
export function readRoute(hash: string): {
  page: Page | "missing";
  caseId?: string;
} {
  const path = hash.replace(/^#\/?/, "");
  if (!path) return { page: "dashboard" };
  const studio = /^cases\/(DEV_(?:MOUTH|NEAR|HAND)_\d{3})\/studio$/.exec(path);
  if (studio) return { page: "studio", caseId: studio[1] };
  if (Object.hasOwn(pages, path)) return { page: path as Page };
  return { page: "missing" };
}
export const caseRoute = (id: string) =>
  `#/cases/${encodeURIComponent(id)}/studio`;
