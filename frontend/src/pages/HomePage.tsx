import React, { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Typography,
} from '@mui/material';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import ManageSearchIcon from '@mui/icons-material/ManageSearch';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useApp } from '../App';

/** 首页：功能卡片 + 一键演示（P1-3）。 */
export default function HomePage(): React.ReactElement {
  const navigate = useNavigate();
  const { setDemoSamples } = useApp();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const startDemo = async () => {
    setError('');
    setLoading(true);
    try {
      const examples = await api.listExamples();
      const python = examples.find((e) => e.language === 'python') ?? examples[0];
      if (!python) throw new Error('未找到内置示例');
      setDemoSamples(python.files);
      navigate('/extract');
    } catch (e) {
      setError(`加载示例失败：${e instanceof Error ? e.message : String(e)}（请确认后端已启动）`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box className="mt-8 flex flex-col items-center gap-8">
      <Box className="text-center">
        <Typography variant="h4" fontWeight="bold">
          代码风格迁移工具
        </Typography>
        <Typography variant="body1" color="text.secondary" className="mt-2">
          支持 C++ / Python / Java：从样例提取风格规则，按规则安全重写代码，全程本地离线。
        </Typography>
      </Box>

      {error && <Alert severity="error">{error}</Alert>}

      <Box className="flex flex-wrap justify-center gap-6">
        <Card className="w-80" variant="outlined">
          <CardContent>
            <ManageSearchIcon color="primary" fontSize="large" />
            <Typography variant="h6" className="mt-2">提取风格</Typography>
            <Typography variant="body2" color="text.secondary">
              上传代码样例，自动归纳命名、缩进、括号、空行等可复用规则，沉淀为团队规范。
            </Typography>
          </CardContent>
          <CardActions>
            <Button variant="contained" onClick={() => navigate('/extract')}>开始提取</Button>
          </CardActions>
        </Card>

        <Card className="w-80" variant="outlined">
          <CardContent>
            <AutoFixHighIcon color="secondary" fontSize="large" />
            <Typography variant="h6" className="mt-2">转换代码</Typography>
            <Typography variant="body2" color="text.secondary">
              粘贴或批量选择代码文件，按选定规则重写；语法校验 + 等价校验，失败自动保留原代码。
            </Typography>
          </CardContent>
          <CardActions>
            <Button variant="contained" color="secondary" onClick={() => navigate('/convert')}>
              开始转换
            </Button>
          </CardActions>
        </Card>
      </Box>

      <Button
        variant="outlined"
        size="large"
        startIcon={<PlayCircleOutlineIcon />}
        onClick={startDemo}
        disabled={loading}
      >
        使用示例演示（提取 → 规则 → 转换 → 对照）
      </Button>
    </Box>
  );
}
