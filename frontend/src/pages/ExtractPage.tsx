import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  MenuItem,
  Paper,
  TextField,
  Typography,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { useApp } from '../App';
import FileDropZone from '../components/FileDropZone';
import type { SampleItem } from '../types';

/** 提取页：上传/拖拽样例、语言识别徽标、触发提取（P0-1 / P0-5）。 */
export default function ExtractPage(): React.ReactElement {
  const navigate = useNavigate();
  const { demoSamples, setDemoSamples, setCurrentProfile, refreshProfiles } = useApp();

  const [samples, setSamples] = useState<SampleItem[]>([]);
  const [profileName, setProfileName] = useState('');
  const [language, setLanguage] = useState('');
  const [detected, setDetected] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  // 一键演示带入的样例
  useEffect(() => {
    if (demoSamples.length > 0) {
      setSamples(demoSamples);
      setProfileName('demo_style');
      setDemoSamples([]);
    }
  }, [demoSamples, setDemoSamples]);

  // 逐样本语言识别徽标
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result: Record<string, string> = {};
      for (const s of samples) {
        try {
          const r = await api.detect(s.content.slice(0, 4000), s.filename);
          result[s.filename] = r.language;
        } catch {
          result[s.filename] = 'unknown';
        }
      }
      if (!cancelled) setDetected(result);
    })();
    return () => {
      cancelled = true;
    };
  }, [samples]);

  const doExtract = async () => {
    setError('');
    setBusy(true);
    try {
      const profile = await api.extract(
        samples,
        profileName || 'untitled',
        language || undefined,
      );
      await refreshProfiles();
      setCurrentProfile(profile.id, profile.language);
      navigate(`/rules?pid=${profile.id}`);
    } catch (e) {
      if (e instanceof ApiError && e.code === 1001) {
        setError('语言识别失败：请在下方手动指定语言后重试。');
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box className="flex flex-col gap-4">
      <Typography variant="h5" fontWeight="bold">提取风格规则</Typography>

      {error && <Alert severity="warning">{error}</Alert>}

      <FileDropZone onFiles={(files) => setSamples((prev) => [...prev, ...files])} />

      {samples.length > 0 && (
        <Paper variant="outlined" className="p-3">
          <Typography variant="subtitle2" className="mb-2">
            已选择 {samples.length} 个样例
          </Typography>
          <Box className="flex flex-wrap gap-2">
            {samples.map((s) => (
              <Chip
                key={s.filename}
                label={`${s.filename} · ${detected[s.filename] ?? '…'}`}
                color={detected[s.filename] && detected[s.filename] !== 'unknown' ? 'primary' : 'default'}
                variant="outlined"
                onDelete={() =>
                  setSamples((prev) => prev.filter((p) => p.filename !== s.filename))
                }
              />
            ))}
          </Box>
        </Paper>
      )}

      <Box className="flex items-center gap-3">
        <TextField
          size="small"
          label="规则集名称"
          value={profileName}
          onChange={(e) => setProfileName(e.target.value)}
          className="w-64"
        />
        <TextField
          select
          size="small"
          label="语言（默认识别）"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className="w-48"
        >
          <MenuItem value="">自动识别</MenuItem>
          <MenuItem value="python">python</MenuItem>
          <MenuItem value="cpp">cpp</MenuItem>
          <MenuItem value="java">java</MenuItem>
        </TextField>
        <Button
          variant="contained"
          disabled={samples.length === 0 || busy}
          onClick={doExtract}
        >
          开始提取
        </Button>
      </Box>
    </Box>
  );
}
