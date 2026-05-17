import React, { useEffect } from 'react';
import { usePepperStore } from '../hooks/usePepperState';

function SearchResultCard({ result, onDismiss }) {
  useEffect(() => {
    const remaining = result.dismissAt - Date.now();
    if (remaining <= 0) { onDismiss(); return; }
    const timer = setTimeout(onDismiss, remaining);
    return () => clearTimeout(timer);
  }, [result.dismissAt, onDismiss]);

  return (
    <div style={{
      width: '320px',
      background: '#2c2c2e',
      border: '1px solid #3a3a3c',
      borderRadius: '10px',
      overflow: 'hidden',
      boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
      fontFamily: "-apple-system, 'Segoe UI', Roboto, sans-serif",
      animation: 'slideInRight 0.3s ease-out',
    }}>
      {/* Header */}
      <div style={{
        padding: '8px 12px',
        borderBottom: '1px solid #3a3a3c',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <span style={{ fontSize: '11px', color: '#999' }}>
          Search: "{result.query}"
        </span>
        <span
          onClick={onDismiss}
          style={{ cursor: 'pointer', color: '#666', fontSize: '12px' }}
        >✕</span>
      </div>

      {/* Results */}
      <div style={{ padding: '10px 12px' }}>
        {(result.results || []).slice(0, 1).map((r, i) => (
          <div key={i}>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#e5e5e5', marginBottom: '4px' }}>
              {r.title}
            </div>
            <div style={{ fontSize: '12px', color: '#999', lineHeight: '1.4', marginBottom: '4px' }}>
              {r.snippet}
            </div>
            <div style={{ fontSize: '10px', color: '#666' }}>
              {r.url}
            </div>
          </div>
        ))}
      </div>

      {/* Auto-dismiss progress bar */}
      <div style={{ height: '2px', background: '#3a3a3c' }}>
        <div style={{
          height: '100%',
          background: '#8aba8a',
          width: '100%',
          animation: 'shrinkWidth 8s linear forwards',
        }} />
      </div>
    </div>
  );
}

export default function SearchResultPopup() {
  const searchResults = usePepperStore((s) => s.searchResults);
  const dismissSearchResult = usePepperStore((s) => s.dismissSearchResult);

  if (searchResults.length === 0) return null;

  return (
    <div style={{
      position: 'fixed',
      top: '16px',
      right: '400px',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      zIndex: 200,
    }}>
      {searchResults.map((result) => (
        <SearchResultCard
          key={result.id}
          result={result}
          onDismiss={() => dismissSearchResult(result.id)}
        />
      ))}
    </div>
  );
}
