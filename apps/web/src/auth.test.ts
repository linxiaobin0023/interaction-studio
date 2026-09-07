import assert from "node:assert/strict";
import test from "node:test";
import { auth, authError, loginCredentials } from "./auth.ts";

test("login reads current form values and trims only the username", () => {
  const form = new FormData();
  form.set("username", " studio_owner\u00a0");
  form.set("password", "  intentional password spaces  ");
  assert.deepEqual(loginCredentials(form), {
    username: "studio_owner",
    password: "  intentional password spaces  ",
  });
});

test("validation messages identify fields without exposing rejected secrets", () => {
  const message = authError(422, {
    detail: [
      {
        loc: ["body", "password"],
        input: "private-password",
        msg: "private-password",
      },
    ],
  });
  assert.match(message, /密码.*256/);
  assert.doesNotMatch(message, /private-password/);
  assert.match(
    authError(422, { detail: [{ loc: ["body", "username"] }] }),
    /账号格式/,
  );
  assert.match(
    authError(422, { detail: [{ loc: ["body", "roles"] }] }),
    /角色/,
  );
});

test("authentication distinguishes rejected credentials and server failures", () => {
  assert.match(
    authError(401, { detail: { code: "LOGIN_FAILED" } }),
    /账号或密码/,
  );
  assert.match(
    authError(403, { detail: { code: "CSRF_CHECK_FAILED" } }),
    /地址/,
  );
  assert.match(authError(503, null), /暂时不可用/);
});

test("non-JSON and network failures yield actionable messages", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async () => new Response("<html>gateway error</html>", { status: 502 }),
  );
  await assert.rejects(auth("/login"), /暂时不可用/);
  t.mock.restoreAll();
  t.mock.method(globalThis, "fetch", async () => {
    throw new TypeError("Failed to fetch");
  });
  await assert.rejects(auth("/login"), /无法连接账号服务/);
});
