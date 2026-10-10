import { useState, useEffect } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8500';

interface Settings {
  base_url: string;
  model: string;
  api_key: string;
}

const DEFAULT_SETTINGS: Settings = {
  base_url: 'https://api.openai.com/v1',
  model: 'gpt-4o-mini',
  api_key: '',
};

export default function SettingsSection() {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [loaded, setLoaded] = useState(false);

  // Fetch current settings on mount
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_URL}/settings`);
        if (res.ok) {
          const data: Settings = await res.json();
          setSettings(data);
        }
      } catch {
        // Backend unreachable — keep defaults
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  const handleChange = (field: keyof Settings, value: string) => {
    setSettings((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const body: Record<string, string> = {};
      if (settings.base_url !== DEFAULT_SETTINGS.base_url) body.base_url = settings.base_url;
      if (settings.model !== DEFAULT_SETTINGS.model) body.model = settings.model;
      if (settings.api_key !== DEFAULT_SETTINGS.api_key) body.api_key = settings.api_key;

      const res = await fetch(`${API_URL}/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const result = await res.json();
      setSettings(result as Settings);
      setMessage({ type: 'success', text: `Settings saved — using "${result.model}" at ${result.base_url}` });
    } catch (e: unknown) {
      setMessage({ type: 'error', text: `Failed to save: ${e instanceof Error ? e.message : 'Unknown error'}` });
    } finally {
      setSaving(false);
    }
  };

  if (!loaded) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="p-8 text-center text-gray-400 text-sm">Loading settings...</div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="font-semibold text-gray-800 flex items-center gap-2">
          <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          LLM Provider Settings
        </h2>
      </div>

      {/* Form */}
      <div className="p-5 space-y-4">
        {/* Model */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
          <input
            type="text"
            value={settings.model}
            onChange={(e) => handleChange('model', e.target.value)}
            placeholder="e.g. gpt-4o-mini, ornith-1.0-35b_moe"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
          />
        </div>

        {/* Base URL */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Base URL</label>
          <input
            type="text"
            value={settings.base_url}
            onChange={(e) => handleChange('base_url', e.target.value)}
            placeholder="e.g. http://192.168.1.81:1234/v1"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent font-mono text-xs"
          />
          <p className="text-xs text-gray-400 mt-1">OpenAI-compatible API endpoint (must end in /v1)</p>
        </div>

        {/* API Key */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
          <input
            type="password"
            value={settings.api_key}
            onChange={(e) => handleChange('api_key', e.target.value)}
            placeholder="sk-... or not-needed"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent font-mono text-xs"
          />
          <p className="text-xs text-gray-400 mt-1">
            Leave empty for providers that don't require auth (LM Studio, Ollama)
          </p>
        </div>

        {/* Status message */}
        {message && (
          <div
            className={`text-sm p-3 rounded-lg ${
              message.type === 'success'
                ? 'bg-green-50 text-green-700 border border-green-200'
                : 'bg-red-50 text-red-700 border border-red-200'
            }`}
          >
            {message.text}
          </div>
        )}

        {/* Save button */}
        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full bg-gray-800 hover:bg-gray-900 disabled:bg-gray-300 text-white py-2.5 rounded-lg text-sm font-medium transition-colors disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {saving ? (
            <>
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Saving...
            </>
          ) : (
            'Save Settings'
          )}
        </button>
        <p className="text-xs text-gray-400 text-center">
          Changes take effect immediately — no restart required.
        </p>
      </div>
    </div>
  );
}
