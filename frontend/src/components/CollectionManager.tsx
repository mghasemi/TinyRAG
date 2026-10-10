import { useState, useEffect, useRef } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8500';

interface Collection {
  name: string;
  doc_count: number;
}

interface CollectionManagerProps {
  onSwitchCollection?: () => void;
}

export default function CollectionManager({ onSwitchCollection }: CollectionManagerProps) {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [active, setActive] = useState('Default');
  const [open, setOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const fetchCollections = async () => {
    try {
      const res = await fetch(`${API_URL}/collections`);
      if (res.ok) {
        const data = await res.json();
        setCollections(data.collections || []);
        setActive(data.active || 'Default');
      }
    } catch {
      // Backend unreachable
    }
  };

  useEffect(() => {
    fetchCollections();
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
        setMessage(null);
        setNewName('');
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const switchCollection = async (name: string) => {
    if (name === active) return;
    try {
      const res = await fetch(`${API_URL}/collections/active`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      if (res.ok) {
        setActive(name);
        setOpen(false);
        onSwitchCollection?.();
        fetchCollections();
      }
    } catch {
      // ignore
    }
  };

  const createCollection = async () => {
    const name = newName.trim();
    if (!name) return;
    setCreating(true);
    setMessage(null);
    try {
      const res = await fetch(`${API_URL}/collections`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      const data = await res.json();
      if (res.ok) {
        setMessage({ type: 'success', text: `Created "${name}"` });
        setNewName('');
        await switchCollection(name);
      } else {
        setMessage({ type: 'error', text: data.detail || 'Failed to create' });
      }
    } catch {
      setMessage({ type: 'error', text: 'Failed to create collection' });
    } finally {
      setCreating(false);
    }
  };

  const activeDocs = collections.find((c) => c.name === active)?.doc_count ?? 0;

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Trigger button */}
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
      >
        <svg className="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
        <span className="max-w-[120px] truncate">{active}</span>
        <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded-full">{activeDocs}</span>
        <svg className={`w-3 h-3 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 mt-2 w-72 bg-white border border-gray-200 rounded-xl shadow-lg z-50 overflow-hidden">
          <div className="p-3 border-b border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Collections</p>
          </div>

          {/* Collection list */}
          <div className="max-h-48 overflow-y-auto">
            {collections.map((c) => (
              <button
                key={c.name}
                onClick={() => switchCollection(c.name)}
                className={`w-full flex items-center justify-between px-4 py-2.5 text-sm transition-colors hover:bg-gray-50 ${
                  c.name === active ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-700'
                }`}
              >
                <span className="flex items-center gap-2">
                  <svg className={`w-3.5 h-3.5 ${c.name === active ? 'text-blue-500' : 'text-gray-300'}`} fill={c.name === active ? 'currentColor' : 'none'} stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                  <span className="truncate">{c.name}</span>
                </span>
                <span className="text-xs text-gray-400">{c.doc_count} doc{c.doc_count !== 1 ? 's' : ''}</span>
              </button>
            ))}
          </div>

          {/* Create new */}
          <div className="border-t border-gray-100 p-3 space-y-2">
            <div className="flex gap-2">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && createCollection()}
                placeholder="New collection name..."
                className="flex-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
              />
              <button
                onClick={createCollection}
                disabled={creating || !newName.trim()}
                className="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:cursor-not-allowed"
              >
                {creating ? '...' : '+'}
              </button>
            </div>
            {message && (
              <p className={`text-xs ${message.type === 'success' ? 'text-green-600' : 'text-red-500'}`}>
                {message.text}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
