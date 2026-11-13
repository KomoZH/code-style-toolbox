import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  MenuItem,
  Paper,
  TextField,
  Typography,
} from '@mui/material';
import JSZip from 'jszip';
import { api } from '../api/client';
import { useApp } from '../App';
import DiffView from '../components/DiffView';
import ResultList from '../components/ResultList';
import type { ConvertResult, HistorySummary } from '../types';

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** 对照页：并排 diff、警示项、采纳导出（P0-4 / P0-6 / P2-1）。 */
export default function DiffPage(): React.ReactElement {
  const { lastConvert, currentLanguage } = useApp();
  const [selected, setSelected] = useState<ConvertResult | null>(null);
  const [history, setHistory] = useState<HistorySummary[]>([]);
  const [message, setMessage] = useState('');

  const results = useMemo(() => lastConvert?.results ?? [], [lastConvert]);

  useEffect(() => {
    if (results.length > 0 && !selected) {
      setSelected(results.find((r) => r.status === 'converted') ?? results[0]);
    }
  }, [results, selected]);

  useEffect(() => {
    api.listHistory().then(setHistory).catch(() => setHistory([]));
  }, [lastConvert]);

  const warnings = results.filter((r) => r.status !== 'converted');

  const exportAll = async () => {
    const converted = results.filter((r) => r.status === 'converted');
    if (converted.length === 0) return;
    if (converted.length === 1) {
      downloadBlob(new Blob([converted[0].converted]), converted[0].filename.replace(/^.*[\\/]/, ''));
      return;
    }
    const zip = new JSZip();
    for (const r of converted) {
      zip.file(r.filename, r.converted);
    }
    downloadBlob(await zip.generateAsync({ type: 'blob' }), 'converted.zip');
  };

  const restore = async (hid: string) => {
    try {
      const data = await api.restoreHistory(hid);
      if (data.items.length === 0) {
        setMessage('该历史无已转换条目可还原。');
        return;
      }
      const zip = new JSZip();
      for (const item of data.items) {
        zip.file(item.filename, item.content);
      }
      downloadBlob(await zip.generateAsync({ type: 'blob' }), 'restored_originals.zip');
      setMessage(`已还原 ${data.restored.length} 个文件的原始内容（下载 zip）。`);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    }
  };

  if (!lastConvert) {
    return (
      <Alert severity="info">暂无转换结果，请先到「转换」页执行一次转换。</Alert>
    );
  }

  return (
    <Box className="flex flex-col gap-4">
      <Box className="flex items-center gap-3">
        <Typography variant="h5" fontWeight="bold" className="flex-1">差异对照</Typography>
        <TextField
          select
          size="small"
          label="文件"
          value={selected?.filename ?? ''}
          onChange={(e) => setSelected(results.find((r) => r.filename === e.target.value) ?? null)}
          className="w-80"
        >
          {results.map((r) => (
            <MenuItem key={r.filename} value={r.filename}>
              {r.filename}（{r.status}）
            </MenuItem>
          ))}
        </TextField>
        <Button
          variant="contained"
          disabled={results.every((r) => r.status !== 'converted')}
          onClick={exportAll}
        >
          采纳导出
        </Button>
      </Box>

      {message && <Alert severity="info" onClose={() => setMessage('')}>{message}</Alert>}

      {warnings.length > 0 && (
        <Alert severity="warning">
          {warnings.length} 个条目无法安全转换，已保留原始代码：
          {warnings.map((w) => `${w.filename}（${w.reason}）`).join('；')}
        </Alert>
      )}

      <ResultList
        results={results}
        summary={lastConvert.summary}
        onSelect={setSelected}
        selectedFilename={selected?.filename}
      />

      {selected && selected.status === 'converted' && (
        <DiffView diff={selected.diff} language={currentLanguage || 'python'} />
      )}
      {selected && selected.status !== 'converted' && (
        <Paper variant="outlined" className="p-3">
          <Typography color="text.secondary">
            {selected.filename}：{selected.reason}
          </Typography>
        </Paper>
      )}

      {history.length > 0 && (
        <Paper variant="outlined" className="p-3">
          <Typography variant="subtitle2" className="mb-2">转换历史（可还原原始代码）</Typography>
          <Box className="flex flex-col gap-1">
            {history.slice(0, 10).map((h) => (
              <Box key={h.id} className="flex items-center gap-2">
                <Typography variant="caption" className="mono flex-1">
                  {h.time} · {h.profile_name} · {h.files.length} 个文件
                </Typography>
                <Button size="small" onClick={() => restore(h.id)}>还原</Button>
              </Box>
            ))}
          </Box>
        </Paper>
      )}
    </Box>
  );
}
