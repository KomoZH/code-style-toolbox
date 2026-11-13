// 与后端 api/schemas.py 一一对应的 TS 类型（架构 §3.3）

export type Language = 'python' | 'cpp' | 'java';
export type NamingStyle = 'snake_case' | 'camelCase' | 'PascalCase' | 'UPPER_SNAKE';
export type ConvertStatus = 'converted' | 'skipped' | 'failed';

export interface ApiEnvelope<T> {
  code: number;
  message: string;
  data: T;
}

export interface DetectResult {
  language: string;
  confidence: number;
  manual_required: boolean;
  scores?: Record<string, number>;
}

export interface RuleMeta {
  confidence: number;
  samples: number;
  examples: string[];
  conflict?: boolean;
  low_evidence?: boolean;
}

export interface NamingRules {
  variables: NamingStyle;
  functions: NamingStyle;
  classes: NamingStyle;
  constants: NamingStyle;
  private_prefix: string;
  member_prefix: string;
}

export interface IndentRules {
  style: 'space' | 'tab';
  size: number;
}

export interface BraceRules {
  style: 'k_and_r' | 'allman';
  space_before_paren: boolean;
}

export interface SpacingRules {
  space_around_operators: boolean;
  space_after_comma: boolean;
  trim_trailing_whitespace: boolean;
}

export interface BlankLineRules {
  max_consecutive: number;
  between_functions: number;
  after_imports: number;
}

export interface CommentRules {
  inline_min_spaces: number;
  docstring_format: 'google' | 'numpy' | 'sphinx' | 'none';
}

export interface DeclarationRules {
  cpp_const_style: 'east' | 'west';
  python_type_hints: boolean;
}

export interface Rules {
  naming: NamingRules;
  indent: IndentRules;
  brace_style: BraceRules;
  spacing: SpacingRules;
  blank_lines: BlankLineRules;
  comments: CommentRules;
  declarations: DeclarationRules;
}

export interface StyleProfile {
  id: string;
  name: string;
  language: Language;
  version: string;
  created_at: string;
  source: 'extracted' | 'preset' | 'manual';
  rules: Rules;
  meta: Record<string, Record<string, RuleMeta> | any>;
}

export interface ProfileSummary {
  id: string;
  name: string;
  language: Language;
  source: string;
  updated_at: string;
}

export interface SampleItem {
  filename: string;
  content: string;
}

export interface DiffOp {
  tag: 'equal' | 'delete' | 'insert' | 'replace';
  old_lines: string[];
  new_lines: string[];
}

export interface ConvertResult {
  filename: string;
  status: ConvertStatus;
  original: string;
  converted: string;
  reason: string;
  diff: DiffOp[];
  rename_map: Record<string, string>;
}

export interface ConvertSummary {
  total: number;
  converted: number;
  skipped: number;
  failed: number;
}

export interface ConvertResponse {
  results: ConvertResult[];
  summary: ConvertSummary;
}

export interface HistorySummary {
  id: string;
  time: string;
  profile_name: string;
  files: string[];
}

export interface RestoreResponse {
  restored: string[];
  items: { filename: string; content: string }[];
}

export interface ExampleGroup {
  language: Language;
  files: SampleItem[];
}
