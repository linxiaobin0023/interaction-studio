import { useEffect, useRef, useState } from "react";
import { useAccount } from "./AccountGate";
import { api, errorText, json } from "./api";
import type { Request } from "./types";
import "./jobs.css";

type Job = {
  id: string;
  case_id: string;
  state: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED";
  created_at: string;
  execution_count: number;
  error_code: string | null;
  output_sha256: string | null;
};
const dimensions = [
  "product",
  "interaction",
  "identity",
  "scene",
  "overall",
] as const;
type Dimension = (typeof dimensions)[number];
type Label = { decision: "" | "PASS" | "FAIL"; reason: string };
type Labels = Record<Dimension, Label>;
type Review = {
  version: number;
  decision: "PASS" | "FAIL";
  occurred_at: string;
  dimensions: Labels;
  content_sha256: string;
};
type Detail = Job & { reviews: Review[] };
const titles: Record<Dimension, string> = {
  product: "产品",
  interaction: "交互",
  identity: "身份",
  scene: "场景",
  overall: "整体",
};
const criteria: Record<Dimension, string> = {
  product: "商品形态、材质和细节是否保留？",
  interaction: "接触位置和遮挡关系是否自然？",
  identity: "人物身份和面部特征是否保留？",
  scene: "背景、光照和画面一致性是否合理？",
  overall: "综合画面是否达到本次开发验证要求？",
};
const states = {
  QUEUED: "排队中",
  RUNNING: "处理中",
  SUCCEEDED: "待查看 / 审核",
  FAILED: "处理失败",
};
const problems: Record<string, string> = {
  PRODUCT_RESIDUAL_EXCEEDED: "商品视角不匹配，请调整视图后重新提交。",
  PLACEMENT_CLIPS_PRODUCT: "商品超出画面，请调整位置或缩小后重新提交。",
  VISIBLE_PRODUCT_CORE_EMPTY: "商品核心被完全遮挡，请调整遮挡或尺寸。",
  QC_VERSION_CONFLICT: "审核记录已更新，请关闭并重新打开结果后再提交。",
  JOB_SOURCE_CHANGED: "任务素材与提交时不一致，请检查素材后重新提交。",
  WORKER_RETRY_EXHAUSTED: "工作进程多次中断，请检查服务后重新提交。",
};
const describe = (e: unknown) => problems[errorText(e)] || errorText(e);
const emptyLabels = (): Labels =>
  Object.fromEntries(
    dimensions.map((key) => [key, { decision: "", reason: "" }]),
  ) as Labels;
const outputURL = (id: string, format: "png" | "bundle") =>
  `/api/v1/development/studio/jobs/${id}/output?format=${format}`;

export function JobsPanel({
  request,
  disabled,
}: {
  request: Request;
  disabled: boolean;
}) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [limit, setLimit] = useState(20);
  const [more, setMore] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  // Reuse the same key after a network failure; a lost response must not create a second job.
  const pending = useRef<{ fingerprint: string; key: string } | null>(null);
  const live = useRef(true);
  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
    };
  }, []);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function poll() {
      try {
        const result = await api<{ jobs: Job[]; has_more: boolean }>(
          `/studio/jobs?case_id=${request.case_id}&limit=${limit}`,
          { signal: controller.signal },
        );
        if (active) {
          setJobs(result.jobs);
          setMore(result.has_more);
          setError("");
        }
      } catch (e) {
        if (active) setError(describe(e));
      }
      if (active) timer = setTimeout(poll, 4000);
    }
    void poll();
    return () => {
      active = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [request.case_id, limit, refresh]);
  async function submit() {
    setBusy(true);
    setError("");
    setNotice("");
    const fingerprint = JSON.stringify(request);
    if (pending.current?.fingerprint !== fingerprint)
      pending.current = { fingerprint, key: crypto.randomUUID() };
    try {
      const job = await api<Job>(
        "/studio/jobs",
        json({ idempotency_key: pending.current.key, parameters: request }),
      );
      if (!live.current) return;
      pending.current = null;
      setNotice(`任务 ${job.id.slice(0, 8)} 已提交，结果会保存在服务端。`);
      setRefresh((v) => v + 1);
    } catch (e) {
      if (live.current) setError(describe(e));
    } finally {
      if (live.current) setBusy(false);
    }
  }
  return (
    <section className="jobs-panel" aria-label="本地处理任务">
      <div className="section-title">
        <h2>处理任务与 QC</h2>
        <button
          className="primary"
          disabled={disabled || busy}
          onClick={() => void submit()}
        >
          {busy ? "正在提交…" : "提交当前参数"}
        </button>
      </div>
      <p className="hint">
        提交当前编辑参数的独立副本。任务与结果持久保存，页面关闭后继续处理。当前使用本地合成，未调用模型。
      </p>
      {error && (
        <p role="alert" className="jobs-error">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="hint">
          {notice}
        </p>
      )}
      {jobs.length === 0 ? (
        <p className="hint">还没有处理任务。调整好画面后，提交一次本地处理。</p>
      ) : (
        <ul className="job-list">
          {jobs.map((job) => (
            <li key={job.id}>
              <div>
                <strong>{states[job.state]}</strong>
                <small>
                  {new Date(job.created_at).toLocaleString("zh-CN")} ·{" "}
                  {job.id.slice(0, 8)} · 已执行 {job.execution_count} 次
                </small>
                {job.error_code && (
                  <p className="jobs-error">
                    {problems[job.error_code] || job.error_code}
                  </p>
                )}
              </div>
              {job.state === "SUCCEEDED" && (
                <button onClick={() => setSelected(job.id)}>
                  查看结果 / QC
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {more && limit < 100 && (
        <button onClick={() => setLimit((v) => Math.min(100, v + 20))}>
          加载更多任务
        </button>
      )}
      {limit === 100 && more && (
        <p className="hint">
          已显示最近 100 个任务，更早记录可通过任务 API 分页读取。
        </p>
      )}
      {selected && (
        <ReviewDialog
          key={selected}
          jobId={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </section>
  );
}

export function ReviewDialog({
  jobId,
  onClose,
}: {
  jobId: string;
  onClose: () => void;
}) {
  const account = useAccount();
  const canReview = account?.roles.some((role) =>
    ["OPERATOR", "REVIEWER"].includes(role),
  );
  const dialog = useRef<HTMLDialogElement>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [labels, setLabels] = useState<Labels>(emptyLabels);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const [evidence, setEvidence] = useState<string | null>(null);
  useEffect(() => {
    dialog.current?.showModal();
    const controller = new AbortController();
    void api<Detail>(`/studio/jobs/${jobId}`, { signal: controller.signal })
      .then((data) => setDetail(data))
      .catch((e) => {
        if (!controller.signal.aborted) setError(describe(e));
      });
    return () => controller.abort();
  }, [jobId]);
  useEffect(() => {
    if (!dirty) return;
    const guard = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [dirty]);
  useEffect(
    () => () => {
      if (evidence) URL.revokeObjectURL(evidence);
    },
    [evidence],
  );
  const complete = dimensions.every(
    (key) =>
      labels[key].decision &&
      (labels[key].decision !== "FAIL" || labels[key].reason.trim()),
  );
  function close() {
    if (busy) return;
    if (dirty) setConfirmClose(true);
    else onClose();
  }
  async function save() {
    if (!detail) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const review = await api<Review>(
        `/studio/jobs/${jobId}/reviews`,
        json({
          expected_version: detail.reviews.length,
          output_sha256: detail.output_sha256,
          dimensions: labels,
        }),
      );
      setDetail({ ...detail, reviews: [...detail.reviews, review] });
      setDirty(false);
      setNotice(
        `已保存审核 v${review.version}：${review.decision === "PASS" ? "通过" : "未通过"}`,
      );
    } catch (e) {
      setError(describe(e));
    } finally {
      setBusy(false);
    }
  }
  async function exportEvidence() {
    setError("");
    try {
      const data = await api<Detail>(`/studio/jobs/${jobId}`);
      setEvidence(
        URL.createObjectURL(
          new Blob([JSON.stringify(data, null, 2)], {
            type: "application/json",
          }),
        ),
      );
    } catch (e) {
      setError(describe(e));
    }
  }
  return (
    <dialog
      ref={dialog}
      className="qc-dialog"
      aria-labelledby="qc-title"
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
    >
      <div className="section-title">
        <div>
          <h2 id="qc-title">处理结果与五维审核</h2>
          <p className="hint">开发验证 · 不计入正式验收</p>
        </div>
        <button disabled={busy} onClick={close}>
          关闭
        </button>
      </div>
      {confirmClose && (
        <div className="qc-close-confirm" role="alert">
          <p>当前审核尚未保存。关闭后会丢弃这些填写内容。</p>
          <button onClick={() => setConfirmClose(false)}>继续填写</button>
          <button onClick={onClose}>丢弃并关闭</button>
        </div>
      )}
      {error && (
        <p role="alert" className="jobs-error">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {!detail ? (
        <p>正在读取已保存结果…</p>
      ) : (
        <>
          <div className="qc-images">
            <figure>
              <img
                src={`/api/v1/development/cases/${detail.case_id}/image`}
                alt="原始素材，用于核对人物与场景"
              />
              <figcaption>原始素材</figcaption>
            </figure>
            <figure>
              <img
                src={outputURL(jobId, "png")}
                alt="本次任务保存的本地合成结果"
                onLoad={() => {
                  setImageLoaded(true);
                  setImageError(false);
                }}
                onError={() => {
                  setImageLoaded(false);
                  setImageError(true);
                }}
              />
              <figcaption>本地合成结果</figcaption>
            </figure>
          </div>
          {imageError && (
            <p role="alert" className="jobs-error">
              结果图片加载失败，请关闭后重试。
            </p>
          )}
          <div className="qc-downloads">
            <a href={outputURL(jobId, "bundle")}>下载结果包</a>
            <a href={`/api/v1/development/studio/jobs/${jobId}/evidence`}>
              下载可校验证据包
            </a>
            <button onClick={() => void exportEvidence()}>
              准备导出任务与审核记录
            </button>
            {evidence && (
              <a href={evidence} download={`${jobId}-review-record.json`}>
                下载审核记录 JSON
              </a>
            )}
          </div>
          <p className="hint">
            结果校验值 {detail.output_sha256?.slice(0, 16)}… ·
            这是人工审核记录，尚未接入模型修复。
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void save();
            }}
          >
            <fieldset disabled={busy || !canReview}>
              <legend>逐项判定；未通过时填写原因</legend>
              {dimensions.map((key) => (
                <div className="qc-dimension" key={key}>
                  <label htmlFor={`qc-${key}`}>
                    <strong>{titles[key]}</strong>
                    <small>{criteria[key]}</small>
                  </label>
                  <select
                    id={`qc-${key}`}
                    value={labels[key].decision}
                    onChange={(e) => {
                      setLabels({
                        ...labels,
                        [key]: {
                          ...labels[key],
                          decision: e.target.value as Label["decision"],
                        },
                      });
                      setDirty(true);
                    }}
                    required
                  >
                    <option value="">请选择</option>
                    <option value="PASS">通过</option>
                    <option value="FAIL">未通过</option>
                  </select>
                  <input
                    aria-label={`${titles[key]}审核原因`}
                    placeholder={
                      labels[key].decision === "FAIL"
                        ? "未通过原因（必填）"
                        : "备注（选填）"
                    }
                    maxLength={2000}
                    required={labels[key].decision === "FAIL"}
                    value={labels[key].reason}
                    onChange={(e) => {
                      setLabels({
                        ...labels,
                        [key]: { ...labels[key], reason: e.target.value },
                      });
                      setDirty(true);
                    }}
                  />
                </div>
              ))}
            </fieldset>
            <button
              className="primary"
              disabled={
                !canReview || !complete || !dirty || busy || !imageLoaded
              }
            >
              {busy ? "正在保存…" : "保存新的审核版本"}
            </button>
          </form>
          <section className="qc-history">
            <h3>审核记录 · {detail.reviews.length} 个版本</h3>
            {detail.reviews.length === 0 && (
              <p className="hint">
                尚未审核。五项均明确通过，服务端才会记录为通过。
              </p>
            )}
            {[...detail.reviews].reverse().map((review) => (
              <details key={review.version}>
                <summary>
                  v{review.version} ·{" "}
                  {review.decision === "PASS" ? "通过" : "未通过"} ·{" "}
                  {new Date(review.occurred_at).toLocaleString("zh-CN")}
                </summary>
                {dimensions.map((key) => (
                  <p key={key}>
                    {titles[key]}：
                    {review.dimensions[key].decision === "PASS"
                      ? "通过"
                      : "未通过"}
                    {review.dimensions[key].reason &&
                      ` — ${review.dimensions[key].reason}`}
                  </p>
                ))}
                <small>记录校验值 {review.content_sha256.slice(0, 16)}…</small>
              </details>
            ))}
          </section>
        </>
      )}
    </dialog>
  );
}
