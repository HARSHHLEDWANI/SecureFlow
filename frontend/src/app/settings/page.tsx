"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import type { Variants } from "framer-motion";

import {
  fetchUserSettings,
  updateUserSettings,
  generateApiKey,
} from "@/lib/api";
import { useToast } from "@/components/Toast";
import {
  Copy,
  Plus,
  Trash2,
  Eye,
  EyeOff,
  Save,
} from "lucide-react";

/* ---------------- TYPES ---------------- */

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

/* ---------------- VARIANTS (FIXED & TYPED) ---------------- */

const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.2,
    },
  },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.4,
      ease: [0.16, 1, 0.3, 1],
    },
  },
};

/* ---------------- PAGE ---------------- */

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

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="space-y-8"
    >
      {/* Header */}
      <motion.div variants={itemVariants}>
        <h1 className="text-4xl font-bold bg-linear-to-r from-zinc-900 to-zinc-700 bg-clip-text text-transparent">
          Settings
        </h1>
        <p className="text-zinc-600 mt-2">
          Manage your account, preferences, and API keys.
        </p>
      </motion.div>

      {loading ? (
        <div className="h-48 bg-gradient-to-r from-zinc-200 to-zinc-100 rounded-2xl animate-pulse" />
      ) : (
        <div className="space-y-6">
          {/* Account */}
          <motion.section variants={itemVariants} className="space-y-6">
            <h2 className="text-2xl font-bold text-zinc-900">Account</h2>

            <div className="glass rounded-2xl p-6 border space-y-6">
              <div>
                <label className="text-sm font-semibold text-zinc-700 mb-2 block">
                  Email
                </label>
                <input
                  type="email"
                  value={formData.email || ""}
                  onChange={(e) =>
                    setFormData({ ...formData, email: e.target.value })
                  }
                  className="w-full px-4 py-2 border rounded-lg"
                />
              </div>

              <div>
                <label className="text-sm font-semibold text-zinc-700 mb-2 block">
                  Member Since
                </label>
                <input
                  disabled
                  value={
                    settings?.createdAt
                      ? new Date(settings.createdAt).toLocaleDateString()
                      : ""
                  }
                  className="w-full px-4 py-2 bg-zinc-50 border rounded-lg"
                />
              </div>
            </div>
          </motion.section>

          {/* Preferences */}
          <motion.section variants={itemVariants} className="space-y-6">
            <h2 className="text-2xl font-bold text-zinc-900">Preferences</h2>

            <div className="glass rounded-2xl p-6 border space-y-6">
              <div>
                <div className="flex justify-between mb-3">
                  <label className="font-semibold">Risk Threshold</label>
                  <span className="font-bold text-blue-600">
                    {formData.riskThreshold || 0}%
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={formData.riskThreshold || 0}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      riskThreshold: Number(e.target.value),
                    })
                  }
                  className="w-full"
                />
              </div>
            </div>
          </motion.section>

          {/* API Keys */}
          <motion.section variants={itemVariants} className="space-y-6">
            <div className="flex justify-between">
              <h2 className="text-2xl font-bold text-zinc-900">API Keys</h2>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={handleGenerateApiKey}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg"
              >
                <Plus className="w-4 h-4" />
                Generate
              </motion.button>
            </div>

            {newApiKey && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-4 bg-emerald-50 border rounded-lg"
              >
                <code className="text-xs break-all">
                  {showApiKey ? newApiKey : "•".repeat(32)}
                </code>
                <div className="flex gap-2 mt-2">
                  <button onClick={() => setShowApiKey(!showApiKey)}>
                    {showApiKey ? <EyeOff /> : <Eye />}
                  </button>
                  <button onClick={() => copyToClipboard(newApiKey)}>
                    <Copy />
                  </button>
                </div>
              </motion.div>
            )}
          </motion.section>

          {/* Save */}
          <motion.div variants={itemVariants} className="flex justify-end">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={handleSaveSettings}
              disabled={saving}
              className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg"
            >
              <Save className="w-4 h-4" />
              Save Changes
            </motion.button>
          </motion.div>
        </div>
      )}
    </motion.div>
  );
}
