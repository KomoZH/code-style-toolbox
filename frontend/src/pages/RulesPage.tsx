import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Paper,
  TextField,
  Typography,
} from '@mui/material';
import { useSearchParams } from 'react-router-dom';
import { api, ApiError } from '../api/client';
import { useApp } from '../App';
import RuleForm, { FieldSpec } from '../components/RuleForm';
import type { RuleMeta, StyleProfile } from '../types';

const NAMING_OPTIONS = ['snake_case', 'camelCase', 'PascalCase', 'UPPER_SNAKE'].map((v) => ({
  value: v,
  label: v,
}));

/** 规则分类与字段描述（与后端 Rules schema 对齐）。 */
const GROUPS: { key: string; label: string; fields: FieldSpec[] }[] = [
  {
    key: 'naming',
    label: '命名约定',
    fields: [
      { key: 'variables', label: '变量', type: 'select', options: NAMING_OPTIONS },
      { key: 'functions', label: '函数', type: 'select', options: NAMING_OPTIONS },
      { key: 'classes', label: '类', type: 'select', options: NAMING_OPTIONS },
      { key: 'constants', label: '常量', type: 'select', options: NAMING_OPTIONS },
      { key: 'private_prefix', label: '私有前缀', type: 'text' },
      { key: 'member_prefix', label: 'C++ 成员前缀', type: 'text' },
    ],
  },
  {
    key: 'indent',
    label: '缩进',
    fields: [
      {
        key: 'style', label: '缩进方式', type: 'select',
        options: [
          { value: 'space', label: '空格' },
          { value: 'tab', label: 'Tab' },
        ],
      },
      {
        key: 'size', label: '缩进宽度', type: 'select',
        options: [
          { value: 2, label: '2' },
          { value: 4, label: '4' },
          { value: 8, label: '8' },
        ],
      },
    ],
  },
  {
    key: 'brace_style',
    label: '括号风格（C++/Java）',
    fields: [
      {
        key: 'style', label: '大括号风格', type: 'select',
        options: [
          { value: 'k_and_r', label: 'K&R（同行）' },
          { value: 'allman', label: 'Allman（换行）' },
        ],
      },
      { key: 'space_before_paren', label: 'if 后空格（if ( vs if()）', type: 'switch' },
    ],
  },
  {
    key: 'spacing',
    label: '空白',
    fields: [
      { key: 'space_around_operators', label: '运算符两侧空格', type: 'switch' },
      { key: 'space_after_comma', label: '逗号后空格', type: 'switch' },
      { key: 'trim_trailing_whitespace', label: '清除行尾空白', type: 'switch' },
    ],
  },
  {
    key: 'blank_lines',
    label: '空行排版',
    fields: [
      { key: 'max_consecutive', label: '最大连续空行', type: 'number', min: 0, max: 4 },
      { key: 'between_functions', label: '函数/类之间空行', type: 'number', min: 0, max: 4 },
      { key: 'after_imports', label: 'import 块后空行', type: 'number', min: 0, max: 4 },
    ],
  },
  {
    key: 'comments',
    label: '注释',
    fields: [
      { key: 'inline_min_spaces', label: '行尾注释前最少空格', type: 'number', min: 1, max: 8 },
      {
        key: 'docstring_format', label: 'docstring 风格（仅识别展示）', type: 'select',
        options: [
          { value: 'google', label: 'google' },
          { value: 'numpy', label: 'numpy' },
          { value: 'sphinx', label: 'sphinx' },
          { value: 'none', label: '无' },
        ],
      },
    ],
  },
  {
    key: 'declarations',
    label: '声明（展示为主）',
    fields: [
      {
        key: 'cpp_const_style', label: 'C++ const 位置', type: 'select',
        options: [
          { value: 'east', label: 'east（T const）' },
          { value: 'west', label: 'west（const T）' },
        ],
      },
      { key: 'python_type_hints', label: 'Python 类型提示（仅展示）', type: 'switch' },
    ],
  },
];

/** 规则页：分类树 + 表单编辑 + 低置信度高亮 + 导入导出切换（P0-2 / P1-2 / P1-4）。 */
export default function RulesPage(): React.ReactElement {
  const { profiles, currentProfileId, setCurrentProfile, refreshProfiles } = useApp();
  const [searchParams] = useSearchParams();

  const [presets, setPresets] = useState<StyleProfile[]>([]);
  const [selectedId, setSelectedId] = useState(searchParams.get('pid') ?? currentProfileId);
  const [profile, setProfile] = useState<StyleProfile | null>(null);
  const [group, setGroup] = useState('naming');
  const [message, setMessage] = useState<{ kind: 'success' | 'error'; text: string } | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importText, setImportText] = useState('');

  useEffect(() => {
    api.listPresets().then(setPresets).catch(() => setPresets([]));
  }, []);

  const loadProfile = useCallback(async (pid: string) => {
    if (!pid) return;
    try {
      const p = await api.getProfile(pid);
      setProfile(p);
      setCurrentProfile(p.id, p.language);
    } catch (e) {
      setMessage({ kind: 'error', text: e instanceof Error ? e.message : String(e) });
    }
  }, [setCurrentProfile]);

  useEffect(() => {
    loadProfile(selectedId);
  }, [selectedId, loadProfile]);

  const options = useMemo(
    () => [
      ...profiles.map((p) => ({ id: p.id, label: `${p.name}（${p.language}）` })),
      ...presets.map((p) => ({ id: p.id, label: `[预设] ${p.name}` })),
    ],
    [profiles, presets],
  );

  const groupSpec = GROUPS.find((g) => g.key === group) ?? GROUPS[0];
  const groupMeta = (profile?.meta?.[group] ?? {}) as Record<string, RuleMeta>;
  const sampleLines = profile?.meta?._sample_lines as { total: number; low_evidence: boolean } | undefined;
  const isPreset = profile?.source === 'preset';

  const updateField = (key: string, value: unknown) => {
    if (!profile) return;
    setProfile({
      ...profile,
      rules: {
        ...profile.rules,
        [group]: { ...(profile.rules as never)[group], [key]: value },
      },
    });
  };

  const save = async () => {
    if (!profile) return;
    try {
      const saved = await api.saveProfile(profile);
      await refreshProfiles();
      setProfile(saved);
      setSelectedId(saved.id);
      setMessage({
        kind: 'success',
        text: isPreset ? '预设为只读，已另存为新规则集。' : '已保存，后续转换即刻生效。',
      });
    } catch (e) {
      setMessage({ kind: 'error', text: e instanceof Error ? e.message : String(e) });
    }
  };

  const doImport = async () => {
    try {
      const p = await api.importProfile(importText);
      await refreshProfiles();
      setImportOpen(false);
      setImportText('');
      setSelectedId(p.id);
      setMessage({ kind: 'success', text: `已导入规则集「${p.name}」。` });
    } catch (e) {
      setMessage({
        kind: 'error',
        text: e instanceof ApiError ? e.message : String(e),
      });
    }
  };

  return (
    <Box className="flex flex-col gap-4">
      <Box className="flex items-center gap-3">
        <Typography variant="h5" fontWeight="bold" className="flex-1">风格规则</Typography>
        <TextField
          select
          size="small"
          label="规则集"
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          className="w-72"
        >
          <MenuItem value="" disabled>请选择</MenuItem>
          {options.map((o) => (
            <MenuItem key={o.id} value={o.id}>{o.label}</MenuItem>
          ))}
        </TextField>
        <Button variant="outlined" onClick={() => setImportOpen(true)}>导入</Button>
        <Button
          variant="outlined"
          disabled={!profile}
          onClick={() => profile && window.open(api.exportUrl(profile.id), '_blank')}
        >
          导出
        </Button>
        <Button variant="contained" disabled={!profile} onClick={save}>
          {isPreset ? '另存为' : '保存'}
        </Button>
      </Box>

      {message && <Alert severity={message.kind} onClose={() => setMessage(null)}>{message.text}</Alert>}
      {sampleLines?.low_evidence && (
        <Alert severity="warning">
          提取样例仅 {sampleLines.total} 行（&lt;200），规则置信度普遍偏低，请人工确认后再用于转换。
        </Alert>
      )}

      {profile ? (
        <Box className="grid grid-cols-4 gap-4">
          <Paper variant="outlined" className="col-span-1">
            <List dense>
              {GROUPS.map((g) => (
                <ListItemButton
                  key={g.key}
                  selected={g.key === group}
                  onClick={() => setGroup(g.key)}
                >
                  <ListItemText primary={g.label} />
                </ListItemButton>
              ))}
            </List>
          </Paper>
          <Paper variant="outlined" className="col-span-3 p-4">
            <Typography variant="subtitle1" fontWeight="bold" className="mb-3">
              {groupSpec.label}
              <Typography component="span" variant="caption" color="text.secondary" className="ml-2">
                （{profile.language} · {profile.source}）
              </Typography>
            </Typography>
            <RuleForm
              fields={groupSpec.fields}
              values={(profile.rules as never)[groupSpec.key]}
              meta={groupMeta}
              onChange={updateField}
            />
          </Paper>
        </Box>
      ) : (
        <Alert severity="info">请选择规则集；也可先到「提取」页从样例生成，或使用内置预设。</Alert>
      )}

      <Dialog open={importOpen} onClose={() => setImportOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>导入规则集（YAML）</DialogTitle>
        <DialogContent>
          <TextField
            multiline
            fullWidth
            minRows={12}
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            placeholder="粘贴 style_profile YAML 文本…"
            InputProps={{ className: 'mono text-sm' }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setImportOpen(false)}>取消</Button>
          <Button variant="contained" disabled={!importText.trim()} onClick={doImport}>导入</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
