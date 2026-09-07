import {
  createContext,
  useContext,
  useEffect,
  useState,
  useRef,
  type ReactNode,
} from "react";
import { errorText, json } from "./api";
import { auth, loginCredentials, sessionExpired } from "./auth";
import "./accounts.css";
import "./access.css";

type Account = {
  id: string;
  username: string;
  roles: string[];
  enabled?: boolean;
  auth_mode?: string;
};
type AccountSession = Account & {
  openSettings: () => void;
  logout: () => void;
};
const AccountContext = createContext<AccountSession | null>(null);
export const useAccount = () => useContext(AccountContext);
const roleNames: Record<string, string> = {
  ADMIN: "技术管理员",
  OPERATOR: "内容操作员",
  REVIEWER: "审核员",
  AUDITOR: "只读审计",
  CUSTODIAN: "素材保管员",
  GATE_SIGNER: "Gate 签署人",
};
function AccessIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.3"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M5 7V5a3 3 0 0 1 6 0v2M4 7h8v7H4zM8 10v1" />
    </svg>
  );
}

function AccessShell({ children }: { children: ReactNode }) {
  return (
    <main className="account-login">
      <div className="access-entry">
        <div className="access-brand">
          <span className="access-logo" aria-hidden="true">
            IS
          </span>
          <strong>Interaction Studio</strong>
        </div>
        {children}
        <p className="access-footer">人物与商品交互创作平台</p>
      </div>
    </main>
  );
}

export function AccountGate({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<Account | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [manage, setManage] = useState(false);
  useEffect(() => {
    let active = true;
    void auth<Account>("/me")
      .then((value) => {
        if (active) setAccount(value);
      })
      .catch((e) => {
        if (active && errorText(e) !== sessionExpired) setError(errorText(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  async function login(form: HTMLFormElement) {
    setBusy(true);
    setError("");
    try {
      await auth<Account>("/login", json(loginCredentials(new FormData(form))));
      setAccount(await auth<Account>("/me"));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  async function logout() {
    if (!window.confirm("退出会丢弃尚未保存的编辑和审核内容，确定退出？"))
      return;
    try {
      await auth("/logout", json({}));
      setAccount(null);
      setManage(false);
    } catch (e) {
      setError(errorText(e));
    }
  }
  if (loading)
    return (
      <AccessShell>
        <p className="access-loading" role="status">
          正在读取登录状态…
        </p>
      </AccessShell>
    );
  if (!account)
    return (
      <AccessShell>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void login(e.currentTarget);
          }}
        >
          <h1>登录账号</h1>
          <p>欢迎回来，登录以继续创作与审核。</p>
          <label>
            账号
            <input
              name="username"
              autoComplete="username"
              placeholder="输入账号"
              autoCapitalize="none"
              spellCheck={false}
              required
            />
          </label>
          <label>
            密码
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              placeholder="输入密码"
              required
              maxLength={256}
            />
          </label>
          {error && <p role="alert">{error}</p>}
          <button className="primary" disabled={busy}>
            {busy ? "正在登录…" : "登录"}
          </button>
          <div className="access-login-help">
            <AccessIcon />
            <p>如需开通账号或重置密码，请联系管理员。</p>
          </div>
        </form>
      </AccessShell>
    );
  return (
    <AccountContext.Provider
      value={{
        ...account,
        openSettings: () => setManage(true),
        logout: () => void logout(),
      }}
    >
      {error && (
        <p className="account-error" role="alert">
          {error}
        </p>
      )}
      {manage && (
        <AccountSettingsDialog onClose={() => setManage(false)}>
          <AccountSettings
            account={account}
            onPasswordChanged={() => {
              setAccount(null);
              setManage(false);
              setError("密码已更新，请重新登录。");
            }}
          />
        </AccountSettingsDialog>
      )}
      {children}
    </AccountContext.Provider>
  );
}

export function AccountControls() {
  const account = useAccount();
  if (!account) return null;
  return (
    <details className="console-account">
      <summary>
        <span className="account-avatar">
          {account.username.slice(0, 1).toUpperCase()}
        </span>
        <span>{account.username}</span>
        <span aria-hidden="true">⌄</span>
      </summary>
      <div className="account-menu">
        <strong>{account.username}</strong>
        <p>{account.roles.map((r) => roleNames[r] || r).join(" / ")}</p>
        {account.auth_mode === "local" ? (
          <p>本地无认证模式</p>
        ) : (
          <>
            <button onClick={account.openSettings}>账号设置</button>
            <button onClick={account.logout}>退出登录</button>
          </>
        )}
      </div>
    </details>
  );
}

function AccountSettingsDialog({
  children,
  onClose,
}: {
  children: ReactNode;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  return (
    <dialog
      ref={dialog}
      className="account-dialog"
      aria-label="账号设置"
      onCancel={onClose}
    >
      <button className="account-dialog-close" onClick={onClose} autoFocus>
        关闭账号设置
      </button>
      {children}
    </dialog>
  );
}

function AccountSettings({
  account,
  onPasswordChanged,
}: {
  account: Account;
  onPasswordChanged: () => void;
}) {
  const [users, setUsers] = useState<Account[]>([]);
  const [events, setEvents] = useState<
    {
      id: string;
      actor: string;
      action: string;
      subject: string;
      created_at: string;
    }[]
  >([]);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [roles, setRoles] = useState(["OPERATOR"]);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function refresh() {
    if (!account.roles.includes("ADMIN")) return;
    setUsers((await auth<{ users: Account[] }>("/users")).users);
    setEvents((await auth<{ events: typeof events }>("/events")).events);
  }
  useEffect(() => {
    void refresh().catch((e) => setError(errorText(e)));
  }, []);
  async function execute(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
      await refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="account-settings">
      <h2>账号设置</h2>
      {error && (
        <p role="alert" className="account-error">
          {error}
        </p>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (
            !window.confirm(
              "更改密码会退出所有已登录会话。请先保存编辑和审核内容。继续？",
            )
          )
            return;
          void execute(async () => {
            await auth(
              "/password",
              json({
                current_password: oldPassword,
                new_password: newPassword,
              }),
            );
            onPasswordChanged();
          });
        }}
      >
        <h3>更改密码</h3>
        <label>
          当前密码
          <input
            type="password"
            autoComplete="current-password"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
            required
            maxLength={256}
          />
        </label>
        <label>
          新密码（至少 12 位）
          <input
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            minLength={12}
            maxLength={256}
          />
        </label>
        <button disabled={busy}>更新密码并退出</button>
      </form>
      {account.roles.includes("ADMIN") && (
        <>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void execute(async () => {
                await auth("/users", json({ username: name, password, roles }));
                setName("");
                setPassword("");
              });
            }}
          >
            <h3>创建独立账号</h3>
            <label>
              账号（3–64 位字母、数字、点、下划线或连字符）
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                pattern="[a-zA-Z0-9][a-zA-Z0-9_.\-]{2,63}"
                required
                autoComplete="off"
              />
            </label>
            <label>
              初始密码（至少 12 位）
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={12}
                maxLength={256}
                required
                autoComplete="new-password"
              />
            </label>
            <fieldset>
              <legend>权限（管理员与 Gate 签署人不能兼任）</legend>
              {Object.entries(roleNames).map(([role, title]) => (
                <label key={role} className="account-role">
                  <input
                    type="checkbox"
                    checked={roles.includes(role)}
                    disabled={
                      (role === "ADMIN" && roles.includes("GATE_SIGNER")) ||
                      (role === "GATE_SIGNER" && roles.includes("ADMIN"))
                    }
                    onChange={(e) =>
                      setRoles(
                        e.target.checked
                          ? [...roles, role]
                          : roles.filter((r) => r !== role),
                      )
                    }
                  />
                  {title}
                </label>
              ))}
            </fieldset>
            <p className="hint">
              素材保管员和 Gate 签署人的正式业务流程尚未开放。
            </p>
            <button disabled={busy || roles.length === 0}>创建账号</button>
          </form>
          <h3>已有账号</h3>
          <ul className="account-users">
            {users.map((user) => (
              <li key={user.id}>
                <span>
                  {user.username} ·{" "}
                  {user.roles.map((r) => roleNames[r]).join(" / ")} ·{" "}
                  {user.enabled ? "启用" : "停用"}
                </span>
                <button
                  disabled={busy || user.id === account.id}
                  onClick={() =>
                    void execute(() =>
                      auth(
                        `/users/${user.id}/status`,
                        json({ enabled: !user.enabled }, "PUT"),
                      ),
                    )
                  }
                >
                  {user.enabled ? "停用" : "启用"}
                </button>
              </li>
            ))}
          </ul>
          <details>
            <summary>最近的账号安全记录</summary>
            <ul>
              {events.map((event) => (
                <li key={event.id}>
                  {new Date(event.created_at).toLocaleString("zh-CN")} ·{" "}
                  {event.action} ·{" "}
                  {users.find((u) => u.id === event.subject)?.username ||
                    event.subject}
                </li>
              ))}
            </ul>
          </details>
        </>
      )}
    </section>
  );
}
