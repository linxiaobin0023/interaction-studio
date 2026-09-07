export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api/v1/development${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail?.code || `请求未完成（${response.status}）`);
  }
  return response.json();
}
export const json = (body: unknown, method = "POST"): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json", "X-Studio-Request": "1" },
  body: JSON.stringify(body),
});
export const errorText = (e: unknown) =>
  e instanceof Error ? e.message : "请求未完成，请重试";
