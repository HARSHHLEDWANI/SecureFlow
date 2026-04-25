"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Copy, Trash2, Plus, Eye, EyeOff, Check } from "lucide-react";
import { useAuth } from "@/context/auth";
import {
  fetchUserSettings,
  updateUserSettings,
  generateApiKey,
  revokeApiKey,
  UserSettings,
} from "@/lib/api";

export default function SettingsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [dataLoading, setDataLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [email, setEmail] = useState("");
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [newKeyName, setNewKeyName] = useState("");
  const [generatingKey, setGeneratingKey] = useState(false);
  const [revealedKey, setRevealedKey] = useState<{ id: string; key: string } | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/auth");
  }, [user, loading, router]);

  useEffect(() => {
    if (!user) return;
    fetchUserSettings()
      .then((s) => {
        setSettings(s);
        setEmail(s.email);
      })
      .finally(() => setDataLoading(false));
  }, [user]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaveMsg(null);
    setSaveError(null);
    try {
      const updated = await updateUserSettings({ email });
      setSettings((s) => s ? { ...s, ...updated } : s);
      setSaveMsg("Profile updated successfully.");
    } catch (err) {
      setSaveError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function handleGenerateKey(e: React.FormEvent) {
    e.preventDefault();
    if (!newKeyName.trim()) return;
    setGeneratingKey(true);
    try {
      const result = await generateApiKey(newKeyName.trim());
      setRevealedKey({ id: result.id, key: result.key });
      setSettings((s) =>
        s
          ? {
              ...s,
              apiKeys: [
                { id: result.id, name: result.name, createdAt: result.createdAt, lastUsedAt: null, expiresAt: null },
                ...s.apiKeys,
              ],
            }
          : s
      );
      setNewKeyName("");
    } catch (err) {
      setSaveError((err as Error).message);
    } finally {
      setGeneratingKey(false);
    }
  }

  async function handleRevoke(keyId: string) {
    try {
      await revokeApiKey(keyId);
      setSettings((s) => s ? { ...s, apiKeys: s.apiKeys.filter((k) => k.id !== keyId) } : s);
      if (revealedKey?.id === keyId) setRevealedKey(null);
    } catch (err) {
      setSaveError((err as Error).message);
    }
  }

  async function copyKey(key: string) {
    await navigator.clipboard.writeText(key);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (loading || dataLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-32 bg-slate-800/40 rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-slate-400 text-sm mt-1">Manage your profile and API access</p>
      </div>

      {saveError && (
        <div className="px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {saveError}
        </div>
      )}

      {/* Profile */}
      <form
        onSubmit={handleSave}
        className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-6 space-y-4"
      >
        <h2 className="text-base font-semibold text-white">Account</h2>
        <div className="space-y-1">
          <label className="text-sm text-slate-400">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-3 py-2 bg-slate-800 border border-slate-700/40 rounded-lg text-sm text-white focus:outline-none focus:border-cyan-500/50"
          />
        </div>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-slate-400 mb-1">Role</p>
            <p className="text-white font-medium">{settings?.role}</p>
          </div>
          <div>
            <p className="text-slate-400 mb-1">Member since</p>
            <p className="text-white">{settings ? new Date(settings.createdAt).toLocaleDateString() : "—"}</p>
          </div>
        </div>
        {saveMsg && <p className="text-emerald-400 text-sm">{saveMsg}</p>}
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-60 text-slate-900 font-semibold rounded-lg text-sm transition-colors"
        >
          {saving ? "Saving…" : "Save Changes"}
        </button>
      </form>

      {/* API Keys */}
      <div className="bg-slate-900/60 border border-slate-700/40 rounded-xl p-6 space-y-4">
        <h2 className="text-base font-semibold text-white">API Keys</h2>
        <p className="text-slate-400 text-sm">
          API keys allow external integrations to authenticate without logging in.
          The plaintext key is shown only once upon creation.
        </p>

        {/* Revealed key banner */}
        {revealedKey && (
          <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg space-y-2">
            <p className="text-amber-400 text-sm font-medium">Save this key — it won't be shown again.</p>
            <div className="flex items-center gap-2">
              <code className="flex-1 text-xs text-white break-all font-mono">
                {showKey ? revealedKey.key : "•".repeat(48)}
              </code>
              <button onClick={() => setShowKey((v) => !v)} className="text-slate-400 hover:text-white">
                {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
              <button onClick={() => copyKey(revealedKey.key)} className="text-slate-400 hover:text-white">
                {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>
          </div>
        )}

        {/* Generate new key */}
        <form onSubmit={handleGenerateKey} className="flex gap-2">
          <input
            type="text"
            placeholder="Key name (e.g. CI pipeline)"
            value={newKeyName}
            onChange={(e) => setNewKeyName(e.target.value)}
            className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700/40 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
          />
          <button
            type="submit"
            disabled={generatingKey || !newKeyName.trim()}
            className="flex items-center gap-1.5 px-4 py-2 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-60 text-slate-900 font-semibold rounded-lg text-sm transition-colors"
          >
            <Plus className="w-4 h-4" /> Generate
          </button>
        </form>

        {/* Existing keys */}
        {settings && settings.apiKeys.length === 0 ? (
          <p className="text-slate-500 text-sm">No API keys yet.</p>
        ) : (
          <div className="divide-y divide-slate-700/40">
            {settings?.apiKeys.map((key) => (
              <div key={key.id} className="flex items-center justify-between py-3">
                <div>
                  <p className="text-white text-sm font-medium">{key.name}</p>
                  <p className="text-slate-500 text-xs mt-0.5">
                    Created {new Date(key.createdAt).toLocaleDateString()}
                    {key.lastUsedAt && ` · Last used ${new Date(key.lastUsedAt).toLocaleDateString()}`}
                  </p>
                </div>
                <button
                  onClick={() => handleRevoke(key.id)}
                  className="p-1.5 text-slate-400 hover:text-red-400 transition-colors"
                  title="Revoke key"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
