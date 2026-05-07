import type { UserMemory } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function handleResponse(res: Response) {
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail || `请求失败 (${res.status})`);
  }
  return res.json();
}

export async function registerUser(userId: string) {
  const res = await fetch(`${API_BASE}/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId }),
  });
  return handleResponse(res);
}

export async function loadMemory(userId: string): Promise<UserMemory> {
  const res = await fetch(`${API_BASE}/memory/${encodeURIComponent(userId)}`);
  return handleResponse(res);
}

export async function saveMemory(
  userId: string,
  memory: Partial<UserMemory>
) {
  const res = await fetch(
    `${API_BASE}/memory/${encodeURIComponent(userId)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(memory),
    }
  );
  return handleResponse(res);
}

export async function* chatStream(userId: string, message: string) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({ user_id: userId, message }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      data.detail || `聊天请求失败 (${res.status})`
    );
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error('无法读取响应流');

  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const token = decodeURIComponent(line.slice(6));
          if (token) yield token;
        }
      }
    }
    // Process remaining buffer
    if (buffer.startsWith('data: ')) {
      const token = decodeURIComponent(buffer.slice(6));
      if (token) yield token;
    }
  } finally {
    reader.releaseLock();
  }
}

export async function checkConnection() {
  try {
    const res = await fetch(`${API_BASE}/`);
    return res.ok;
  } catch {
    return false;
  }
}
