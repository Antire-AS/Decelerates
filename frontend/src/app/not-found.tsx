import Link from "next/link";
import { Home } from "lucide-react";

export const metadata = {
  title: "Siden ble ikke funnet · Broker Accelerator",
};

export default function NotFound() {
  return (
    <div className="broker-card max-w-md mx-auto text-center py-12">
      <p className="text-5xl font-bold text-brand-dark">404</p>
      <h1 className="mt-4 text-xl font-semibold text-brand-dark">Siden ble ikke funnet</h1>
      <p className="mt-2 text-sm text-brand-muted">
        Lenken kan være utdatert, eller siden er flyttet.
      </p>
      <Link
        href="/dashboard"
        className="mt-6 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-dark text-white text-sm font-medium hover:bg-primary/90"
      >
        <Home className="w-4 h-4" />
        Til forsiden
      </Link>
    </div>
  );
}
