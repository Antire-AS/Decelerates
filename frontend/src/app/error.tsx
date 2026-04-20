"use client";

import { useEffect } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="broker-card max-w-md w-full text-center space-y-4">
        <AlertTriangle className="w-10 h-10 text-amber-500 mx-auto" />
        <div>
          <p className="text-base font-semibold text-foreground">Noe gikk galt</p>
          <p className="text-sm text-muted-foreground mt-1">{error.message}</p>
          {error.digest && (
            <p className="text-xs text-muted-foreground mt-1 font-mono">ID: {error.digest}</p>
          )}
        </div>
        <button
          onClick={reset}
          className="flex items-center gap-2 px-4 py-2 mx-auto bg-primary text-primary-foreground text-sm rounded-lg hover:bg-primary/80"
        >
          <RotateCcw className="w-4 h-4" />
          Prøv igjen
        </button>
      </div>
    </div>
  );
}
