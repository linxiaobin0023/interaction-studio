const errors: Record<string, string> = {
  LOGIN_FAILED:
    "账号或密码不正确，或账号已停用/暂时锁定。连续失败 5 次将锁定 15 分钟。",
  ACCOUNT_CONFLICT: "账号名称已被使用。",
  CURRENT_PASSWORD_INCORRECT: "当前密码不正确。",
  ROLE_FORBIDDEN: "当前账号没有此操作权限。",
  AUTH_REQUIRED: "会话已过期，请重新登录。",
  CSRF_CHECK_FAILED: "登录页面地址与服务不一致，请刷新页面后重试。",
  AUTH_STORAGE_UNAVAILABLE: "账号服务暂时不可用，请稍后重试。",
};
export const sessionExpired = errors.AUTH_REQUIRED;

export function loginCredentials(form: FormData) {
  return {
    username: String(form.get("username") ?? "").trim(),
    password: String(form.get("password") ?? ""),
  };
}

export function authError(status: number, body: unknown): string {
  const detail =
    body && typeof body === "object" && "detail" in body ? body.detail : null;
  if (Array.isArray(detail)) {
    // Do not display the server's input values: they can contain passwords.
    const fields = new Set(
      detail.flatMap((item: unknown) => {
        if (!item || typeof item !== "object" || !("loc" in item)) return [];
        return Array.isArray(item.loc) ? item.loc.slice(1) : [];
      }),
    );
    if (fields.has("username"))
      return "账号格式不正确：请输入 3–64 位字母、数字、下划线、点或短横线，并以字母或数字开头。";
    if (fields.has("password")) return "请输入密码，长度不得超过 256 个字符。";
    if (fields.has("new_password")) return "新密码长度须为 12–256 个字符。";
    if (fields.has("current_password")) return "请输入当前密码。";
    if (fields.has("roles")) return "角色组合不符合要求，请检查所选角色。";
    return "提交的信息格式不正确，请检查填写内容。";
  }
  if (
    detail &&
    typeof detail === "object" &&
    "code" in detail &&
    typeof detail.code === "string" &&
    errors[detail.code]
  )
    return errors[detail.code];
  if (status >= 500) return "登录或账号服务暂时不可用，请稍后重试。";
  if (status === 422) return "提交的信息格式不正确，请检查填写内容。";
  return `请求未完成（${status}），请刷新页面后重试。`;
}

export async function auth<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1/auth${path}`, options);
  } catch {
    throw new Error("无法连接账号服务，请检查网络连接后重试。");
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new Error(authError(response.status, body));
  if (body === null) throw new Error("账号服务返回异常，请刷新页面后重试。");
  return body as T;
}
