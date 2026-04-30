'use client';

import { useState } from 'react';
import './globals.css';

export default function Home() {
  const [files, setFiles] = useState<FileList | null>(null);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(e.target.files);
    }
  };

  const handleUpload = async () => {
    if (!files) return;
    setLoading(true);
    setError(null);
    setSummary(null);

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }

    try {
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Upload failed');
      }

      const data = await response.json();
      setSummary(data);
    } catch (err: any) {
      setError(err.message || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (type: 'cleaned' | 'duplicates') => {
    try {
      const response = await fetch(`/api/download/${type}`);
      const data = await response.json();
      
      const blob = new Blob([data.content], { type: 'text/csv;charset=utf-8;' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', data.filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error('Download failed', err);
    }
  };

  return (
    <main className="container animate-fade-in">
      <header style={{ marginBottom: '3rem', textAlign: 'center' }}>
        <h1 className="gradient-text" style={{ fontSize: '3.5rem', marginBottom: '0.5rem' }}>
          Deduplicator Pro
        </h1>
        <p style={{ color: 'hsl(var(--muted-foreground))' }}>
          ファジーロジックを用いたスマートなレストランデータ重複排除
        </p>
      </header>

      <div className="card glass" style={{ marginBottom: '2rem' }}>
        <h2 style={{ marginBottom: '1.5rem' }}>CSVデータをアップロード</h2>
        <div 
          style={{ 
            border: '2px dashed hsl(var(--border))', 
            borderRadius: 'var(--radius)', 
            padding: '3rem', 
            textAlign: 'center',
            cursor: 'pointer',
            backgroundColor: 'rgba(255, 255, 255, 0.02)',
            transition: 'border-color 0.2s'
          }}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            if (e.dataTransfer.files) setFiles(e.dataTransfer.files);
          }}
        >
          <input 
            type="file" 
            multiple 
            accept=".csv" 
            onChange={handleFileChange} 
            id="fileInput"
            style={{ display: 'none' }}
          />
          <label htmlFor="fileInput" style={{ cursor: 'pointer' }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📁</div>
            <p style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>
              {files ? `${files.length} 個のファイルを選択中` : 'CSVファイルをここにドラッグ＆ドロップするか、クリックして参照してください。'}
            </p>
            <p style={{ fontSize: '0.9rem', color: 'hsl(var(--muted-foreground))' }}>
              複数のファイル形式（Google、食べログ、ホットペッパーなど）に対応しています。
            </p>
          </label>
        </div>

        {files && (
          <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'center' }}>
            <button 
              className="btn btn-primary" 
              onClick={handleUpload} 
              disabled={loading}
              style={{ padding: '1rem 3rem' }}
            >
              {loading ? '処理中...' : '重複排除を実行'}
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="card" style={{ backgroundColor: 'rgba(255, 0, 0, 0.1)', borderColor: 'hsl(var(--destructive))', marginBottom: '2rem' }}>
          <p style={{ color: 'hsl(var(--destructive))' }}>Error: {error}</p>
        </div>
      )}

      {summary && (
        <div className="animate-fade-in">
          <div className="grid" style={{ marginBottom: '2rem' }}>
            <div className="card glass">
              <p style={{ color: 'hsl(var(--muted-foreground))', fontSize: '0.9rem' }}>入力件数</p>
              <h3 style={{ fontSize: '2.5rem' }}>{summary.input_count.toLocaleString()}</h3>
            </div>
            <div className="card glass">
              <p style={{ color: 'hsl(var(--muted-foreground))', fontSize: '0.9rem' }}>重複件数</p>
              <h3 style={{ fontSize: '2.5rem', color: 'hsl(var(--destructive))' }}>{summary.dup_count.toLocaleString()}</h3>
            </div>
            <div className="card glass">
              <p style={{ color: 'hsl(var(--muted-foreground))', fontSize: '0.9rem' }}>クリーンな出力</p>
              <h3 style={{ fontSize: '2.5rem', color: '#00ff88' }}>{summary.output_count.toLocaleString()}</h3>
            </div>
          </div>

          <div className="card glass" style={{ marginBottom: '2rem' }}>
            <h2 style={{ marginBottom: '1.5rem' }}>重複排除サマリー</h2>
            <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
              {Object.entries(summary.reasons).map(([reason, count]: [any, any]) => (
                <div key={reason} style={{ flex: '1', minWidth: '150px' }}>
                  <p style={{ fontSize: '0.8rem', color: 'hsl(var(--muted-foreground))', textTransform: 'uppercase' }}>{reason.replace(/_/g, ' ')}</p>
                  <p style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{count}</p>
                </div>
              ))}
              <div style={{ flex: '1', minWidth: '150px' }}>
                <p style={{ fontSize: '0.8rem', color: 'hsl(var(--muted-foreground))', textTransform: 'uppercase' }}>重複率</p>
                <p style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{summary.dup_rate}%</p>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
            <button className="btn btn-secondary" onClick={() => handleDownload('cleaned')}>
              クリーンなCSVをダウンロード
            </button>
            <button className="btn btn-secondary" onClick={() => handleDownload('duplicates')}>
              重複ログをダウンロード
            </button>
          </div>
        </div>
      )}

      <footer style={{ marginTop: '5rem', textAlign: 'center', color: 'hsl(var(--muted-foreground))', fontSize: '0.8rem' }}>
        &copy; 2026 重複検出チェックシステム。Next.js & FastAPIで構築されています。
      </footer>
    </main>
  );
}
