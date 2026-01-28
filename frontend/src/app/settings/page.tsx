"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { fetchUserSettings, updateUserSettings, generateApiKey } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { Copy, Plus, Trash2, Eye, EyeOff, Save } from "lucide-react";

interface UserSettings {
  id: string;
  email: string;
  riskThreshold: number;
  notificationsEnabled: boolean;
  twoFactorEnabled: boolean;
  apiKeys: string[];
  createdAt: string;
  updatedAt: string;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState<Partial<UserSettings>>({});
  const [showApiKey, setShowApiKey] = useState(false);
  const [newApiKey, setNewApiKey] = useState<string | null>(null);
  const { show } = useToast();

  useEffect(() => {
    const loadSettings = async () => {
      try {
        setLoading(true);
        const data = await fetchUserSettings();
        if (data) {
          setSettings(data);
          setFormData(data);
        }
      } catch (error) {
        console.error("Error loading settings:", error);
        show("Error", "Failed to load settings", "error");
      } finally {
        setLoading(false);
      }
    };

    loadSettings();
  }, [show]);

  const handleSaveSettings = async () => {
    try {
      setSaving(true);
      await updateUserSettings(formData);
      show("Success", "Settings updated successfully", "success");
    } catch (error) {
      console.error("Error saving settings:", error);
      show("Error", "Failed to save settings", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleGenerateApiKey = async () => {
    try {
      const response = await generateApiKey();
      setNewApiKey(response.key);
      show("Success", "API key generated successfully", "success");
    } catch (error) {
      console.error("Error generating API key:", error);
      show("Error", "Failed to generate API key", "error");
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    show("Copied", "Copied to clipboard", "success");
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
        delayChildren: 0.2,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.4, ease: "easeOut" },
    },
  };

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="space-y-8"
    >
      {/* Header */}
      <motion.div variants={itemVariants}>
        <h1 className="text-4xl font-bold bg-gradient-to-r from-zinc-900 to-zinc-700 bg-clip-text text-transparent">
          Settings
        </h1>
        <p className="text-zinc-600 text-base mt-2">Manage your account, preferences, and API keys.</p>
      </motion.div>

      {loading ? (
        <div className="space-y-4">
          <div className="h-48 bg-gradient-to-r from-zinc-200 to-zinc-100 rounded-2xl animate-pulse" />
        </div>
      ) : (
        <div className="space-y-6">
          {/* Account Section */}
          <motion.section variants={itemVariants} className="space-y-6">
            <h2 className="text-2xl font-bold text-zinc-900">Account</h2>

            <div className="glass rounded-2xl p-6 border border-zinc-200/50 space-y-6">
              {/* Email */}
              <div>
                <label className="block text-sm font-semibold text-zinc-700 mb-2">Email</label>
                <input
                  type="email"
                  value={formData.email || ""}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full px-4 py-2 bg-white border border-zinc-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                />
              </div>

              {/* Created At */}
              <div>
                <label className="block text-sm font-semibold text-zinc-700 mb-2">Member Since</label>
                <input
                  type="text"
                  value={settings?.createdAt ? new Date(settings.createdAt).toLocaleDateString() : ""}
                  disabled
                  className="w-full px-4 py-2 bg-zinc-50 border border-zinc-200 rounded-lg text-zinc-600"
                />
              </div>
            </div>
          </motion.section>

          {/* Preferences Section */}
          <motion.section variants={itemVariants} className="space-y-6">
            <h2 className="text-2xl font-bold text-zinc-900">Preferences</h2>

            <div className="glass rounded-2xl p-6 border border-zinc-200/50 space-y-6">
              {/* Risk Threshold */}
              <div>
                <div className="flex items-center justify-between mb-4">
                  <label className="text-sm font-semibold text-zinc-700">Risk Score Threshold</label>
                  <span className="text-lg font-bold text-blue-600">
                    {formData.riskThreshold || 0}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={formData.riskThreshold || 0}
                  onChange={(e) =>
                    setFormData({ ...formData, riskThreshold: parseInt(e.target.value) })
                  }
                  className="w-full h-2 bg-zinc-200 rounded-lg appearance-none cursor-pointer"
                />
                <p className="text-xs text-zinc-500 mt-2">
                  Transactions with risk score above this threshold will be flagged for review.
                </p>
              </div>

              {/* Notifications */}
              <div className="border-t border-zinc-200 pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-zinc-700">Email Notifications</p>
                    <p className="text-xs text-zinc-500 mt-1">
                      Receive alerts for flagged transactions
                    </p>
                  </div>
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() =>
                      setFormData({
                        ...formData,
                        notificationsEnabled: !formData.notificationsEnabled,
                      })
                    }
                    className={`relative inline-flex h-8 w-14 items-center rounded-full transition-colors ${
                      formData.notificationsEnabled ? "bg-blue-600" : "bg-zinc-300"
                    }`}
                  >
                    <motion.div
                      layout
                      className={`inline-flex h-6 w-6 transform items-center justify-center rounded-full bg-white transition-transform ${
                        formData.notificationsEnabled ? "translate-x-7" : "translate-x-1"
                      }`}
                    />
                  </motion.button>
                </div>
              </div>

              {/* Two Factor */}
              <div className="border-t border-zinc-200 pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-zinc-700">Two-Factor Authentication</p>
                    <p className="text-xs text-zinc-500 mt-1">
                      Add an extra layer of security to your account
                    </p>
                  </div>
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() =>
                      setFormData({
                        ...formData,
                        twoFactorEnabled: !formData.twoFactorEnabled,
                      })
                    }
                    className={`relative inline-flex h-8 w-14 items-center rounded-full transition-colors ${
                      formData.twoFactorEnabled ? "bg-blue-600" : "bg-zinc-300"
                    }`}
                  >
                    <motion.div
                      layout
                      className={`inline-flex h-6 w-6 transform items-center justify-center rounded-full bg-white transition-transform ${
                        formData.twoFactorEnabled ? "translate-x-7" : "translate-x-1"
                      }`}
                    />
                  </motion.button>
                </div>
              </div>
            </div>
          </motion.section>

          {/* API Keys Section */}
          <motion.section variants={itemVariants} className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold text-zinc-900">API Keys</h2>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={handleGenerateApiKey}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white font-semibold rounded-lg hover:bg-emerald-700 transition-all"
              >
                <Plus className="w-4 h-4" />
                Generate New Key
              </motion.button>
            </div>

            <div className="glass rounded-2xl p-6 border border-zinc-200/50 space-y-4">
              {/* New Generated Key */}
              {newApiKey && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg"
                >
                  <p className="text-sm font-semibold text-emerald-900 mb-2">New API Key</p>
                  <div className="flex items-center gap-2 p-3 bg-white rounded border border-emerald-200">
                    <code className="flex-1 text-xs font-mono text-zinc-700">
                      {showApiKey ? newApiKey : "•".repeat(32)}
                    </code>
                    <motion.button
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={() => setShowApiKey(!showApiKey)}
                      className="p-1 text-zinc-400 hover:text-zinc-600"
                    >
                      {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </motion.button>
                    <motion.button
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={() => copyToClipboard(newApiKey)}
                      className="p-1 text-zinc-400 hover:text-zinc-600"
                    >
                      <Copy className="w-4 h-4" />
                    </motion.button>
                  </div>
                  <p className="text-xs text-emerald-700 mt-2">
                    Save this key in a secure location. You won't be able to see it again.
                  </p>
                </motion.div>
              )}

              {/* Existing Keys */}
              <div className="space-y-2">
                {formData.apiKeys && formData.apiKeys.length > 0 ? (
                  formData.apiKeys.map((key, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.05 }}
                      className="flex items-center justify-between p-3 bg-zinc-50 rounded-lg border border-zinc-200 hover:border-zinc-300 transition-colors group"
                    >
                      <code className="text-xs font-mono text-zinc-600">{key.slice(0, 24)}...</code>
                      <motion.button
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.95 }}
                        className="p-1 text-zinc-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-all"
                      >
                        <Trash2 className="w-4 h-4" />
                      </motion.button>
                    </motion.div>
                  ))
                ) : (
                  <p className="text-sm text-zinc-500">No API keys created yet.</p>
                )}
              </div>
            </div>
          </motion.section>

          {/* Save Button */}
          <motion.div variants={itemVariants} className="flex justify-end">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={handleSaveSettings}
              disabled={saving}
              className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:bg-blue-400 transition-all shadow-lg"
            >
              {saving ? (
                <>
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity }}
                    className="w-4 h-4 border-2 border-white border-t-transparent rounded-full"
                  />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  Save Changes
                </>
              )}
            </motion.button>
          </motion.div>
        </div>
      )}
    </motion.div>
  );
}
