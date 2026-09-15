import { Component, type ErrorInfo, type ReactNode } from "react";
import { ErrorState } from "./States";

interface Props {
  children: ReactNode;
  /** A label for what failed, e.g. "Alert queue" — shown in the fallback so
   * a page with several boundaries reads clearly about WHICH panel broke. */
  panelName?: string;
}
interface State {
  hasError: boolean;
  message: string;
}

/** One panel's crash must never blank the whole page — each major panel on
 * a screen gets its own boundary (hardening item #1/#4). */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: "" };

  static getDerivedStateFromError(error: unknown): State {
    return { hasError: true, message: error instanceof Error ? error.message : String(error) };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error(`[${this.props.panelName ?? "panel"}] crashed:`, error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="panel">
          <ErrorState
            title={this.props.panelName ? `${this.props.panelName} failed to load` : "This panel failed to load"}
            message={this.state.message || "An unexpected error occurred while rendering this panel."}
            onRetry={() => this.setState({ hasError: false, message: "" })}
          />
        </div>
      );
    }
    return this.props.children;
  }
}
