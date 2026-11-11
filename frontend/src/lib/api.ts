import type { DemoRole, DemoState } from './types';

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { credentials: 'same-origin', ...init });
  } catch {
    throw new ApiError('network_error', 'Не удалось связаться с сервисом. Проверьте соединение и повторите действие.', 0);
  }
  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new ApiError('invalid_response', 'Сервис не вернул данные. Попробуйте обновить страницу через несколько секунд.', response.status);
  }
  if (!response.ok) {
    const error = data as { error?: { code?: string; message?: string } };
    throw new ApiError(error.error?.code ?? 'request_error', error.error?.message ?? 'Не удалось выполнить действие. Обновите данные и повторите попытку.', response.status);
  }
  return data as T;
}

export function loadDemo(): Promise<DemoState> {
  return request<DemoState>('/demo');
}

export function updateDemo(path: string, role: DemoRole, body: Record<string, unknown>): Promise<DemoState> {
  return request<DemoState>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Demo-Action': '1', 'X-Demo-Role': role },
    body: JSON.stringify(body),
  });
}
