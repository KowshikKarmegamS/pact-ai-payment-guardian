export class ApiError extends Error {
  status: number;
  code: string | null;
  data: unknown;

  constructor(message: string, status: number, code: string | null = null, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.data = data;
  }
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

function extractError(data: unknown, fallback: string): { message: string; code: string | null } {
  if (typeof data === 'object' && data !== null && 'detail' in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === 'string') return { message: detail, code: null };
    if (typeof detail === 'object' && detail !== null && 'message' in detail) {
      const d = detail as { message: unknown; code?: unknown };
      return { message: String(d.message), code: typeof d.code === 'string' ? d.code : null };
    }
    if (Array.isArray(detail)) {
      return {
        message: detail
          .map((e) => (typeof e === 'object' && e && 'msg' in e ? String((e as { msg: unknown }).msg) : String(e)))
          .join('; '),
        code: 'VALIDATION_ERROR',
      };
    }
  }
  return { message: fallback, code: null };
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const headers = new Headers(options.headers || {});
  if (options.body !== undefined) headers.set('Content-Type', 'application/json');
  headers.set('Accept', 'application/json');

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch {
    throw new ApiError('Cannot reach the PACT backend. Is the API server running?', 0, 'NETWORK');
  }

  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!response.ok) {
    const { message, code } = extractError(data, response.statusText || `Request failed (${response.status})`);
    throw new ApiError(message, response.status, code, data);
  }
  return data as T;
}

export const api = {
  get: <T>(endpoint: string): Promise<T> => request<T>(endpoint, { method: 'GET' }),
  post: <T>(endpoint: string, body?: unknown): Promise<T> =>
    request<T>(endpoint, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined }),
  put: <T>(endpoint: string, body?: unknown): Promise<T> =>
    request<T>(endpoint, { method: 'PUT', body: body !== undefined ? JSON.stringify(body) : undefined }),
};

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return 'Unexpected error';
}

export default api;
