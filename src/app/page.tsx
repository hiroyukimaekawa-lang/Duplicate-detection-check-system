'use client';

import { useState } from 'react';
import './globals.css';

export default function Home() {
  const [files, setFiles] = useState<FileList | null>(null);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [criteria, setCriteria] = useState<string[]>(['phone', 'name', 'address']);
  const [excludeChains, setExcludeChains] = useState<boolean>(false);
  const [privacyMode, setPrivacyMode] = useState<boolean>(false);
  const [processedResults, setProcessedResults] = useState<any>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(e.target.files);
    }
  };

  const toggleCriterion = (id: string) => {
    setCriteria(prev => 
      prev.includes(id) 
        ? prev.filter(c => c !== id) 
        : [...prev, id]
    );
  };

  const handleUpload = async () => {
    if (!files) return;
    if (criteria.length === 0) {
      setError('少なくとも一つの重複チェック項目を選択してください。');
      return;
    }
    setLoading(true);
    setError(null);
    setSummary(null);

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }
    formData.append('criteria', JSON.stringify(criteria));
    formData.append('exclude_chains', excludeChains.toString());
    formData.append('privacy_mode', privacyMode.toString());

    try {
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const data = await response.json();
      setSummary(data.stats || data);
      if (data.results) {
        setProcessedResults(data.results);
      }
    } catch (err: any) {
      setError(err.message || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (format: 'excel' | 'csv' = 'excel') => {
    if (!processedResults) {
      console.error('No processed results available');
      return;
    }
    try {
      const response = await fetch('/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          results: processedResults,
          format: format
        }),
      });
      if (!response.ok) throw new Error('Download failed');
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const extension = format === 'csv' ? 'zip' : 'xlsx';
      link.setAttribute('download', `restaurant_list.${extension}`);
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
        <div style={{ marginBottom: '2rem' }}>
          <h3 style={{ fontSize: '1rem', marginBottom: '1rem', color: 'hsl(var(--muted-foreground))' }}>重複チェックの基準を選択:</h3>
          <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
            <label className="checkbox-container">
              <input 
                type="checkbox" 
                checked={criteria.includes('name')} 
                onChange={() => toggleCriterion('name')}
              />
              <span className="checkmark"></span>
              <span style={{ fontSize: '1rem' }}>店名</span>
            </label>
            <label className="checkbox-container">
              <input 
                type="checkbox" 
                checked={criteria.includes('phone')} 
                onChange={() => toggleCriterion('phone')}
              />
              <span className="checkmark"></span>
              <span style={{ fontSize: '1rem' }}>電話番号</span>
            </label>
            <label className="checkbox-container">
              <input 
                type="checkbox" 
                checked={criteria.includes('address')} 
                onChange={() => toggleCriterion('address')}
              />
              <span className="checkmark"></span>
              <span style={{ fontSize: '1rem' }}>住所</span>
            </label>
          </div>
          <p style={{ fontSize: '0.8rem', color: 'hsl(var(--muted-foreground))', marginTop: '0.5rem' }}>
            ※「店名」と「住所」の両方を選択すると、より精度の高い名寄せが行われます。
          </p>
          <div style={{ marginTop: '1.5rem', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '1.5rem' }}>
            <h3 style={{ fontSize: '1rem', marginBottom: '1rem', color: 'hsl(var(--muted-foreground))' }}>その他のオプション:</h3>
            <label className="checkbox-container">
              <input 
                type="checkbox" 
                checked={excludeChains} 
                onChange={(e) => setExcludeChains(e.target.checked)}
              />
              <span className="checkmark"></span>
              <span style={{ fontSize: '1rem', color: '#ffaa00' }}>チェーン店（「〜店」など）を排除する</span>
            </label>
            <label className="checkbox-container" style={{ marginTop: '0.5rem' }}>
              <input 
                type="checkbox" 
                checked={privacyMode} 
                onChange={(e) => setPrivacyMode(e.target.checked)}
              />
              <span className="checkmark"></span>
              <span style={{ fontSize: '1rem', color: '#00ccff' }}>個人情報保護モード（電話番号等をマスクする）</span>
            </label>
          </div>
        </div>

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
          onDragOver={(e: React.DragEvent<HTMLDivElement>) => e.preventDefault()}
          onDrop={(e: React.DragEvent<HTMLDivElement>) => {
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
            <div className="card glass">
              <p style={{ color: 'hsl(var(--muted-foreground))', fontSize: '0.9rem' }}>電話番号不備</p>
              <h3 style={{ fontSize: '2.5rem', color: '#ffaa00' }}>{summary.invalid_phone_count.toLocaleString()}</h3>
            </div>
            {summary.excluded_chains_count > 0 && (
              <div className="card glass">
                <p style={{ color: 'hsl(var(--muted-foreground))', fontSize: '0.9rem' }}>排除チェーン店</p>
                <h3 style={{ fontSize: '2.5rem', color: '#ffaa00' }}>{summary.excluded_chains_count.toLocaleString()}</h3>
              </div>
            )}
            {summary.mall_excluded > 0 && (
              <div className="card glass">
                <p style={{ color: 'hsl(var(--muted-foreground))', fontSize: '0.9rem' }}>商業施設除外</p>
                <h3 style={{ fontSize: '2.5rem', color: '#ffaa00' }}>{summary.mall_excluded.toLocaleString()}</h3>
              </div>
            )}
          </div>

          <div className="card glass" style={{ marginBottom: '2rem' }}>
            <h2 style={{ marginBottom: '1.5rem' }}>市区町村別の件数</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '1rem' }}>
              {Object.entries(summary.municipality_counts).sort(([, a]: any, [, b]: any) => b - a).map(([mun, count]) => (
                <div key={mun} style={{ padding: '0.75rem', backgroundColor: 'rgba(255, 255, 255, 0.05)', borderRadius: 'var(--radius)', display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontWeight: '600' }}>{mun}</span>
                  <span style={{ color: 'hsl(var(--primary))' }}>{String(count)} 件</span>
                </div>
              ))}
            </div>
          </div>

          <div className="card glass" style={{ marginBottom: '2rem' }}>
            <h2 style={{ marginBottom: '1.5rem' }}>重複排除サマリー</h2>
            <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
              {Object.entries(summary.reasons).map(([reason, count]) => (
                <div key={reason} style={{ flex: '1', minWidth: '150px' }}>
                  <p style={{ fontSize: '0.8rem', color: 'hsl(var(--muted-foreground))', textTransform: 'uppercase' }}>{reason.replace(/_/g, ' ')}</p>
                  <p style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{String(count)}</p>
                </div>
              ))}
              <div style={{ flex: '1', minWidth: '150px' }}>
                <p style={{ fontSize: '0.8rem', color: 'hsl(var(--muted-foreground))', textTransform: 'uppercase' }}>重複率</p>
                <p style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{summary.dup_rate}%</p>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '1.5rem', justifyContent: 'center', flexWrap: 'wrap', marginBottom: '3rem' }}>
            <button className="btn btn-secondary" onClick={() => handleDownload('excel')} style={{ padding: '1rem 2.5rem' }}>
              統合リスト (Excel)
            </button>
            <button className="btn btn-primary" onClick={() => handleDownload('csv')} style={{ padding: '1rem 2.5rem' }}>
              統合リスト (CSV)
            </button>
          </div>

          {processedResults.review_samples && processedResults.review_samples.length > 0 && (
            <div className="card glass animate-fade-in" style={{ border: '1px solid hsl(var(--primary))' }}>
              <h2 style={{ marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.5rem' }}>🧠</span> AI判定の確認（フィードバック）
              </h2>
              <p style={{ color: 'hsl(var(--muted-foreground))', marginBottom: '2rem', fontSize: '0.9rem' }}>
                システムが重複と判断したペアです。正誤を教えることで、AIの精度がさらに向上します。
              </p>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
                {processedResults.review_samples.map((sample: any, idx: number) => (
                  <div key={idx} style={{ padding: '1.5rem', backgroundColor: 'rgba(255, 255, 255, 0.03)', borderRadius: 'var(--radius)', border: '1px solid rgba(255,255,255,0.05)' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>
                      <div>
                        <p style={{ fontSize: '0.7rem', color: 'hsl(var(--primary))', fontWeight: 'bold' }}>レコード A (元データ)</p>
                        <p style={{ fontWeight: 'bold', fontSize: '1.1rem' }}>{sample.row_a.name}</p>
                        <p style={{ fontSize: '0.8rem', opacity: 0.8 }}>{sample.row_a.address}</p>
                        <p style={{ fontSize: '0.8rem', opacity: 0.6 }}>{sample.row_a.phone}</p>
                      </div>
                      <div>
                        <p style={{ fontSize: '0.7rem', color: 'hsl(var(--destructive))', fontWeight: 'bold' }}>レコード B (重複判定)</p>
                        <p style={{ fontWeight: 'bold', fontSize: '1.1rem' }}>{sample.row_b.name}</p>
                        <p style={{ fontSize: '0.8rem', opacity: 0.8 }}>{sample.row_b.address}</p>
                        <p style={{ fontSize: '0.8rem', opacity: 0.6 }}>{sample.row_b.phone}</p>
                      </div>
                    </div>
                    
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.8rem', padding: '0.2rem 0.6rem', backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: '10px' }}>
                        判定理由: {sample.reason}
                      </span>
                      <div style={{ display: 'flex', gap: '1rem' }}>
                        <button 
                          className="btn" 
                          style={{ backgroundColor: 'rgba(0, 255, 136, 0.1)', color: '#00ff88', border: '1px solid #00ff88', padding: '0.5rem 1rem' }}
                          onClick={async (e) => {
                            const btn = e.currentTarget;
                            btn.disabled = true;
                            btn.innerText = '送信中...';
                            await fetch('/api/feedback', {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({ row_a: sample.row_a, row_b: sample.row_b, is_duplicate: true })
                            });
                            btn.innerText = '✅ 正解';
                            btn.style.backgroundColor = '#00ff88';
                            btn.style.color = '#000';
                          }}
                        >
                          正しい (重複)
                        </button>
                        <button 
                          className="btn" 
                          style={{ backgroundColor: 'rgba(255, 68, 68, 0.1)', color: '#ff4444', border: '1px solid #ff4444', padding: '0.5rem 1rem' }}
                          onClick={async (e) => {
                            const btn = e.currentTarget;
                            btn.disabled = true;
                            btn.innerText = '送信中...';
                            await fetch('/api/feedback', {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({ row_a: sample.row_a, row_b: sample.row_b, is_duplicate: false })
                            });
                            btn.innerText = '❌ 誤判定';
                            btn.style.backgroundColor = '#ff4444';
                            btn.style.color = '#fff';
                          }}
                        >
                          間違い (別店舗)
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <footer style={{ marginTop: '5rem', textAlign: 'center', color: 'hsl(var(--muted-foreground))', fontSize: '0.8rem' }}>
        &copy; 2026 重複検出チェックシステム。Next.js & FastAPIで構築されています。
      </footer>
    </main>
  );
}
