import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from "react";
import { api, errorText, json } from "./api";
import { useAccount } from "./AccountGate";
import { JobsPanel } from "./JobsPanel";
import {
  applyTemplate,
  change,
  equal,
  point,
  redo,
  undo,
  validPolygon,
  type History,
} from "./editor";
import {
  initial,
  labels,
  type Catalog,
  type DraftResponse,
  type Event,
  type Request,
  type Template,
} from "./types";

const messages: Record<string, string> = {
  PRODUCT_RESIDUAL_EXCEEDED: "当前商品视图与人物或手部角度不匹配，请更换视图。",
  PLACEMENT_CLIPS_PRODUCT: "商品超出画面，请向画面内移动或缩小。",
  VISIBLE_PRODUCT_CORE_EMPTY: "遮挡过多或商品过小，没有可保留的商品核心。",
  DRAFT_VERSION_CONFLICT:
    "另一个页面已保存新版本。请先导出当前参数，再重新读取草稿。",
  STUDIO_VERSION_CONFLICT: "数据已有新版本，请重新读取后再保存。",
  STUDIO_STORAGE_UNAVAILABLE: "暂时无法连接草稿存储，当前调整仍保留在页面中。",
  STUDIO_HISTORY_INTEGRITY_FAILED: "保存记录校验失败，已停止读取。",
  DRAFT_SOURCE_CHANGED: "草稿引用的素材已变化，不能直接继续使用。",
};
const friendly = (e: unknown) => messages[errorText(e)] || errorText(e);
const frame = (request: Request): History => ({
  past: [],
  present: request,
  future: [],
});
function download(data: Blob, name: string) {
  const url = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function Studio({
  openCase,
  onCaseChange,
}: {
  onCaseChange: (id: string) => void;
  openCase: { id: string; sequence: number } | null;
}) {
  const consumedOpen = useRef<number | null>(null);
  const account = useAccount();
  const [catalog, setCatalog] = useState<Catalog>();
  const [editor, setEditor] = useState<History>();
  const [filter, setFilter] = useState("ALL");
  const [query, setQuery] = useState("");
  const [saved, setSaved] = useState<Request>();
  const [version, setVersion] = useState<number>();
  const [events, setEvents] = useState<Event[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templateName, setTemplateName] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState("");
  const [previewKind, setPreviewKind] = useState("编辑");
  const [mode, setMode] = useState<"move" | "occlusion">("move");
  const [polygon, setPolygon] = useState<[number, number][]>([]);
  const [pendingCase, setPendingCase] = useState("");
  const [action, setAction] = useState("SAVE");
  const loadSequence = useRef(0);
  const requestSequence = useRef(0);
  const draftDialog = useRef<HTMLDialogElement>(null);
  const board = useRef<HTMLDivElement>(null);
  const drag = useRef<{ start: [number, number]; original: Request } | null>(
    null,
  );
  const request = editor?.present;
  const current = request
    ? catalog?.cases.find((c) => c.case_id === request.case_id)
    : undefined;
  const dirty = !!request && !equal(request, saved);
  const active = request && current;
  const locked = !account?.roles.includes("OPERATOR") || loading || !!busy;
  const currentRef = useRef(request);
  currentRef.current = request;
  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;
  const [imageError, setImageError] = useState("");

  function clearPreview() {
    setPreview("");
    setPreviewKind("编辑");
    requestSequence.current++;
  }
  function update(next: Request, reason = "SAVE") {
    setEditor((h) => (h ? change(h, next) : frame(next)));
    setAction(reason);
    setNotice("");
    clearPreview();
  }
  async function loadCase(caseId: string, catalogValue = catalog) {
    const item = catalogValue?.cases.find((c) => c.case_id === caseId);
    if (!item) {
      setError("没有找到这个开发案例，请从左侧选择可用案例。");
      return;
    }
    onCaseChange(caseId);
    const sequence = ++loadSequence.current;
    setLoading(true);
    setError("");
    setNotice("");
    clearPreview();
    setEditor(frame(initial(item)));
    setSaved(undefined);
    setVersion(undefined);
    setEvents([]);
    setPolygon([]);
    setImageError("");
    setAction("SAVE");
    try {
      const result = await api<DraftResponse>(`/studio/drafts/${caseId}`);
      if (sequence !== loadSequence.current) return;
      setEditor(frame(result.draft.parameters));
      setSaved(result.draft.parameters);
      setVersion(result.draft.resource_version);
      setEvents(result.events);
    } catch (e) {
      if (sequence === loadSequence.current) setError(friendly(e));
    } finally {
      if (sequence === loadSequence.current) setLoading(false);
    }
  }
  function selectCase(caseId: string) {
    if (loading || busy || caseId === request?.case_id) return;
    if (dirty) {
      setPendingCase(caseId);
      draftDialog.current?.showModal();
    } else void loadCase(caseId);
  }
  useEffect(() => {
    let alive = true;
    api<Catalog>("/catalog")
      .then((c) => {
        if (alive) {
          setCatalog(c);
          if (c.cases.length) {
            consumedOpen.current = openCase?.sequence ?? null;
            void loadCase(openCase?.id || c.cases[0].case_id, c);
          }
        }
      })
      .catch((e) => {
        if (alive) setError(friendly(e));
      });
    api<{ templates: Template[] }>("/studio/templates")
      .then((r) => {
        if (alive) setTemplates(r.templates);
      })
      .catch(() => {});
    return () => {
      alive = false;
      loadSequence.current++;
    };
  }, []);
  useEffect(() => {
    if (
      !catalog ||
      loading ||
      busy ||
      !openCase ||
      consumedOpen.current === openCase.sequence
    )
      return;
    consumedOpen.current = openCase.sequence;
    selectCase(openCase.id);
  }, [catalog, loading, busy, openCase]);
  useEffect(
    () => () => {
      if (preview) URL.revokeObjectURL(preview);
    },
    [preview],
  );
  useEffect(() => {
    const guard = (event: BeforeUnloadEvent) => {
      if (dirtyRef.current) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, []);
  useEffect(() => {
    const context = (
      document as Document & {
        modelContext?: {
          registerTool: (
            tool: unknown,
            options: unknown,
          ) => void | Promise<void>;
        };
      }
    ).modelContext;
    if (!context) return;
    const lifecycle = new AbortController();
    try {
      void Promise.resolve(
        context.registerTool(
          {
            name: "inspect_studio_state",
            description:
              "Read the currently selected Development case and its staged editing parameters. Does not save or render.",
            inputSchema: {
              type: "object",
              properties: {},
              additionalProperties: false,
            },
            annotations: { readOnlyHint: true },
            execute: (input: unknown) => {
              if (
                !input ||
                typeof input !== "object" ||
                Array.isArray(input) ||
                Object.keys(input).length
              )
                throw new Error("Expected an empty object");
              return {
                parameters: currentRef.current ?? null,
                unsaved: dirtyRef.current,
              };
            },
          },
          { signal: lifecycle.signal },
        ),
      ).catch(() => {});
    } catch {
      /* optional browser capability */
    }
    return () => lifecycle.abort();
  }, []);

  async function save() {
    if (!request || version === undefined) return false;
    setBusy("save");
    setError("");
    try {
      const result = await api<DraftResponse>(
        `/studio/drafts/${request.case_id}`,
        json({ expected_version: version, parameters: request, action }, "PUT"),
      );
      setSaved(result.draft.parameters);
      setVersion(result.draft.resource_version);
      setEvents(result.events);
      setNotice(`草稿已保存 · 版本 ${result.draft.resource_version}`);
      setAction("SAVE");
      return true;
    } catch (e) {
      setError(friendly(e));
      return false;
    } finally {
      setBusy("");
    }
  }
  async function saveTemplate() {
    if (!request || !templateName.trim()) return;
    setBusy("template");
    setError("");
    try {
      const result = await api<Template>(
        "/studio/templates",
        json({ name: templateName.trim(), parameters: request }),
      );
      setTemplates((t) => [result, ...t]);
      setTemplateId(result.id);
      setNotice(`已保存模板「${result.name}」版本 ${result.version}`);
      setTemplateName("");
    } catch (e) {
      setError(friendly(e));
    } finally {
      setBusy("");
    }
  }
  async function render(kind = "编辑") {
    if (!request) return;
    const sequence = ++requestSequence.current;
    setBusy("render");
    setError("");
    const format =
      kind === "下载" ? "bundle" : kind === "编辑" ? "png" : "mask";
    const url =
      format === "mask"
        ? `/previews/masks/${kind}`
        : `/previews?format=${format}`;
    try {
      const res = await fetch(`/api/v1/development${url}`, json(request));
      if (!res.ok) {
        const body = await res.json();
        throw new Error(body.detail?.code || "预览生成失败");
      }
      const blob = await res.blob();
      if (sequence !== requestSequence.current) return;
      if (kind === "下载") {
        download(blob, `${request.case_id}-preview.zip`);
        setNotice("预览包已下载");
      } else {
        setPreview(URL.createObjectURL(blob));
        setPreviewKind(kind);
        setNotice("本地预览已更新");
      }
    } catch (e) {
      if (sequence === requestSequence.current) setError(friendly(e));
    } finally {
      setBusy("");
    }
  }
  function pointerDown(e: PointerEvent<HTMLDivElement>) {
    if (!active || locked || preview) return;
    const bounds = e.currentTarget.getBoundingClientRect();
    const start = point(e.clientX, e.clientY, bounds);
    if (mode === "occlusion") {
      setPolygon((p) => (p.length < 128 ? [...p, start] : p));
      return;
    }
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { start, original: structuredClone(request) };
  }
  function pointerMove(e: PointerEvent<HTMLDivElement>) {
    if (!drag.current || !request || !board.current) return;
    const p = point(
      e.clientX,
      e.clientY,
      board.current.getBoundingClientRect(),
    );
    const original = drag.current.original;
    const next = {
      ...original,
      placement: {
        ...original.placement,
        center_x: Math.max(
          0,
          Math.min(
            1,
            original.placement.center_x + p[0] - drag.current.start[0],
          ),
        ),
        center_y: Math.max(
          0,
          Math.min(
            1,
            original.placement.center_y + p[1] - drag.current.start[1],
          ),
        ),
      },
    };
    setEditor((h) => (h ? { ...h, present: next } : frame(next)));
  }
  function pointerUp() {
    if (!drag.current) return;
    const original = drag.current.original;
    drag.current = null;
    setEditor((h) => (h ? change({ ...h, present: original }, h.present) : h));
    setAction("SAVE");
    setNotice("");
  }
  function keyboard(e: KeyboardEvent<HTMLDivElement>) {
    if (!request || locked || preview) return;
    const steps: Record<string, [number, number]> = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    };
    const step = steps[e.key];
    if (step) {
      e.preventDefault();
      const delta = e.shiftKey ? 0.01 : 0.001;
      update({
        ...request,
        placement: {
          ...request.placement,
          center_x: Math.max(
            0,
            Math.min(1, request.placement.center_x + step[0] * delta),
          ),
          center_y: Math.max(
            0,
            Math.min(1, request.placement.center_y + step[1] * delta),
          ),
        },
      });
    }
  }
  const visible = catalog?.cases.filter(
    (c) =>
      (filter === "ALL" || c.interaction === filter) &&
      c.case_id.toLowerCase().includes(query.toLowerCase()),
  );
  const availableTemplates = templates.filter(
    (t) =>
      t.interaction === current?.interaction &&
      t.manifest_sha256 === catalog?.provenance.dataset_manifest_sha256,
  );
  return (
    <div className="studio-editor">
      <main>
        <aside className="case-panel">
          <div className="section-title">
            <h2>案例素材</h2>
            <span>{visible?.length ?? "—"} / 30</span>
          </div>
          <label className="sr-only" htmlFor="search">
            搜索案例编号
          </label>
          <input
            id="search"
            placeholder="搜索案例编号"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <label className="sr-only" htmlFor="filter">
            交互类型
          </label>
          <select
            id="filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="ALL">全部交互</option>
            {Object.entries(labels).map(([key, value]) => (
              <option key={key} value={key}>
                {value}
              </option>
            ))}
          </select>
          <div className="case-list">
            {visible?.map((c) => (
              <button
                key={c.case_id}
                disabled={loading || !!busy}
                aria-pressed={current?.case_id === c.case_id}
                className={`case-item ${current?.case_id === c.case_id ? "selected" : ""}`}
                onClick={() => selectCase(c.case_id)}
              >
                <strong>{c.case_id}</strong>
                <span>
                  {labels[c.interaction]}{" "}
                  <i className={`pose-dot ${c.pose_zone.toLowerCase()}`} />
                  {c.pose_zone === "GREEN" ? "常规" : "边界"}
                </span>
                {!c.suggestion.residual.within_gate && (
                  <em>需要匹配商品视角</em>
                )}
              </button>
            ))}
            {visible?.length === 0 && <p className="hint">没有匹配的案例</p>}
          </div>
          <div className="side-note">
            30 张已封存开发素材
            <br />
            输入原图保持只读
          </div>
        </aside>
        <section className="workspace">
          <div className="workspace-heading">
            <div>
              <small>DEVELOPMENT / V1</small>
              <h1>{current ? labels[current.interaction] : "加载工作台"}</h1>
              <span className="studio-case-id">{current?.case_id}</span>
            </div>
            <div className="actions">
              <span className="save-status">
                {loading
                  ? "读取草稿中"
                  : dirty
                    ? "有未保存调整"
                    : version
                      ? `已保存 · v${version}`
                      : "尚未保存"}
              </span>
              <button
                onClick={() => void save()}
                disabled={!active || locked || version === undefined || !dirty}
              >
                {busy === "save" ? "正在保存…" : "保存草稿"}
              </button>
              <button
                className="primary"
                onClick={() => void render()}
                disabled={!active || locked || !!imageError}
              >
                {busy === "render" ? "正在生成…" : "生成本地预览"}
              </button>
            </div>
          </div>
          {error && (
            <div role="alert" className="error">
              {error}
              <button
                className="inline"
                disabled={locked}
                onClick={() => {
                  if (request) {
                    setPendingCase(request.case_id);
                    draftDialog.current?.showModal();
                  } else location.reload();
                }}
              >
                重新读取
              </button>
            </div>
          )}
          {notice && (
            <div className="notice" role="status">
              {notice}
            </div>
          )}
          {imageError && (
            <div className="error" role="alert">
              {imageError}
            </div>
          )}
          <div className="canvas-toolbar">
            <div className="actions">
              <button
                aria-pressed={mode === "move" && !preview}
                disabled={locked}
                onClick={() => {
                  setMode("move");
                  clearPreview();
                }}
              >
                移动
              </button>
              <button
                aria-pressed={mode === "occlusion" && !preview}
                disabled={locked}
                onClick={() => {
                  setMode("occlusion");
                  clearPreview();
                }}
              >
                绘制遮挡
              </button>
              <button
                aria-label="撤销"
                disabled={locked || !editor?.past.length}
                onClick={() => {
                  setEditor((h) => (h ? undo(h) : h));
                  clearPreview();
                }}
              >
                ↶ 撤销
              </button>
              <button
                aria-label="重做"
                disabled={locked || !editor?.future.length}
                onClick={() => {
                  setEditor((h) => (h ? redo(h) : h));
                  clearPreview();
                }}
              >
                ↷ 重做
              </button>
            </div>
            <span>
              {preview
                ? previewKind === "编辑"
                  ? "合成预览"
                  : previewKind
                : "定位编辑"}
            </span>
          </div>
          <div className="canvas-shell">
            {active ? (
              <div
                ref={board}
                tabIndex={0}
                role="group"
                aria-label="商品定位画布，可拖拽或使用方向键微调"
                className={`artboard ${mode === "occlusion" ? "drawing" : ""}`}
                style={{
                  aspectRatio: `${current.width}/${current.height}`,
                  width: `min(100%, max(250px, calc((100vh - 310px) * ${current.width / current.height})))`,
                }}
                onPointerDown={pointerDown}
                onPointerMove={pointerMove}
                onPointerUp={pointerUp}
                onPointerCancel={pointerUp}
                onKeyDown={keyboard}
              >
                <img
                  key={`${current.case_id}-${preview}`}
                  className="base"
                  src={
                    preview ||
                    `/api/v1/development/cases/${current.case_id}/image`
                  }
                  alt={preview ? "当前参数的本地预览" : "开发案例原图"}
                  draggable={false}
                  onError={() =>
                    setImageError("素材图片加载失败，请重新读取。")
                  }
                />
                {!preview && (
                  <>
                    <img
                      key={`${request.product_revision ?? "v1"}-${request.product_view_id}`}
                      className="product"
                      src={`/api/v1/development/product-views/${request.product_view_id}/image?product_revision=${request.product_revision ?? "v1"}`}
                      alt="奶嘴定位"
                      draggable={false}
                      onError={() =>
                        setImageError("商品图层加载失败，请重新读取。")
                      }
                      style={{
                        left: `${((request.placement.center_x * (current.width - 1)) / current.width) * 100}%`,
                        top: `${((request.placement.center_y * (current.height - 1)) / current.height) * 100}%`,
                        width: `${request.placement.width_ratio * 100}%`,
                        transform: `translate(-50%,-50%) rotate(${-request.placement.rotation_degrees}deg)`,
                      }}
                    />
                    <svg
                      className="occlusion-overlay"
                      viewBox="0 0 100 100"
                      preserveAspectRatio="none"
                      aria-hidden="true"
                    >
                      {request.occlusion_polygons.map((p, i) => (
                        <polygon
                          key={i}
                          points={p
                            .map((x) => `${x[0] * 100},${x[1] * 100}`)
                            .join(" ")}
                        />
                      ))}
                      {polygon.length > 0 && (
                        <polyline
                          points={polygon
                            .map((x) => `${x[0] * 100},${x[1] * 100}`)
                            .join(" ")}
                        />
                      )}
                    </svg>
                  </>
                )}
              </div>
            ) : (
              <p>正在读取开发素材…</p>
            )}
          </div>
          <footer className="canvas-caption">
            <span>
              {current?.case_id} · {current?.width} × {current?.height}
            </span>
            <span>
              {mode === "occlusion" && !preview
                ? "点击轮廓上的点，完成后添加遮挡"
                : "拖拽移动 · 方向键微调 · Shift 加大步幅"}
            </span>
          </footer>
          {mode === "occlusion" && !preview && (
            <div className="actions polygon-controls">
              <span>已选 {polygon.length} 个点</span>
              <button
                disabled={
                  polygon.length < 3 ||
                  locked ||
                  !request ||
                  request.occlusion_polygons.length >= 16
                }
                onClick={() => {
                  if (request) {
                    if (!validPolygon(polygon)) {
                      setError("遮挡轮廓需要至少三个不在同一直线上的点。");
                      return;
                    }
                    update({
                      ...request,
                      occlusion_polygons: [
                        ...request.occlusion_polygons,
                        polygon,
                      ],
                    });
                    setPolygon([]);
                  }
                }}
              >
                添加遮挡
              </button>
              <button disabled={!polygon.length} onClick={() => setPolygon([])}>
                取消绘制
              </button>
              <button
                disabled={!request?.occlusion_polygons.length || locked}
                onClick={() => {
                  if (request)
                    update({
                      ...request,
                      occlusion_polygons: request.occlusion_polygons.slice(
                        0,
                        -1,
                      ),
                    });
                }}
              >
                移除最后一层
              </button>
            </div>
          )}
          <div className="result-bar">
            <div>
              <b>本地预览</b>
              <p>用于检查定位、商品保留与手工遮挡。模型接触修补暂未启用。</p>
            </div>
            <button
              disabled={!active || locked}
              onClick={() => void render("下载")}
            >
              下载预览包 ↓
            </button>
            <button
              disabled={!request}
              onClick={() =>
                download(
                  new Blob([JSON.stringify(request, null, 2)], {
                    type: "application/json",
                  }),
                  `${request!.case_id}-parameters.json`,
                )
              }
            >
              导出参数
            </button>
          </div>
          {request && (
            <JobsPanel
              key={request.case_id}
              request={request}
              disabled={locked}
            />
          )}
          <section className="history">
            <div className="section-title">
              <h2>保存记录</h2>
              <span>{events.length} 次 · 服务端校验</span>
            </div>
            {events.length === 0 ? (
              <p className="hint">保存草稿后，可在这里查看和恢复历史参数。</p>
            ) : (
              <ol>
                {[...events].reverse().map((event) => (
                  <li key={event.sequence_no}>
                    <span className="history-version">
                      v{event.sequence_no}
                    </span>
                    <div>
                      <strong>
                        {event.action === "RESET"
                          ? "自动定位后保存"
                          : event.action === "APPLY_TEMPLATE"
                            ? "应用模板后保存"
                            : "保存编辑参数"}
                      </strong>
                      <small>
                        {new Date(event.occurred_at).toLocaleString("zh-CN")} ·{" "}
                        {event.event_hash.slice(0, 12)}
                      </small>
                    </div>
                    <button
                      disabled={locked}
                      onClick={() => {
                        update(structuredClone(event.after));
                        setNotice("历史参数已载入，保存后生成新版本");
                      }}
                    >
                      恢复参数
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </section>
        <aside className="properties">
          <h2>交互设置</h2>
          <label>
            商品素材
            <select
              id="product-revision"
              value={request?.product_revision ?? "v1"}
              disabled={!active || locked}
              onChange={(e) => {
                if (request)
                  update({
                    ...request,
                    product_revision: e.target.value as "v1" | "v2",
                  });
              }}
            >
              <option value="v2">结构修正版</option>
              <option value="v1">旧版素材（历史还原）</option>
            </select>
          </label>
          <label>
            商品视图
            <select
              disabled={!active || locked}
              value={request?.product_view_id ?? ""}
              onChange={(e) => {
                if (request) {
                  update({ ...request, product_view_id: e.target.value });
                  setImageError("");
                }
              }}
            >
              {catalog?.product_views.map((v) => (
                <option key={v.view_id} value={v.view_id}>
                  {v.view_id} · {v.yaw}° / {v.pitch}°
                </option>
              ))}
            </select>
          </label>
          {current && (
            <div
              className={`residual ${current.suggestion.residual.within_gate ? "" : "warning"}`}
            >
              <span>自动推荐视图</span>
              <b>{current.suggestion.product_view_id}</b>
              <small>
                角度残差 {current.suggestion.residual.yaw}° /{" "}
                {current.suggestion.residual.pitch}°
              </small>
            </div>
          )}
          <button
            className="wide"
            disabled={!active || locked}
            onClick={() => {
              if (current) {
                update(initial(current), "RESET");
                setPolygon([]);
              }
            }}
          >
            自动定位
          </button>
          <h3>位置与尺寸</h3>
          {request &&
            (
              [
                "center_x",
                "center_y",
                "width_ratio",
                "rotation_degrees",
              ] as const
            ).map((key, i) => (
              <label key={key}>
                <span className="parameter-label">
                  {["水平位置", "垂直位置", "商品尺寸", "旋转角度"][i]}
                  <b>
                    {key === "rotation_degrees"
                      ? `${request.placement[key]}°`
                      : `${(request.placement[key] * 100).toFixed(1)}%`}
                  </b>
                </span>
                <input
                  type="range"
                  disabled={locked}
                  min={
                    key === "rotation_degrees"
                      ? -180
                      : key === "width_ratio"
                        ? 0.02
                        : 0
                  }
                  max={
                    key === "rotation_degrees"
                      ? 180
                      : key === "width_ratio"
                        ? 0.5
                        : 1
                  }
                  step={key === "rotation_degrees" ? 1 : 0.001}
                  value={request.placement[key]}
                  onChange={(e) =>
                    update({
                      ...request,
                      placement: {
                        ...request.placement,
                        [key]: Number(e.target.value),
                      },
                    })
                  }
                />
              </label>
            ))}
          <details>
            <summary>遮罩与保留区域</summary>
            {request &&
              (["core_inset_px", "contact_radius_px"] as const).map(
                (key, i) => (
                  <label key={key}>
                    {i ? "接触带宽度" : "核心向内收缩"} · {request[key]} px
                    <input
                      type="range"
                      min={1}
                      max={i ? 64 : 32}
                      disabled={locked}
                      value={request[key]}
                      onChange={(e) =>
                        update({ ...request, [key]: Number(e.target.value) })
                      }
                    />
                  </label>
                ),
              )}
            <div className="mask-buttons">
              {[
                ["M_product", "商品"],
                ["M_core", "核心"],
                ["M_transition", "过渡"],
                ["M_contact", "接触"],
                ["M_occlusion", "遮挡"],
                ["M_visible_core", "可见核心"],
              ].map(([key, label]) => (
                <button
                  key={key}
                  disabled={!active || locked}
                  onClick={() => void render(key)}
                >
                  {label}
                </button>
              ))}
            </div>
            <p className="hint">
              接触带是商品边缘附近的几何区域，尚未进行嘴唇或手指语义分割。
            </p>
          </details>
          <section className="template-section">
            <h3>定位模板</h3>
            <label>
              载入已有模板
              <select
                disabled={locked}
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
              >
                <option value="">选择当前交互的模板</option>
                {availableTemplates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} · v{t.version}
                  </option>
                ))}
              </select>
            </label>
            <button
              disabled={
                !templateId ||
                locked ||
                !request ||
                !availableTemplates.some((t) => t.id === templateId)
              }
              onClick={() => {
                const t = availableTemplates.find((t) => t.id === templateId);
                if (t && request)
                  update(
                    applyTemplate(request, t.parameters),
                    "APPLY_TEMPLATE",
                  );
              }}
            >
              应用模板
            </button>
            <label className="template-name">
              另存为模板
              <input
                maxLength={80}
                placeholder="例如：正面轻微右偏"
                disabled={locked}
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
              />
            </label>
            <button
              className="wide"
              disabled={!templateName.trim() || !active || locked}
              onClick={() => void saveTemplate()}
            >
              保存模板新版本
            </button>
          </section>
        </aside>
      </main>
      <dialog
        ref={draftDialog}
        onCancel={() => {
          setPendingCase("");
          if (request) onCaseChange(request.case_id);
        }}
      >
        <h2>重新读取前保留当前调整</h2>
        <p>未保存的调整会被替换。你可以先保存，或放弃调整后继续。</p>
        <div className="actions">
          <button
            onClick={() => {
              draftDialog.current?.close();
              setPendingCase("");
              if (request) onCaseChange(request.case_id);
            }}
          >
            继续编辑
          </button>
          <button
            onClick={() => {
              draftDialog.current?.close();
              void loadCase(pendingCase);
              setPendingCase("");
            }}
          >
            放弃并读取
          </button>
          <button
            className="primary"
            disabled={locked || version === undefined}
            onClick={async () => {
              if (await save()) {
                draftDialog.current?.close();
                void loadCase(pendingCase);
                setPendingCase("");
              }
            }}
          >
            保存并读取
          </button>
        </div>
      </dialog>
    </div>
  );
}
