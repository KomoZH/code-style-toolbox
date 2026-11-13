import React from 'react';
import { Box, Paper, Typography } from '@mui/material';
import { Highlight, themes } from 'prism-react-renderer';
import type { DiffOp } from '../types';

interface Props {
  diff: DiffOp[];
  language?: string;
}

interface Row {
  oldText: string | null;
  newText: string | null;
  kind: 'equal' | 'delete' | 'insert' | 'replace';
}

const PRISM_LANG: Record<string, string> = { python: 'python', cpp: 'cpp', java: 'java' };

const KIND_BG: Record<string, string> = {
  equal: 'transparent',
  delete: '#fee2e2',
  insert: '#dcfce7',
  replace: '#fef9c3',
};

/** 并排 diff 渲染（行内增删标记 + 语法高亮；按 tag 渲染红/绿/灰，不二次计算）。 */
export default function DiffView({ diff, language = 'python' }: Props): React.ReactElement {
  // 展开 opcodes 为并排行
  const rows: Row[] = [];
  for (const op of diff) {
    const maxLen = Math.max(op.old_lines.length, op.new_lines.length);
    for (let i = 0; i < maxLen; i++) {
      const oldText = i < op.old_lines.length ? op.old_lines[i] : null;
      const newText = i < op.new_lines.length ? op.new_lines[i] : null;
      let kind: Row['kind'] = op.tag as Row['kind'];
      if (op.tag === 'replace') {
        kind = oldText !== null && newText !== null ? 'replace' : oldText !== null ? 'delete' : 'insert';
      }
      rows.push({ oldText, newText, kind });
    }
  }

  const renderCell = (text: string | null, kind: Row['kind'], side: 'old' | 'new') => {
    if (text === null) return <Box className="mono min-h-[1.4em] flex-1 px-2" />;
    const dim =
      (side === 'old' && kind === 'insert') || (side === 'new' && kind === 'delete');
    const bg = dim ? 'transparent' : KIND_BG[kind];
    const prefix = kind === 'insert' ? '+ ' : kind === 'delete' ? '- ' : '  ';
    return (
      <Box className="mono flex-1 overflow-hidden px-2 text-sm" style={{ background: bg }}>
        <Highlight theme={themes.vsLight} code={text || ' '} language={PRISM_LANG[language] ?? 'plain'}>
          {({ tokens, getTokenProps }) => (
            <span style={{ whiteSpace: 'pre' }}>
              <span style={{ color: '#9ca3af' }}>{prefix}</span>
              {(tokens[0] ?? []).map((token, key) => (
                <span key={key} {...getTokenProps({ token })} />
              ))}
            </span>
          )}
        </Highlight>
      </Box>
    );
  };

  if (rows.length === 0) {
    return <Typography color="text.secondary">无差异（代码未发生变化）。</Typography>;
  }

  return (
    <Paper variant="outlined" className="max-h-[560px] overflow-auto">
      <Box className="grid grid-cols-2 border-b bg-gray-50 px-2 py-1">
        <Typography variant="caption" fontWeight="bold">原始</Typography>
        <Typography variant="caption" fontWeight="bold">转换后</Typography>
      </Box>
      {rows.map((row, idx) => (
        <Box key={idx} className="grid grid-cols-2 divide-x">
          {renderCell(row.oldText, row.kind, 'old')}
          {renderCell(row.newText, row.kind, 'new')}
        </Box>
      ))}
    </Paper>
  );
}
