import { useEffect, useState, useCallback } from 'react';

const API_URL = import.meta.env.VITE_API_URL || '';

interface Document {
  id: number;
  filename: string;
  file_type: string;
  file_size: number;
  upload_timestamp: string;
  chunk_count: number;
  collection: string;
}

export default function DocumentBrowser() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<number | null>(null);

  const fetchDocs = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/documents`);
      if (res.ok) {
        setDocs(await res.json());
      }
    } catch {
      // Backend not reachable — stay empty
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

  const handleDelete = async (doc: Document) => {
    setDeleting(doc.id);
    try {
      const res = await fetch(`${API_URL}/documents/${doc.id}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setDocs((prev) => prev.filter((d) => d.id !== doc.id));
      } else {
        const err = await res.json().catch(() => ({ detail: 'Delete failed' }));
        alert(`Failed to delete: ${err.detail}`);
      }
    } catch {
      alert('Failed to delete document');
    } finally {
      setDeleting(null);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatTime = (iso: string) => {
    return new Date(iso).toLocaleString();
  };

  const typeIcon = (type: string) => {
    switch (type) {
      case 'pdf': return '📄';
      case 'md':  return '📝';
      case 'txt': return '📃';
      default:    return '📎';
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <h2 className="font-semibold text-gray-800 flex items-center gap-2">
          <svg className="w-4 h-4 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
          </svg>
          Knowledge Base
        </h2>
        <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-full">
          {docs.length} doc{docs.length !== 1 ? 's' : ''}
        </span>
      </div>

      <div className="max-h-80 overflow-y-auto">
        {loading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Loading...</div>
        ) : docs.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">
            No documents yet. Upload files to build your knowledge base.
          </div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {docs.map((doc) => (
              <li key={doc.id} className="px-5 py-3 hover:bg-gray-50 transition-colors group">
                <div className="flex items-start gap-3">
                  <span className="text-lg mt-0.5">{typeIcon(doc.file_type)}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate">{doc.filename}</p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {formatSize(doc.file_size)} · {doc.chunk_count} chunks · {formatTime(doc.upload_timestamp)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium uppercase text-gray-400 bg-gray-100 px-2 py-0.5 rounded">
                      {doc.file_type}
                    </span>
                    <button
                      onClick={() => handleDelete(doc)}
                      disabled={deleting === doc.id}
                      className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500 disabled:opacity-50"
                      title="Delete document"
                    >
                      {deleting === doc.id ? (
                        <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                      ) : (
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
