import React, { useCallback, useRef, useState } from 'react';
import { Box, Typography } from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import type { SampleItem } from '../types';

interface Props {
  onFiles: (files: SampleItem[]) => void;
  multiple?: boolean;
  directory?: boolean;
  hint?: string;
}

const ACCEPT_EXT = ['.py', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.java', '.txt'];

function readFile(file: File): Promise<SampleItem> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () =>
      resolve({
        filename: (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name,
        content: String(reader.result ?? ''),
      });
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

/** 拖拽/多文件上传区（支持目录选择，纯本地读取不上传落盘）。 */
export default function FileDropZone({
  onFiles,
  multiple = true,
  directory = false,
  hint,
}: Props): React.ReactElement {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFiles = useCallback(
    async (fileList: FileList | File[]) => {
      const files = Array.from(fileList).filter((f) =>
        ACCEPT_EXT.some((ext) => f.name.toLowerCase().endsWith(ext)),
      );
      if (files.length > 0) {
        onFiles(await Promise.all(files.map(readFile)));
      }
    },
    [onFiles],
  );

  return (
    <Box
      className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors ${
        dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white'
      }`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFiles(e.dataTransfer.files);
      }}
    >
      <UploadFileIcon color="action" fontSize="large" />
      <Typography variant="body1" className="mt-2">
        {hint ?? '拖拽文件到此处，或点击选择（支持 .py / .cpp / .h / .java，可多选）'}
      </Typography>
      <input
        ref={inputRef}
        type="file"
        hidden
        multiple={multiple || directory}
        accept={ACCEPT_EXT.join(',')}
        {...(directory ? ({ webkitdirectory: '' } as object) : {})}
        onChange={(e) => {
          if (e.target.files) handleFiles(e.target.files);
          e.target.value = '';
        }}
      />
    </Box>
  );
}
