import { useState, useRef, useCallback } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8500';

interface Props {
  onIngestComplete: () => void;
}

export default function UploadSection({ onIngestComplete }: Props) {
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    for (const file of Array.from(files)) {
      setStatus('uploading');
      setMessage(`Uploading ${file.name}...`);

      const formData = new FormData();
      formData.append('file', file);

      try {
        const res = await fetch(`${API_URL}/ingest`, {
          method: 'POST',
          body: formData,
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
          throw new Error(err.detail || 'Upload failed');
        }

        const data = await res.json();
        setStatus('success');
        setMessage(
          `✅ ${file.name} ingested — ${data.chunk_count} chunks, ${(data.file_size / 1024).toFixed(1)} KB`,
        );
        onIngestComplete();
      } catch (e: unknown) {
        setStatus('error');
        setMessage(`❌ ${file.name}: ${e instanceof Error ? e.message : 'Unknown error'}`);
      }
    }
  }, [onIngestComplete]);

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  };

  const onDragLeave = () => setDragging(false);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="font-semibold text-gray-800 flex items-center gap-2">
          <svg className="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
          </svg>
          Upload Documents
        </h2>
      </div>

      <div className="p-5">
        <div
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`
            border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
            ${dragging ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-300 hover:bg-gray-50'}
          `}
        >
          <svg className="w-10 h-10 mx-auto text-gray-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <p className="text-sm text-gray-600">
            <span className="font-medium text-blue-500">Click to upload</span> or drag &amp; drop
          </p>
          <p className="text-xs text-gray-400 mt-1">.txt, .md, .pdf</p>
        </div>

        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".txt,.md,.pdf"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />

        {message && (
          <div className={`mt-4 text-sm p-3 rounded-lg ${
            status === 'success' ? 'bg-green-50 text-green-700' :
            status === 'error' ? 'bg-red-50 text-red-700' :
            'bg-blue-50 text-blue-700'
          }`}>
            {message}
          </div>
        )}
      </div>
    </div>
  );
}
