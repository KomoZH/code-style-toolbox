import React from 'react';
import { AppBar, Box, Chip, Tab, Tabs, Toolbar, Typography } from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';
import { useApp } from '../App';

const STEPS = [
  { label: '首页', path: '/' },
  { label: '1. 提取', path: '/extract' },
  { label: '2. 规则', path: '/rules' },
  { label: '3. 转换', path: '/convert' },
  { label: '4. 对照', path: '/diff' },
];

/** 顶部步骤式导航（提取→规则→转换→对照），右上角显示当前规则集与语言。 */
export default function StepNav(): React.ReactElement {
  const navigate = useNavigate();
  const location = useLocation();
  const { profiles, currentProfileId, currentLanguage } = useApp();

  const current = profiles.find((p) => p.id === currentProfileId);
  const active = Math.max(
    0,
    STEPS.findIndex((s) => s.path === location.pathname),
  );

  return (
    <AppBar position="static" color="default" elevation={1}>
      <Toolbar className="flex items-center gap-4">
        <Typography variant="h6" className="whitespace-nowrap" color="primary">
          Code Style Toolbox
        </Typography>
        <Tabs
          value={active}
          onChange={(_, idx: number) => navigate(STEPS[idx].path)}
          className="flex-1"
        >
          {STEPS.map((s) => (
            <Tab key={s.path} label={s.label} />
          ))}
        </Tabs>
        <Box className="flex items-center gap-2">
          {currentLanguage && <Chip size="small" label={currentLanguage} color="primary" variant="outlined" />}
          <Chip
            size="small"
            label={current ? `规则集：${current.name}` : '未选择规则集'}
            color={current ? 'success' : 'default'}
            variant={current ? 'filled' : 'outlined'}
          />
        </Box>
      </Toolbar>
    </AppBar>
  );
}
