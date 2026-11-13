import { createTheme } from '@mui/material/styles';

// 全本地离线：不引用任何 CDN 字体（架构 §8 离线约束）
export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#2563eb' },
    secondary: { main: '#7c3aed' },
    success: { main: '#16a34a' },
    warning: { main: '#d97706' },
    error: { main: '#dc2626' },
  },
  typography: {
    fontFamily: "'Segoe UI', 'Microsoft YaHei', Roboto, sans-serif",
  },
});
