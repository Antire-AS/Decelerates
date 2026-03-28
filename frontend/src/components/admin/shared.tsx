"use client";

export function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-3">
      <h2 className="text-sm font-semibold text-[#2C3E50]">{title}</h2>
      {subtitle && <p className="text-xs text-[#8A7F74] mt-0.5">{subtitle}</p>}
    </div>
  );
}

export function ActionButton({
  label, loadingLabel, onClick, variant = "primary", disabled,
}: {
  label: string; loadingLabel?: string; onClick: () => void;
  variant?: "primary" | "secondary" | "danger"; disabled?: boolean;
}) {
  const base = "px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";
  const styles = {
    primary:   `${base} bg-[#2C3E50] text-white hover:bg-[#3d5166]`,
    secondary: `${base} border border-[#D4C9B8] text-[#2C3E50] hover:bg-[#EDE8E3]`,
    danger:    `${base} bg-red-600 text-white hover:bg-red-700`,
  };
  return (
    <button onClick={onClick} disabled={disabled} className={styles[variant]}>
      {disabled && loadingLabel ? loadingLabel : label}
    </button>
  );
}

export function ResultMessage({ msg }: { msg: string | null }) {
  if (!msg) return null;
  const isErr = msg.startsWith("Feil");
  return (
    <p className={`mt-2 text-xs ${isErr ? "text-red-600" : "text-green-700"}`}>{msg}</p>
  );
}
