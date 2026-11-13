import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { HashRouter, Route, Routes } from 'react-router-dom';
import { Box } from '@mui/material';
import StepNav from './components/StepNav';
import HomePage from './pages/HomePage';
import ExtractPage from './pages/ExtractPage';
import RulesPage from './pages/RulesPage';
import ConvertPage from './pages/ConvertPage';
import DiffPage from './pages/DiffPage';
import { api } from './api/client';
import type { ConvertResponse, ProfileSummary, SampleItem } from './types';

/** 全局应用状态：当前规则集/语言、最近一次转换结果、演示预填样例。 */
interface AppState {
  profiles: ProfileSummary[];
  currentProfileId: string;
  currentLanguage: string;
  setCurrentProfile: (id: string, language: string) => void;
  refreshProfiles: () => Promise<void>;
  lastConvert: ConvertResponse | null;
  setLastConvert: (r: ConvertResponse | null) => void;
  demoSamples: SampleItem[];
  setDemoSamples: (s: SampleItem[]) => void;
}

const AppContext = createContext<AppState>(null as unknown as AppState);

export function useApp(): AppState {
  return useContext(AppContext);
}

export default function App(): React.ReactElement {
  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [currentProfileId, setCurrentProfileId] = useState('');
  const [currentLanguage, setCurrentLanguage] = useState('');
  const [lastConvert, setLastConvert] = useState<ConvertResponse | null>(null);
  const [demoSamples, setDemoSamples] = useState<SampleItem[]>([]);

  const refreshProfiles = useCallback(async () => {
    try {
      setProfiles(await api.listProfiles());
    } catch {
      // 后端未启动时静默失败，由页面级错误提示兜底
    }
  }, []);

  useEffect(() => {
    refreshProfiles();
  }, [refreshProfiles]);

  const setCurrentProfile = useCallback((id: string, language: string) => {
    setCurrentProfileId(id);
    setCurrentLanguage(language);
  }, []);

  const state = useMemo<AppState>(
    () => ({
      profiles,
      currentProfileId,
      currentLanguage,
      setCurrentProfile,
      refreshProfiles,
      lastConvert,
      setLastConvert,
      demoSamples,
      setDemoSamples,
    }),
    [profiles, currentProfileId, currentLanguage, refreshProfiles, lastConvert, demoSamples, setCurrentProfile],
  );

  return (
    <AppContext.Provider value={state}>
      <HashRouter>
        <Box className="flex min-h-screen flex-col">
          <StepNav />
          <Box component="main" className="mx-auto w-full max-w-7xl flex-1 p-4">
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/extract" element={<ExtractPage />} />
              <Route path="/rules" element={<RulesPage />} />
              <Route path="/convert" element={<ConvertPage />} />
              <Route path="/diff" element={<DiffPage />} />
            </Routes>
          </Box>
        </Box>
      </HashRouter>
    </AppContext.Provider>
  );
}
