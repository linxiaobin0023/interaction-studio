import React, { Component, useEffect, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { AccountGate } from "./AccountGate";
import "./style.css";
declare global {
  interface Window {
    studioStartup?: { ready: () => void; fail: (message: string) => void };
  }
}

class StartupBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: Error) {
    console.error("Studio rendering failed", error);
    window.studioStartup?.fail(
      "页面显示遇到错误，请重新加载。已保存的内容仍保留在服务端。",
    );
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}
function StartupReady({ children }: { children: ReactNode }) {
  useEffect(() => {
    window.studioStartup?.ready();
  }, []);
  return children;
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <StartupBoundary>
      <StartupReady>
        <AccountGate>
          <App />
        </AccountGate>
      </StartupReady>
    </StartupBoundary>
  </React.StrictMode>,
);
