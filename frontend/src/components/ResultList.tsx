import React from 'react';
import {
  Box,
  Chip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import type { ConvertResult, ConvertSummary } from '../types';

interface Props {
  results: ConvertResult[];
  summary: ConvertSummary;
  onSelect?: (result: ConvertResult) => void;
  selectedFilename?: string;
}

const STATUS_COLOR: Record<string, 'success' | 'warning' | 'error'> = {
  converted: 'success',
  skipped: 'warning',
  failed: 'error',
};

const STATUS_LABEL: Record<string, string> = {
  converted: '已转换',
  skipped: '已跳过',
  failed: '失败(已回退)',
};

/** 批量结果清单（成功/跳过/失败 + 原因，P1-1）。 */
export default function ResultList({
  results,
  summary,
  onSelect,
  selectedFilename,
}: Props): React.ReactElement {
  return (
    <Box className="flex flex-col gap-2">
      <Box className="flex gap-2">
        <Chip label={`共 ${summary.total}`} variant="outlined" />
        <Chip label={`成功 ${summary.converted}`} color="success" variant="outlined" />
        <Chip label={`跳过 ${summary.skipped}`} color="warning" variant="outlined" />
        <Chip label={`失败 ${summary.failed}`} color="error" variant="outlined" />
      </Box>
      <Paper variant="outlined" className="max-h-[320px] overflow-auto">
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell>文件</TableCell>
              <TableCell width={130}>状态</TableCell>
              <TableCell>说明 / 原因</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {results.map((r) => (
              <TableRow
                key={r.filename}
                hover
                selected={r.filename === selectedFilename}
                onClick={() => onSelect?.(r)}
                sx={{ cursor: onSelect ? 'pointer' : 'default' }}
              >
                <TableCell className="mono">{r.filename}</TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    color={STATUS_COLOR[r.status]}
                    label={STATUS_LABEL[r.status]}
                  />
                </TableCell>
                <TableCell>
                  <Typography variant="caption" color="text.secondary">
                    {r.status === 'converted'
                      ? Object.keys(r.rename_map).length > 0
                        ? `重命名 ${Object.keys(r.rename_map).length} 处`
                        : '仅格式调整'
                      : r.reason}
                  </Typography>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Paper>
    </Box>
  );
}
