import { useEffect, useRef, useState, type ReactNode } from "react";
import Studio from "./Studio";
import { AccountControls, useAccount } from "./AccountGate";
import { ReviewDialog } from "./JobsPanel";
import { labels, type Catalog, type Template } from "./types";
import {
  caseRoute,
  dimensionNames,
  failureNames,
  jobStates,
  pages,
  readRoute,
  useRemote,
  type Job,
  type Page,
  type Summary,
} from "./console-data";
import "./console.css";

type Remote<T> = ReturnType<typeof useRemote<T>>;
const technicalPages: Page[] = [
  "preflight",
  "algorithms",
  "workflows",
  "test-runs",
  "analytics",
  "trace",
];
const descriptions: Partial<Record<Page, string>> = {
  dashboard: "素材就绪、案例生产和质量状态的统一入口。",
  cases: "浏览开发案例，检查素材状态并进入生成工作台。",
  assets: "人物底图、商品视角与素材来源的统一管理。",
  review: "查看已保存的本地处理结果，完成五维人工审核。",
  algorithms: "查看已保存的定位模板及其版本，在工作台中应用。",
  analytics: "基于实际本地任务与最新人工审核的质量统计。",
  trace: "查看本地任务记录与结果，导出可校验的审核证据。",
};

function Icon({ name }: { name: Page | "arrow" }) {
  const paths: Record<string, ReactNode> = {
    dashboard: (
      <>
        <rect x="3" y="3" width="18" height="18" rx="3" />
        <path d="M9 3v18M9 10h12" />
      </>
    ),
    cases: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </>
    ),
    studio: (
      <>
        <path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z" />
        <path d="m20 2 .5 1.5L22 4l-1.5.5L20 6l-.5-1.5L18 4l1.5-.5Z" />
      </>
    ),
    review: (
      <>
        <path d="m5 12 4 4L19 6" />
        <path d="M20 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9" />
      </>
    ),
    assets: (
      <>
        <rect x="3" y="3" width="18" height="18" rx="3" />
        <circle cx="8" cy="8" r="1.5" />
        <path d="m3 17 5-5 4 4 4-7 5 6" />
      </>
    ),
    preflight: (
      <>
        <circle cx="12" cy="12" r="9" />
        <circle cx="12" cy="12" r="4" />
      </>
    ),
    algorithms: (
      <>
        <path d="M8 3v18M16 3v18M3 8h18M3 16h18" />
      </>
    ),
    workflows: (
      <>
        <path d="m12 2 9 5v10l-9 5-9-5V7l9-5Z" />
        <path d="m3 7 9 5 9-5M12 12v10" />
      </>
    ),
    "test-runs": (
      <>
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <path d="M7 8h10M7 12h10M7 16h6" />
      </>
    ),
    analytics: (
      <>
        <path d="M3 3v18h18M6 15l4-5 4 3 6-8" />
      </>
    ),
    trace: (
      <>
        <circle cx="5" cy="5" r="2" />
        <circle cx="19" cy="19" r="2" />
        <path d="M5 7v7a5 5 0 0 0 5 5h7M11 5h8v8" />
      </>
    ),
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
  };
  return (
    <svg
      viewBox="0 0 24 24"
      width="17"
      height="17"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}
function Pill({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`console-pill ${tone}`}>{children}</span>;
}
function Empty({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="console-empty">
      <span className="empty-mark" aria-hidden="true">
        ◇
      </span>
      <strong>{title}</strong>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}
function RemoteError({
  remote,
}: {
  remote: { error: string; refresh: () => void };
}) {
  return remote.error ? (
    <div role="alert" className="console-error">
      <span>数据读取失败：{remote.error}。 已显示的数据可能不是最新状态。</span>
      <button onClick={remote.refresh}>重新读取</button>
    </div>
  ) : null;
}
function PageHead({ page, children }: { page: Page; children?: ReactNode }) {
  return (
    <div className="console-page-head">
      <div>
        <h1>{pages[page]}</h1>
        <p>{descriptions[page] || "技术配置与生产流程的管理入口。"}</p>
      </div>
      {children}
    </div>
  );
}
function Panel({
  title,
  action,
  children,
  className = "",
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`console-panel ${className}`}>
      <div className="panel-heading">
        <h2>{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}
function Quality({ summary }: { summary?: Summary }) {
  return (
    <>
      <div className="quality-bars">
        {Object.entries(dimensionNames).map(([key, name]) => {
          const metric = summary?.quality[key];
          return (
            <div className="quality-row" key={key}>
              <span>{name}</span>
              <div className="metric-track">
                <i
                  className={
                    metric?.rate != null && metric.rate < 80 ? "amber" : "green"
                  }
                  style={{ width: `${metric?.rate ?? 0}%` }}
                />
              </div>
              <b>{metric?.rate == null ? "—" : `${metric.rate}%`}</b>
            </div>
          );
        })}
      </div>
      <p className="panel-note">
        {summary
          ? summary.quality.product.reviewed
            ? `${summary.quality.product.reviewed} 个已审核结果 · 每个结果取最新版本`
            : "暂无审核数据 · 完成五维评审后显示"
          : "等待读取审核数据"}
      </p>
    </>
  );
}
function Flow() {
  return (
    <>
      <div className="production-flow">
        {[
          ["输入检查", "Case Base / SKU", "available"],
          ["自动定位", "Anchor / Snap", "available"],
          ["Contact Edit", "模型未接入", "deferred"],
          ["QC", "本地五维评审", "available"],
          ["完成", "本地结果 / 证据", "available"],
        ].map(([title, sub, tone], i) => (
          <div className={`flow-step ${tone}`} key={title}>
            <span className="flow-dot">{i + 1}</span>
            <b>{title}</b>
            <small>{sub}</small>
          </div>
        ))}
      </div>
      <div className="console-callout">
        <b>当前可用：</b>自动定位、安全微调、手工遮挡、本地合成与
        QC。模型接触修补尚未接入。
      </div>
      <p className="panel-note">流程能力说明；不代表某个案例的完成进度。</p>
    </>
  );
}
function Dashboard({
  catalog,
  summary,
}: {
  catalog: Remote<Catalog>;
  summary: Remote<Summary>;
}) {
  const data = summary.data;
  const cases = catalog.data?.cases;
  const metrics = [
    {
      label: "待处理任务",
      value: data ? data.counts.QUEUED + data.counts.RUNNING : "—",
      sub: data
        ? `${data.counts.QUEUED} 个排队 · ${data.counts.RUNNING} 个处理中`
        : "等待读取任务",
      tone: "",
    },
    {
      label: "Technical Pass",
      value: "—",
      sub: "暂无数据 · 正式技术评估未接入",
      tone: "purple",
    },
    {
      label: "Attempt 1 Pass",
      value: "—",
      sub: "暂无数据 · 模型生成未接入",
      tone: "",
    },
    {
      label: "平均人工处理",
      value: "—",
      sub: "暂无数据 · 尚未记录人工用时",
      tone: "green",
    },
  ];
  return (
    <div className="console-content">
      <PageHead page="dashboard">
        <Pill
          tone={
            summary.error || catalog.error
              ? "amber"
              : data && cases
                ? "green"
                : "neutral"
          }
        >
          ●{" "}
          {summary.error || catalog.error
            ? "数据连接异常"
            : data && cases
              ? "本地服务可用"
              : "正在连接"}
        </Pill>
      </PageHead>
      <RemoteError remote={catalog} />
      <RemoteError remote={summary} />
      <div className="overview-metrics">
        {metrics.map((m) => (
          <section className="console-panel metric-card" key={m.label}>
            <span>{m.label}</span>
            <strong className={m.tone}>{m.value}</strong>
            <small>{m.sub}</small>
          </section>
        ))}
      </div>
      <div className="overview-middle">
        <Panel
          title="当前队列"
          action={
            <a href="#/trace" className="console-text-link">
              查看全部 →
            </a>
          }
        >
          <div className="console-table-wrap">
            <table className="console-table">
              <thead>
                <tr>
                  <th>Case</th>
                  <th>交互</th>
                  <th>姿态</th>
                  <th>阶段</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {data?.queue.map((job) => {
                  const item = cases?.find((c) => c.case_id === job.case_id);
                  return (
                    <tr key={job.id}>
                      <td>
                        <a href={caseRoute(job.case_id)}>{job.case_id}</a>
                        <small>{job.id.slice(0, 8)}</small>
                      </td>
                      <td>{item ? labels[item.interaction] : "—"}</td>
                      <td>{item?.pose_zone || "—"}</td>
                      <td>本地合成</td>
                      <td>
                        <Pill tone="purple">{jobStates[job.state]}</Pill>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {!data?.queue.length && (
            <Empty
              title={
                summary.loading
                  ? "正在读取队列…"
                  : summary.error
                    ? "队列暂不可用"
                    : "当前没有待处理任务"
              }
              action={
                !summary.loading &&
                !summary.error && (
                  <a className="console-text-link" href="#/cases">
                    选择案例，开始制作 →
                  </a>
                )
              }
            >
              提交处理任务后，可在这里查看进度。
            </Empty>
          )}
        </Panel>
        <Panel title="单 Case 生产链">
          <Flow />
        </Panel>
      </div>
      <div className="overview-bottom">
        <Panel title="素材就绪">
          {[
            [
              "Case Base",
              cases ? `${cases.length} 张已入库` : "—",
              !!cases?.length,
            ],
            [
              "Product Views",
              catalog.data
                ? `${catalog.data.product_views.length} 个可用视角`
                : "—",
              !!catalog.data?.product_views.length,
            ],
            ["Canonical Base", "暂无独立目录", false],
          ].map(([name, value, ready]) => (
            <div className="asset-readiness" key={String(name)}>
              <div>
                <span>{name}</span>
                <b>{value}</b>
              </div>
              <div className="metric-track">
                <i style={{ width: ready ? "100%" : "0%" }} />
              </div>
            </div>
          ))}
          <p className="panel-note">
            Development 素材目录 · 不代表正式生产准入
          </p>
        </Panel>
        <Panel title="质量分布">
          <Quality summary={data} />
        </Panel>
        <Panel title="最近异常">
          {data?.recent_failures.length ? (
            <ol className="exception-list">
              {data.recent_failures.map((job) => (
                <li key={job.id}>
                  <a href={caseRoute(job.case_id)}>
                    {failureNames[job.error_code || ""] ||
                      job.error_code ||
                      "任务失败"}
                  </a>
                  <small>
                    {job.case_id} ·{" "}
                    {new Date(job.created_at).toLocaleString("zh-CN")}
                  </small>
                </li>
              ))}
            </ol>
          ) : (
            <Empty
              title={
                summary.loading
                  ? "正在读取…"
                  : summary.error
                    ? "异常记录暂不可用"
                    : "暂无处理异常"
              }
            >
              后续失败任务将在此显示。
            </Empty>
          )}
        </Panel>
      </div>
    </div>
  );
}
function CaseFilters({
  query,
  setQuery,
  filter,
  setFilter,
}: {
  query: string;
  setQuery: (v: string) => void;
  filter: string;
  setFilter: (v: string) => void;
}) {
  return (
    <div className="console-filters">
      <input
        aria-label="搜索案例编号"
        placeholder="搜索案例编号…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <select
        aria-label="筛选交互类型"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      >
        <option value="ALL">全部交互</option>
        {Object.entries(labels).map(([key, value]) => (
          <option value={key} key={key}>
            {value}
          </option>
        ))}
      </select>
    </div>
  );
}
function Cases({ catalog }: { catalog: Remote<Catalog> }) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("ALL");
  const items = catalog.data?.cases.filter(
    (c) =>
      c.case_id.toLowerCase().includes(query.trim().toLowerCase()) &&
      (filter === "ALL" || filter === c.interaction),
  );
  return (
    <div className="console-content">
      <PageHead page="cases">
        <Pill tone="purple">
          Development · {catalog.data?.cases.length ?? "—"} 个案例
        </Pill>
      </PageHead>
      <RemoteError remote={catalog} />
      <Panel
        title="案例列表"
        action={
          <span className="panel-note">{items?.length ?? "—"} 个匹配案例</span>
        }
      >
        <CaseFilters {...{ query, setQuery, filter, setFilter }} />
        <div className="console-table-wrap">
          <table className="console-table case-table">
            <thead>
              <tr>
                <th>Case / 素材</th>
                <th>交互类型</th>
                <th>姿态分区</th>
                <th>推荐商品视角</th>
                <th>定位状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {items?.map((c) => (
                <tr key={c.case_id}>
                  <td>
                    <div className="case-cell">
                      <img
                        loading="lazy"
                        src={`/api/v1/development/cases/${c.case_id}/image`}
                        alt=""
                      />
                      <div>
                        <b>{c.case_id}</b>
                        <small>
                          {c.width} × {c.height} · Development
                        </small>
                      </div>
                    </div>
                  </td>
                  <td>{labels[c.interaction]}</td>
                  <td>
                    <Pill tone={c.pose_zone === "GREEN" ? "green" : "amber"}>
                      {c.pose_zone === "GREEN"
                        ? "Green · 常规"
                        : "Yellow · 边界"}
                    </Pill>
                  </td>
                  <td>{c.suggestion.product_view_id}</td>
                  <td>
                    <Pill
                      tone={
                        c.suggestion.residual.within_gate ? "green" : "amber"
                      }
                    >
                      {c.suggestion.residual.within_gate
                        ? "可定位"
                        : "需要匹配视角"}
                    </Pill>
                  </td>
                  <td>
                    <a
                      className="console-text-link"
                      href={caseRoute(c.case_id)}
                    >
                      进入工作台 →
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!items?.length && (
          <Empty
            title={
              catalog.loading
                ? "正在读取案例…"
                : catalog.error
                  ? "案例目录暂不可用"
                  : "没有匹配的案例"
            }
          >
            尝试其他编号或交互类型。
          </Empty>
        )}
      </Panel>
    </div>
  );
}
function Assets({ catalog }: { catalog: Remote<Catalog> }) {
  const [tab, setTab] = useState("cases");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("ALL");
  const items = catalog.data?.cases.filter(
    (c) =>
      c.case_id.toLowerCase().includes(query.trim().toLowerCase()) &&
      (filter === "ALL" || filter === c.interaction),
  );
  return (
    <div className="console-content">
      <PageHead page="assets">
        <Pill tone="green">Development · 素材只读</Pill>
      </PageHead>
      <RemoteError remote={catalog} />
      <div className="console-callout asset-source">
        <b>当前素材库</b>
        <span>
          {catalog.data
            ? `${catalog.data.cases.length} 张人物底图 · ${catalog.data.product_views.length} 个商品视角`
            : "正在读取素材目录"}
        </span>
        <small>正式数据集与模型生成尚未开放。</small>
      </div>
      <div className="console-tabs" role="tablist" aria-label="素材类型">
        {[
          ["cases", "Case Base"],
          ["products", "Product Views"],
          ["canonical", "Canonical Base"],
        ].map(([id, label]) => (
          <button
            role="tab"
            aria-selected={tab === id}
            aria-controls={`assets-${id}`}
            id={`tab-${id}`}
            key={id}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>
      <section
        role="tabpanel"
        id={`assets-${tab}`}
        aria-labelledby={`tab-${tab}`}
      >
        {tab === "cases" && (
          <>
            <CaseFilters {...{ query, setQuery, filter, setFilter }} />
            <div className="console-asset-grid">
              {items?.map((c) => (
                <a
                  className="asset-tile"
                  href={caseRoute(c.case_id)}
                  key={c.case_id}
                >
                  <div className="asset-tile-image">
                    <img
                      loading="lazy"
                      src={`/api/v1/development/cases/${c.case_id}/image`}
                      alt={`${c.case_id} 人物底图`}
                    />
                    <Pill tone={c.pose_zone === "GREEN" ? "green" : "amber"}>
                      {c.pose_zone}
                    </Pill>
                  </div>
                  <div>
                    <b>{c.case_id}</b>
                    <small>
                      {labels[c.interaction]} · {c.width} × {c.height}
                    </small>
                  </div>
                </a>
              ))}
            </div>
            {!items?.length && (
              <Empty
                title={
                  catalog.loading
                    ? "正在读取素材…"
                    : catalog.error
                      ? "素材暂不可用"
                      : "没有匹配的素材"
                }
              />
            )}
          </>
        )}
        {tab === "products" && (
          <>
            <div className="console-asset-grid products">
              {catalog.data?.product_views.map((v) => (
                <div className="asset-tile" key={v.view_id}>
                  <div className="asset-tile-image">
                    <img
                      loading="lazy"
                      src={`/api/v1/development/product-views/${v.view_id}/image?product_revision=v2`}
                      alt={`${v.view_id} 商品视角`}
                    />
                  </div>
                  <div>
                    <b>{v.view_id}</b>
                    <small>
                      结构修正版 · Yaw {v.yaw}° / Pitch {v.pitch}°
                    </small>
                  </div>
                </div>
              ))}
            </div>
            {!catalog.data && (
              <Empty
                title={
                  catalog.loading ? "正在读取商品视角…" : "商品视角暂不可用"
                }
              />
            )}
          </>
        )}
        {tab === "canonical" && (
          <Panel title="人物参考">
            <Empty title="暂无独立人物参考目录">
              当前可用人物底图收录在 Case Base 中。
            </Empty>
          </Panel>
        )}
      </section>
      {catalog.data && (
        <details className="source-details">
          <summary>素材来源与校验</summary>
          <p>数据集 Manifest SHA256</p>
          <code>{catalog.data.provenance.dataset_manifest_sha256}</code>
        </details>
      )}
    </div>
  );
}
function JobCenter({
  page,
  onChange,
}: {
  page: "review" | "trace";
  onChange: () => void;
}) {
  const [state, setState] = useState(page === "review" ? "SUCCEEDED" : "ALL");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const remote = useRemote<{ jobs: Job[]; has_more: boolean }>(
    `/studio/jobs?limit=20&offset=${offset}${state === "ALL" ? "" : `&state=${state}`}`,
    10000,
  );
  return (
    <div className="console-content">
      <PageHead page={page}>
        <button onClick={remote.refresh}>刷新列表</button>
      </PageHead>
      <RemoteError remote={remote} />
      <Panel
        title={page === "review" ? "待审核与历史结果" : "任务记录"}
        action={<Pill>本地开发</Pill>}
      >
        {page === "trace" && (
          <div className="console-filters">
            <select
              aria-label="筛选任务状态"
              value={state}
              onChange={(e) => {
                setState(e.target.value);
                setOffset(0);
              }}
            >
              <option value="ALL">全部状态</option>
              {Object.entries(jobStates).map(([key, label]) => (
                <option value={key} key={key}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="console-table-wrap">
          <table className="console-table">
            <thead>
              <tr>
                <th>Case / 任务</th>
                <th>创建时间</th>
                <th>处理状态</th>
                <th>审核记录</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {remote.data?.jobs.map((job) => (
                <tr key={job.id}>
                  <td>
                    <b>{job.case_id}</b>
                    <small>{job.id.slice(0, 8)}</small>
                  </td>
                  <td>{new Date(job.created_at).toLocaleString("zh-CN")}</td>
                  <td>
                    <Pill
                      tone={
                        job.state === "FAILED"
                          ? "amber"
                          : job.state === "SUCCEEDED"
                            ? "green"
                            : "purple"
                      }
                    >
                      {jobStates[job.state]}
                    </Pill>
                    {job.error_code && (
                      <small>
                        {failureNames[job.error_code] || job.error_code}
                      </small>
                    )}
                  </td>
                  <td>
                    {job.state === "SUCCEEDED"
                      ? job.review_version
                        ? `已审核 · v${job.review_version}`
                        : "待审核"
                      : "—"}
                  </td>
                  <td>
                    {job.state === "SUCCEEDED" ? (
                      <button
                        className="console-link-button"
                        onClick={() => setSelected(job.id)}
                      >
                        查看结果 / QC →
                      </button>
                    ) : (
                      <a
                        className="console-text-link"
                        href={caseRoute(job.case_id)}
                      >
                        进入工作台 →
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!remote.data?.jobs.length && (
          <Empty
            title={
              remote.loading
                ? "正在读取任务…"
                : remote.error
                  ? "任务列表暂不可用"
                  : page === "review"
                    ? "暂无可审核的结果"
                    : "暂无处理任务"
            }
            action={
              !remote.loading &&
              !remote.error && (
                <a className="console-text-link" href="#/cases">
                  选择案例，进入工作台 →
                </a>
              )
            }
          >
            在工作台提交本地处理任务，完成后即可查看结果。
          </Empty>
        )}
        <div className="console-pagination">
          <span>第 {offset / 20 + 1} 页</span>
          <button
            disabled={offset === 0 || remote.loading}
            onClick={() => setOffset((v) => Math.max(0, v - 20))}
          >
            上一页
          </button>
          <button
            disabled={!remote.data?.has_more || remote.loading}
            onClick={() => setOffset((v) => v + 20)}
          >
            下一页
          </button>
        </div>
      </Panel>
      {selected && (
        <ReviewDialog
          jobId={selected}
          onClose={() => {
            setSelected(null);
            remote.refresh();
            onChange();
          }}
        />
      )}
    </div>
  );
}
function Templates() {
  const remote = useRemote<{ templates: Template[] }>("/studio/templates");
  return (
    <div className="console-content">
      <PageHead page="algorithms" />
      <RemoteError remote={remote} />
      <Panel
        title="定位模板"
        action={
          <a className="console-text-link" href="#/studio">
            前往工作台保存模板 →
          </a>
        }
      >
        <div className="console-table-wrap">
          <table className="console-table">
            <thead>
              <tr>
                <th>模板名称</th>
                <th>版本</th>
                <th>交互类型</th>
                <th>商品视角</th>
                <th>使用</th>
              </tr>
            </thead>
            <tbody>
              {remote.data?.templates.map((t) => (
                <tr key={t.id}>
                  <td>
                    <b>{t.name}</b>
                  </td>
                  <td>v{t.version}</td>
                  <td>{labels[t.interaction]}</td>
                  <td>{t.parameters.product_view_id}</td>
                  <td>
                    <a
                      href={caseRoute(t.parameters.case_id)}
                      className="console-text-link"
                    >
                      在工作台选择模板 →
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!remote.data?.templates.length && (
          <Empty
            title={
              remote.loading
                ? "正在读取模板…"
                : remote.error
                  ? "模板暂不可用"
                  : "还没有保存的模板"
            }
          >
            在工作台调整定位后，命名保存为模板即可在此查看。
          </Empty>
        )}
      </Panel>
    </div>
  );
}
function Technical({
  page,
  summary,
}: {
  page: Page;
  summary: Remote<Summary>;
}) {
  if (page === "algorithms") return <Templates />;
  if (page === "analytics")
    return (
      <div className="console-content">
        <PageHead page={page} />
        <RemoteError remote={summary} />
        <div className="overview-middle">
          <Panel title="本地五维审核通过比例">
            <Quality summary={summary.data} />
          </Panel>
          <Panel title="本地任务统计">
            <div className="technical-stat-list">
              {Object.entries(jobStates).map(([key, title]) => (
                <div key={key}>
                  <span>{title}</span>
                  <b>{summary.data?.counts[key as Job["state"]] ?? "—"}</b>
                </div>
              ))}
            </div>
            <p className="panel-note">
              按任务统计；不等同于 Business Attempt 或正式质量通过率。
            </p>
          </Panel>
        </div>
      </div>
    );
  const copy: Partial<Record<Page, [string, string]>> = {
    preflight: [
      "正式 Preflight 尚未接入",
      "当前可在案例中心检查定位视角匹配情况。正式 Gate 判定将在生产流程接入后开放。",
    ],
    workflows: [
      "模型与工作流尚未接入",
      "当前使用本地定位与合成。模型接触修补、材质重打光和生产路由仍未启用。",
    ],
    "test-runs": [
      "正式批量测试尚未接入",
      "当前支持在生成工作台逐个提交本地处理任务，并在任务记录中查看进度和结果。",
    ],
  };
  const [title, description] = copy[page] || [
    "此能力尚未接入",
    "当前可用功能可从左侧导航进入。",
  ];
  return (
    <div className="console-content">
      <PageHead page={page} />
      <Panel title={pages[page]} action={<Pill tone="amber">未接入</Pill>}>
        <Empty
          title={title}
          action={
            <a
              href={page === "test-runs" ? "#/trace" : "#/cases"}
              className="console-button"
            >
              {page === "test-runs" ? "查看本地任务" : "查看开发案例"}
              <Icon name="arrow" />
            </a>
          }
        >
          {description}
        </Empty>
      </Panel>
    </div>
  );
}
function DevelopmentNote({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  return (
    <dialog
      className="console-note-dialog"
      ref={dialog}
      aria-labelledby="development-title"
      onCancel={onClose}
    >
      <h2 id="development-title">开发说明</h2>
      <p>
        当前为本地开发版本，已支持素材浏览、自动与手动定位、手工遮挡、草稿和模板、本地处理任务及五维人工审核。
      </p>
      <p>
        模型接触修补、生产 Attempt、正式 Preflight
        与批量测试尚未接入。概览中的正式通过率和人工处理用时在没有对应数据时显示“—”。
      </p>
      <p>
        质量分布只统计本地任务，每个结果取最新人工审核版本，不作为正式验收结论。
      </p>
      <button className="primary" onClick={onClose} autoFocus>
        知道了
      </button>
    </dialog>
  );
}
export default function App() {
  const account = useAccount();
  const [route, setRoute] = useState(() => readRoute(location.hash));
  const [openCase, setOpenCase] = useState<{
    id: string;
    sequence: number;
  } | null>(() => (route.caseId ? { id: route.caseId, sequence: 0 } : null));
  const [studioVisited, setStudioVisited] = useState(route.page === "studio");
  const [technical, setTechnical] = useState(
    technicalPages.includes(route.page as Page),
  );
  const [note, setNote] = useState(false);
  const catalog = useRemote<Catalog>("/catalog");
  const summary = useRemote<Summary>("/studio/jobs/summary", 15000);
  useEffect(() => {
    function changed() {
      const next = readRoute(location.hash);
      setRoute(next);
      if (next.page === "studio") setStudioVisited(true);
      if (next.caseId)
        setOpenCase((v) => ({
          id: next.caseId!,
          sequence: (v?.sequence ?? 0) + 1,
        }));
      if (technicalPages.includes(next.page as Page)) setTechnical(true);
    }
    window.addEventListener("hashchange", changed);
    return () => window.removeEventListener("hashchange", changed);
  }, []);
  const title = route.page === "missing" ? "页面不存在" : pages[route.page];
  useEffect(() => {
    document.title = `${title} · Interaction Studio`;
  }, [title]);
  const nav = (page: Page, count?: number) => (
    <a
      href={`#/${page}`}
      className={`console-nav-item ${route.page === page ? "active" : ""}`}
      aria-current={route.page === page ? "page" : undefined}
      key={page}
    >
      <Icon name={page} />
      <span>{pages[page]}</span>
      {count !== undefined && <em>{count}</em>}
    </a>
  );
  return (
    <div className="console-shell">
      <a
        className="console-skip"
        href="#console-main"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("console-main")?.focus();
        }}
      >
        跳转到主要内容
      </a>
      <aside className="console-sidebar" aria-label="应用导航">
        <a className="console-brand" href="#/dashboard">
          <span className="console-logo">IS</span>
          <span>
            <strong>Interaction Studio</strong>
            <small>人物-奶嘴交互一致性</small>
          </span>
        </a>
        <div className="console-role-switch" aria-label="导航视图">
          <button
            aria-pressed={!technical}
            onClick={() => {
              setTechnical(false);
              if (technicalPages.includes(route.page as Page))
                location.hash = "/dashboard";
            }}
          >
            内容运营
          </button>
          <button aria-pressed={technical} onClick={() => setTechnical(true)}>
            技术管理
          </button>
        </div>
        <nav className="console-nav" aria-label="主导航">
          <span className="console-nav-title">生产</span>
          {nav("dashboard")}
          {nav("cases", catalog.data?.cases.length)}
          {nav("studio")}
          {nav("review", summary.data?.pending_review)}
          <span className="console-nav-title">素材</span>
          {nav("assets")}
          <span className="console-nav-title">技术管理</span>
          {technical && technicalPages.map((p) => nav(p))}
        </nav>
        <div className="console-sidebar-foot">
          <span className="local-indicator" />
          <div>
            本地工作空间<small>Development / V1</small>
          </div>
        </div>
      </aside>
      <div className="console-body">
        <header className="console-topbar">
          <div className="console-location">
            <small>Interaction Studio / {title}</small>
            <strong>{title}</strong>
          </div>
          <div className="console-top-actions">
            <Pill tone="purple">{technical ? "技术管理" : "内容运营"}</Pill>
            <button className="console-secondary" onClick={() => setNote(true)}>
              开发说明
            </button>
            <a className="console-button primary" href="#/cases">
              选择案例
            </a>
            <AccountControls />
          </div>
        </header>
        <main id="console-main" tabIndex={-1} className="console-main">
          {route.page === "dashboard" && (
            <Dashboard catalog={catalog} summary={summary} />
          )}
          {route.page === "cases" && <Cases catalog={catalog} />}
          {route.page === "assets" && <Assets catalog={catalog} />}
          {(route.page === "review" || route.page === "trace") && (
            <JobCenter
              key={route.page}
              page={route.page}
              onChange={summary.refresh}
            />
          )}
          {technicalPages.includes(route.page as Page) &&
            route.page !== "trace" && (
              <Technical page={route.page as Page} summary={summary} />
            )}
          {studioVisited && (
            <div hidden={route.page !== "studio"} className="console-studio">
              <div className="studio-context">
                <span>
                  生成工作台 <span className="context-separator">/</span>{" "}
                  本地编辑
                </span>
                <Pill tone="amber">模型未接入</Pill>
                {!account?.roles.includes("OPERATOR") && <Pill>只读访问</Pill>}
              </div>
              <Studio
                openCase={openCase}
                onCaseChange={(id) => {
                  if (readRoute(location.hash).page !== "studio") return;
                  history.replaceState(null, "", caseRoute(id));
                  setRoute({ page: "studio", caseId: id });
                }}
              />
            </div>
          )}
          {route.page === "missing" && (
            <div className="console-content">
              <Empty
                title="没有找到这个页面"
                action={
                  <a href="#/dashboard" className="console-button primary">
                    返回生产概览
                  </a>
                }
              />
            </div>
          )}
        </main>
      </div>
      {note && <DevelopmentNote onClose={() => setNote(false)} />}
    </div>
  );
}
