import React, { useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  MenuItem,
  Paper,
  Tab,
  Tabs,
  TextField,
  Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useApp } from '../App';
import CodeEditor from '../components/CodeEditor';
import FileDropZone from '../components/FileDropZone';
import ResultList from '../components/ResultList';
import type { SampleItem } from '../types';

/** 转换页：粘贴/单文件/批量 Tab、校验状态提示、结果清单（P0-3 / P0-6 / P1-1）。 */
export default function ConvertPage(): React.ReactElement {
  const navigate = useNavigate();
  const { profiles, currentProfileId, setCurrentProfile, lastConvert, setLastConvert } = useApp();

  const [tab, setTab] = useState(0);
  const [pasteCode, setPasteCode] = useState('');
  const [files, setFiles] = useState<SampleItem[]>([]);
  const [language, setLanguage] = useState('');
  const [detectedLang, setDetectedLang] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const [presets, setPresets] = useState<{ id: string; name: string; language: string }[]>([]);
  React.useEffect(() => {
    api.listPresets().then((ps) => setPresets(ps.map((p) => ({ id: p.id, name: p.name, language: p.language })))).catch(() => {});
  }, []);

  const profileOptions = useMemo(
    () => [
      ...profiles.map((p) => ({ id: p.id, label: `${p.name}（${p.language}）` })),
      ...presets.map((p) => ({ id: p.id, label: `[预设] ${p.name}（${p.language}）` })),
    ],
    [profiles, presets],
  );

  const detectPaste = async (code: string) => {
    setPasteCode(code);
    if (code.trim().length < 8) {
      setDetectedLang('');
      return;
    }
    try {
      const r = await api.detect(code.slice(0, 4000));
      setDetectedLang(r.manual_required ? 'unknown（请手动指定）' : r.language);
    } catch {
      setDetectedLang('');
    }
  };

  const items: SampleItem[] =
    tab === 0
      ? pasteCode.trim()
        ? [{ filename: `paste.${language === 'python' ? 'py' : language === 'java' ? 'java' : 'cpp'}`, content: pasteCode }]
        : []
      : files;

  const doConvert = async () => {
    setError('');
    setBusy(true);
    try {
      const result = await api.convert(currentProfileId, items, language || undefined);
      setLastConvert(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box className="flex flex-col gap-4">
      <Box className="flex items-center gap-3">
        <Typography variant="h5" fontWeight="bold" className="flex-1">转换代码</Typography>
        <TextField
          select
          size="small"
          label="使用规则集"
          value={currentProfileId}
          onChange={(e) => {
            const opt = profileOptions.find((o) => o.id === e.target.value);
            const lang = opt ? opt.label.match(/（(\w+)）$/)?.[1] ?? '' : '';
            setCurrentProfile(e.target.value, lang);
          }}
          className="w-72"
        >
          <MenuItem value="" disabled>请选择</MenuItem>
          {profileOptions.map((o) => (
            <MenuItem key={o.id} value={o.id}>{o.label}</MenuItem>
          ))}
        </TextField>
      </Box>

      {error && <Alert severity="error">{error}</Alert>}

      <Paper variant="outlined">
        <Tabs value={tab} onChange={(_, v: number) => setTab(v)}>
          <Tab label="粘贴代码" />
          <Tab label="单文件" />
          <Tab label="批量（目录）" />
        </Tabs>
        <Box className="p-4">
          {tab === 0 && (
            <CodeEditor
              value={pasteCode}
              onChange={detectPaste}
              language={language}
              detectedLanguage={detectedLang}
              onLanguageChange={setLanguage}
            />
          )}
          {tab === 1 && (
            <FileDropZone
              multiple={false}
              onFiles={(f) => setFiles(f.slice(0, 1))}
              hint="选择或拖拽单个代码文件"
            />
          )}
          {tab === 2 && (
            <FileDropZone
              directory
              onFiles={setFiles}
              hint="选择整个目录（webkitdirectory，纯本地读取，不上传落盘）"
            />
          )}
          {tab > 0 && files.length > 0 && (
            <Typography variant="body2" color="text.secondary" className="mt-2">
              已选择 {files.length} 个文件：{files.slice(0, 5).map((f) => f.filename).join('、')}
              {files.length > 5 ? ' …' : ''}
            </Typography>
          )}
        </Box>
      </Paper>

      <Box className="flex items-center gap-3">
        <Button
          variant="contained"
          size="large"
          disabled={!currentProfileId || items.length === 0 || busy}
          onClick={doConvert}
        >
          {busy ? '转换中…' : `转换（${items.length} 项）`}
        </Button>
        {!currentProfileId && (
          <Typography variant="caption" color="error">请先在右上角选择规则集</Typography>
        )}
        {lastConvert && (
          <Button variant="outlined" onClick={() => navigate('/diff')}>查看对照</Button>
        )}
      </Box>

      {lastConvert && (
        <ResultList results={lastConvert.results} summary={lastConvert.summary} />
      )}
    </Box>
  );
}
