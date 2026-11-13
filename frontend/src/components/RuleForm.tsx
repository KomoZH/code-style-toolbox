import React from 'react';
import {
  Box,
  MenuItem,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import ConfidenceBadge from './ConfidenceBadge';
import type { RuleMeta } from '../types';

export interface FieldSpec {
  key: string;
  label: string;
  type: 'select' | 'switch' | 'number' | 'text';
  options?: { value: string | number; label: string }[];
  min?: number;
  max?: number;
}

interface Props {
  fields: FieldSpec[];
  values: Record<string, unknown>;
  meta?: Record<string, RuleMeta>;
  disabled?: boolean;
  onChange: (key: string, value: unknown) => void;
}

/** 单组规则编辑控件（select/switch/number），每条规则右侧附置信度徽标。 */
export default function RuleForm({
  fields,
  values,
  meta = {},
  disabled = false,
  onChange,
}: Props): React.ReactElement {
  return (
    <Box className="flex flex-col gap-3">
      {fields.map((field) => {
        const value = values[field.key];
        const control =
          field.type === 'select' ? (
            <TextField
              select
              size="small"
              fullWidth
              disabled={disabled}
              value={String(value ?? '')}
              onChange={(e) => {
                const opt = field.options?.find((o) => String(o.value) === e.target.value);
                onChange(field.key, opt ? opt.value : e.target.value);
              }}
            >
              {field.options?.map((o) => (
                <MenuItem key={String(o.value)} value={String(o.value)}>
                  {o.label}
                </MenuItem>
              ))}
            </TextField>
          ) : field.type === 'switch' ? (
            <Switch
              checked={Boolean(value)}
              disabled={disabled}
              onChange={(e) => onChange(field.key, e.target.checked)}
            />
          ) : field.type === 'number' ? (
            <TextField
              type="number"
              size="small"
              fullWidth
              disabled={disabled}
              value={Number(value ?? 0)}
              inputProps={{ min: field.min ?? 0, max: field.max ?? 99 }}
              onChange={(e) => onChange(field.key, Number(e.target.value))}
            />
          ) : (
            <TextField
              size="small"
              fullWidth
              disabled={disabled}
              value={String(value ?? '')}
              onChange={(e) => onChange(field.key, e.target.value)}
            />
          );

        return (
          <Box key={field.key} className="grid grid-cols-5 items-center gap-3">
            <Typography variant="body2" className="col-span-2">
              {field.label}
            </Typography>
            <Box className="col-span-2">{control}</Box>
            <Box className="col-span-1 text-right">
              <ConfidenceBadge meta={meta[field.key]} />
            </Box>
          </Box>
        );
      })}
    </Box>
  );
}
