export interface ScannedFile {
  path: string;
  line_count: number;
}

export interface ScanResult {
  repository_path: string;
  repository_name: string;
  python_file_count: number;
  total_line_count: number;
  total_discovered_files: number;
  discovered_files: ScannedFile[];
  scan_status: string;
}

export interface IndexJob {
  job_id: string;
  repository_id: string;
  repository_name: string;
  repository_path: string;
  status: "queued" | "indexing" | "completed" | "failed";
  stage: string;
  files_total: number;
  files_processed: number;
  files_indexed: number;
  chunks_total: number;
  chunks_indexed: number;
  syntax_error_files: number;
  warnings: string[];
  error: string | null;
}

export interface RepositoryOverviewResponse {
  repository_id: string;
  repository_name: string;
  repository_path: string;
  supported_languages: string[];
  files_count: number;
  lines_count: number;
  chunks_count: number;
  classes_count: number;
  functions_count: number;
  methods_count: number;
  modules_count: number;
  indexed_at: string;
  embedding_model: string;
  llm_model: string;
  default_retrieval_mode: string;
}

export interface SourceReference {
  file_path: string;
  symbol: string;
  parent_symbol: string;
  chunk_type: string;
  start_line: number;
  end_line: number;
}

export interface SourceSnippet {
  repository_id: string;
  file_path: string;
  start_line: number;
  end_line: number;
  total_lines: number;
  code: string;
  full_content: string | null;
}

export interface ChatResponse {
  answer: string;
  sources: SourceReference[];
  retrieved_chunks: number;
  repository_id: string;
  repository_name: string;
  retrieval_mode: string;
}

export interface OllamaStatus {
  available: boolean;
  model: string;
  model_available: boolean;
  detail: string;
}

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("The backend returned an unexpected response. Please try again.");
  }
  return value as Record<string, unknown>;
}

function stringField(value: unknown): string {
  if (typeof value !== "string") {
    throw new Error("The backend returned an unexpected response. Please try again.");
  }
  return value;
}

function numberField(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error("The backend returned an unexpected response. Please try again.");
  }
  return value;
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    throw new Error("The backend returned an unexpected response. Please try again.");
  }
  return value;
}

export function parseChatResponse(value: unknown): ChatResponse {
  const body = record(value);
  if (!Array.isArray(body.sources)) {
    throw new Error("The assistant returned an unexpected response. Please try again.");
  }
  const sources = body.sources.map((value): SourceReference => {
    const source = record(value);
    return {
      file_path: stringField(source.file_path),
      symbol: stringField(source.symbol),
      parent_symbol: stringField(source.parent_symbol),
      chunk_type: stringField(source.chunk_type),
      start_line: numberField(source.start_line),
      end_line: numberField(source.end_line),
    };
  });
  const answer = stringField(body.answer).trim();
  if (!answer || answer === "[object Object]") throw new Error("The assistant returned an invalid answer. Please try again.");
  return {
    answer,
    sources,
    retrieved_chunks: numberField(body.retrieved_chunks),
    repository_id: stringField(body.repository_id),
    repository_name: stringField(body.repository_name),
    retrieval_mode: stringField(body.retrieval_mode),
  };
}

export function parseScanResult(value: unknown): ScanResult {
  const body = record(value);
  if (!Array.isArray(body.discovered_files)) throw new Error("The scan returned an unexpected response.");
  return {
    repository_path: stringField(body.repository_path),
    repository_name: stringField(body.repository_name),
    python_file_count: numberField(body.python_file_count),
    total_line_count: numberField(body.total_line_count),
    total_discovered_files: numberField(body.total_discovered_files),
    discovered_files: body.discovered_files.map((file) => {
      const item = record(file);
      return { path: stringField(item.path), line_count: numberField(item.line_count) };
    }),
    scan_status: stringField(body.scan_status),
  };
}

export function parseIndexJob(value: unknown): IndexJob {
  const body = record(value);
  const status = stringField(body.status);
  if (!["queued", "indexing", "completed", "failed"].includes(status)) {
    throw new Error("The backend returned an unexpected indexing status.");
  }
  return {
    job_id: stringField(body.job_id),
    repository_id: stringField(body.repository_id),
    repository_name: stringField(body.repository_name),
    repository_path: stringField(body.repository_path),
    status: status as IndexJob["status"],
    stage: stringField(body.stage),
    files_total: numberField(body.files_total),
    files_processed: numberField(body.files_processed),
    files_indexed: numberField(body.files_indexed),
    chunks_total: numberField(body.chunks_total),
    chunks_indexed: numberField(body.chunks_indexed),
    syntax_error_files: numberField(body.syntax_error_files),
    warnings: stringArray(body.warnings),
    error: typeof body.error === "string" ? body.error : null,
  };
}

export function parseOverview(value: unknown): RepositoryOverviewResponse {
  const body = record(value);
  return {
    repository_id: stringField(body.repository_id),
    repository_name: stringField(body.repository_name),
    repository_path: stringField(body.repository_path),
    supported_languages: stringArray(body.supported_languages),
    files_count: numberField(body.files_count),
    lines_count: numberField(body.lines_count),
    chunks_count: numberField(body.chunks_count),
    classes_count: numberField(body.classes_count),
    functions_count: numberField(body.functions_count),
    methods_count: numberField(body.methods_count),
    modules_count: numberField(body.modules_count),
    indexed_at: stringField(body.indexed_at),
    embedding_model: stringField(body.embedding_model),
    llm_model: stringField(body.llm_model),
    default_retrieval_mode: stringField(body.default_retrieval_mode),
  };
}

export function parseSourceSnippet(value: unknown): SourceSnippet {
  const body = record(value);
  return {
    repository_id: stringField(body.repository_id),
    file_path: stringField(body.file_path),
    start_line: numberField(body.start_line),
    end_line: numberField(body.end_line),
    total_lines: numberField(body.total_lines),
    code: stringField(body.code),
    full_content: typeof body.full_content === "string" ? body.full_content : null,
  };
}

export async function requestJson(url: string, init?: RequestInit): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new Error("Could not reach the backend. Check that it is running and try again.");
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new Error("The backend returned an unreadable response. Please try again.");
  }
  if (!response.ok) {
    const body = typeof payload === "object" && payload !== null ? payload as Record<string, unknown> : {};
    const detail = typeof body.detail === "string" ? body.detail : "";
    if (response.status === 503 && /ollama/i.test(detail)) {
      throw new Error("Ollama isn't ready. Start Ollama, confirm the configured model is installed, and try again.");
    }
    if (response.status === 409 && /index/i.test(detail)) {
      throw new Error("This repository is still being indexed or has not been indexed yet.");
    }
    if (response.status === 400 || response.status === 403 || response.status === 404) {
      throw new Error(detail || "The backend could not complete that request.");
    }
    if (response.status === 422) throw new Error("Check the request details and try again.");
    throw new Error("The backend could not complete that request. Please try again.");
  }
  return payload;
}
