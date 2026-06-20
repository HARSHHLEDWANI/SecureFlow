"use client";

import { useMemo, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { ChevronDown, QrCode, Smartphone } from "lucide-react";
import type { UpiDemoUser } from "@/lib/types";
import { formatINR } from "@/lib/format";
import { UPI_HANDLES, upiDeepLink } from "@/lib/labFormat";

export interface PayForm {
  receiver_vpa: string;
  amount_inr: number;
  txn_type: string;
  note: string;
}

const TYPE_LABELS: Record<string, string> = {
  P2P: "Send Money",
  P2M: "Pay Merchant",
  BILL_PAY: "Bill Payment",
};

export default function PhoneFrame({
  users,
  sender,
  onSenderChange,
  form,
  onChange,
  onPay,
  busy,
}: {
  users: UpiDemoUser[];
  sender: UpiDemoUser | null;
  onSenderChange: (vpa: string) => void;
  form: PayForm;
  onChange: (patch: Partial<PayForm>) => void;
  onPay: () => void;
  busy: boolean;
}) {
  const [showQr, setShowQr] = useState(false);
  const receiverHandle = form.receiver_vpa.includes("@") ? form.receiver_vpa.split("@")[1] : "";
  const showSuggest = form.receiver_vpa.endsWith("@");

  const deepLink = useMemo(
    () => upiDeepLink(form.receiver_vpa || "merchant@upi", sender?.name ?? "SecureFlow", form.amount_inr, form.note),
    [form.receiver_vpa, form.amount_inr, form.note, sender],
  );

  const amountValid = form.amount_inr > 0 && form.amount_inr <= 10_000_000;
  const vpaValid = /^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}$/.test(form.receiver_vpa);

  return (
    <div className="mx-auto w-full max-w-[380px]">
      <div
        className="overflow-hidden rounded-[2.2rem] border-[6px] shadow-2xl"
        style={{ borderColor: "#0a0f1d", background: "linear-gradient(180deg,#0e1830,#0b1322)" }}
      >
        {/* status bar / notch */}
        <div className="relative flex h-7 items-center justify-center" style={{ background: "#0a0f1d" }}>
          <div className="h-1.5 w-20 rounded-full" style={{ background: "#1e2a44" }} />
        </div>

        {/* header */}
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <Smartphone className="h-4 w-4 text-[var(--accent-cyan)]" />
            <span className="text-sm font-bold">SecurePay UPI</span>
          </div>
          <button
            onClick={() => setShowQr((v) => !v)}
            className="rounded-md p-1.5 text-[var(--text-muted)] hover:text-[var(--text)]"
            title="Show QR"
          >
            <QrCode className="h-4 w-4" />
          </button>
        </div>

        {/* sender card */}
        <div className="mx-4 mb-3 rounded-xl p-3" style={{ background: "var(--surface-2)" }}>
          <label className="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-dim)]">
            Paying from
          </label>
          <div className="relative flex items-center gap-3">
            <div
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
              style={{ background: "var(--accent)" }}
            >
              {sender?.name?.[0] ?? "?"}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">{sender?.name ?? "Select user"}</p>
              <p className="truncate text-[11px] text-[var(--text-muted)]">
                {sender?.vpa} · {sender?.home_city}
              </p>
            </div>
            <div className="relative">
              <select
                value={sender?.vpa ?? ""}
                onChange={(e) => onSenderChange(e.target.value)}
                className="appearance-none rounded-md border border-[var(--border-strong)] bg-[var(--bg-elevated)] py-1 pl-2 pr-6 text-[11px]"
              >
                {users.map((u) => (
                  <option key={u.vpa} value={u.vpa}>
                    {u.name}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-1.5 top-1.5 h-3 w-3 text-[var(--text-dim)]" />
            </div>
          </div>
        </div>

        {showQr ? (
          <div className="flex flex-col items-center gap-3 px-4 pb-5">
            <div className="rounded-xl bg-white p-3">
              <QRCodeSVG value={deepLink} size={180} level="M" />
            </div>
            <p className="text-center text-[11px] text-[var(--text-muted)]">
              Scan to pay <span className="font-semibold text-[var(--text)]">{form.receiver_vpa || "—"}</span>
              <br />
              {formatINR(form.amount_inr)} · {TYPE_LABELS[form.txn_type]}
            </p>
            <p className="break-all text-center font-mono text-[9px] text-[var(--text-dim)]">{deepLink}</p>
          </div>
        ) : (
          <div className="space-y-3 px-4 pb-5">
            {/* amount — big */}
            <div className="rounded-xl py-3 text-center" style={{ background: "var(--bg-elevated)" }}>
              <div className="flex items-center justify-center gap-1">
                <span className="text-2xl font-semibold text-[var(--text-muted)]">₹</span>
                <input
                  type="number"
                  value={form.amount_inr}
                  min={1}
                  onChange={(e) => onChange({ amount_inr: Number(e.target.value) })}
                  className="w-40 bg-transparent text-center text-4xl font-bold text-[var(--text)] outline-none"
                />
              </div>
              <p className="mt-1 text-[11px] text-[var(--text-dim)]">
                {amountValid ? formatINR(form.amount_inr) : "Enter a valid amount"}
              </p>
            </div>

            {/* receiver */}
            <div className="relative">
              <label className="mb-1 block text-[10px] uppercase tracking-wide text-[var(--text-dim)]">
                Pay to (UPI ID)
              </label>
              <input
                value={form.receiver_vpa}
                onChange={(e) => onChange({ receiver_vpa: e.target.value })}
                placeholder="name@bank"
                className="field"
                style={{ borderColor: form.receiver_vpa && !vpaValid ? "var(--danger)" : undefined }}
              />
              {showSuggest && (
                <div className="absolute z-10 mt-1 flex w-full flex-wrap gap-1 rounded-lg border border-[var(--border-strong)] bg-[var(--bg-elevated)] p-2">
                  {UPI_HANDLES.map((h) => (
                    <button
                      key={h}
                      type="button"
                      onClick={() => onChange({ receiver_vpa: form.receiver_vpa.slice(0, -1) + h })}
                      className="rounded px-2 py-0.5 text-[11px] text-[var(--text-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]"
                    >
                      {h}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* note + type */}
            <input
              value={form.note}
              onChange={(e) => onChange({ note: e.target.value })}
              placeholder="Add a note"
              className="field"
            />
            <div className="grid grid-cols-3 gap-1.5">
              {Object.entries(TYPE_LABELS).map(([val, label]) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => onChange({ txn_type: val })}
                  className={`rounded-lg border py-1.5 text-[11px] transition ${
                    form.txn_type === val
                      ? "border-[var(--accent)] text-[var(--text)]"
                      : "border-[var(--border)] text-[var(--text-muted)]"
                  }`}
                  style={form.txn_type === val ? { background: "rgba(47,129,247,0.12)" } : undefined}
                >
                  {label}
                </button>
              ))}
            </div>

            <button
              onClick={onPay}
              disabled={busy || !amountValid || !vpaValid || !sender}
              className="btn btn-primary w-full text-base"
              style={{ background: "linear-gradient(90deg,#1f9d55,#2ea043)", borderColor: "#2ea043" }}
            >
              {busy ? "Processing…" : `Pay ${formatINR(form.amount_inr)}`}
            </button>
            <p className="text-center text-[10px] text-[var(--text-dim)]">
              Simulated payment · no real money moves · routed through SecureFlow detection
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
