"use client";

import { Component, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  message: string;
}

/**
 * Wraps a subtree and catches render errors (e.g. a chart library crashing,
 * a map failing to initialise). Shows a minimal inline card instead of
 * unmounting the entire page.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <SomeChartOrMap />
 *   </ErrorBoundary>
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error: unknown): State {
    return {
      hasError: true,
      message: error instanceof Error ? error.message : String(error),
    };
  }

  override render() {
    if (!this.state.hasError) return this.props.children;

    if (this.props.fallback) return this.props.fallback;

    return (
      <div className="broker-card flex items-start gap-3 text-sm text-[#8A7F74]">
        <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
        <div>
          <p className="font-medium text-[#2C3E50]">Komponenten kunne ikke lastes</p>
          <p className="text-xs mt-0.5 font-mono">{this.state.message}</p>
          <button
            className="text-xs text-[#4A6FA5] hover:underline mt-1"
            onClick={() => this.setState({ hasError: false, message: "" })}
          >
            Prøv igjen
          </button>
        </div>
      </div>
    );
  }
}
