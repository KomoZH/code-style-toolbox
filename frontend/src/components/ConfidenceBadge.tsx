import React from 'react';
import { Chip, Tooltip } from '@mui/material';
import type { RuleMeta } from '../types';

interface Props {
  meta?: RuleMeta;
}

/** 置信度徽标：低置信度（<0.6 或样本不足或冲突）醒目警示色（P1-4）。 */
export default function ConfidenceBadge({ meta }: Props): React.ReactElement | null {
  if (!meta) return null;

  const low = meta.confidence < 0.6 || meta.low_evidence || meta.conflict;
  const color = meta.conflict ? 'error' : low ? 'warning' : 'success';
  const label = meta.conflict
    ? `冲突 ${(meta.confidence * 100).toFixed(0)}%`
    : `${(meta.confidence * 100).toFixed(0)}%`;

  const tipLines = [
    `样本数: ${meta.samples}`,
    ...(meta.examples?.length ? [`样例: ${meta.examples.slice(0, 3).join(' / ')}`] : []),
    ...(meta.conflict ? ['样本中存在两种以上风格（≥30%），取多数派'] : []),
    ...(meta.low_evidence ? ['证据不足（样本<30 或总行数<200），请人工确认'] : []),
  ];

  return (
    <Tooltip title={<span style={{ whiteSpace: 'pre-line' }}>{tipLines.join('\n')}</span>}>
      <Chip size="small" color={color} variant={low ? 'filled' : 'outlined'} label={label} />
    </Tooltip>
  );
}
