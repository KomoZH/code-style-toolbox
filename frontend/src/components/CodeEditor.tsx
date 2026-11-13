import React from 'react';
import { Box, Chip, MenuItem, Paper, TextField, Typography } from '@mui/material';
import { Highlight, themes } from 'prism-react-renderer';

interface Props {
  value: string;
  onChange?: (v: string) => void;
  language?: string;
  detectedLanguage?: string;
  onLanguageChange?: (lang: string) => void;
  readOnly?: boolean;
  minRows?: number;
}

const PRISM_LANG: Record<string, string> = {
  python: 'python',
  cpp: 'cpp',
  java: 'java',
};

/** 代码粘贴域：编辑 + prism 高亮预览 + 语言徽标 + 手动指定语言。 */
export default function CodeEditor({
  value,
  onChange,
  language = '',
  detectedLanguage = '',
  onLanguageChange,
  readOnly = false,
  minRows = 14,
}: Props): React.ReactElement {
  const prismLang = PRISM_LANG[language] ?? 'plain';

  return (
    <Box className="flex flex-col gap-2">
      <Box className="flex items-center gap-2">
        {detectedLanguage && (
          <Chip
            size="small"
            color="primary"
            variant="outlined"
            label={`识别：${detectedLanguage}`}
          />
        )}
        {onLanguageChange && (
          <TextField
            select
            size="small"
            label="手动指定语言"
            value={language}
            onChange={(e) => onLanguageChange(e.target.value)}
            className="w-44"
          >
            <MenuItem value="">自动识别</MenuItem>
            <MenuItem value="python">python</MenuItem>
            <MenuItem value="cpp">cpp</MenuItem>
            <MenuItem value="java">java</MenuItem>
          </TextField>
        )}
      </Box>

      {readOnly ? (
        <Paper variant="outlined" className="max-h-[480px] overflow-auto p-3">
          <Highlight theme={themes.vsLight} code={value} language={prismLang}>
            {({ tokens, getLineProps, getTokenProps }) => (
              <pre className="mono text-sm">
                {tokens.map((line, i) => (
                  <div key={i} {...getLineProps({ line })}>
                    {line.map((token, key) => (
                      <span key={key} {...getTokenProps({ token })} />
                    ))}
                  </div>
                ))}
              </pre>
            )}
          </Highlight>
        </Paper>
      ) : (
        <TextField
          multiline
          fullWidth
          minRows={minRows}
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          placeholder="在此粘贴代码…"
          InputProps={{ className: 'mono text-sm' }}
          variant="outlined"
        />
      )}
      {!readOnly && value && (
        <Typography variant="caption" color="text.secondary">
          {value.split('\n').length} 行 / {value.length} 字符
        </Typography>
      )}
    </Box>
  );
}
