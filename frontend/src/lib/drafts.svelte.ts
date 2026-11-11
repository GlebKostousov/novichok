import { ApiError, request } from './api';
import type { DemoRole } from './types';

export interface DraftFields {
  answer: string; comment: string; checked: string[];
  full_name: string; department_id: string; start_date: string; external_id: string;
}
interface SavedDraft { key: string; version: number; fields: DraftFields; }
export interface DraftEntry extends SavedDraft {
  role: DemoRole; saved: string; status: 'saved' | 'pending' | 'saving' | 'error' | 'conflict';
  error: string; remote?: SavedDraft;
}
export const emptyFields = (): DraftFields => ({ answer: '', comment: '', checked: [], full_name: '', department_id: '', start_date: '', external_id: '' });

export class DraftStore {
  entries = $state<Record<string, DraftEntry>>({});
  private timers = new Map<string, ReturnType<typeof setTimeout>>();
  private flights = new Map<string, Promise<void>>();
  private paused = false;

  async load() {
    const saved = await request<SavedDraft[]>('/demo/drafts', { headers: { 'X-Demo-Role': 'employee' } });
    this.entries = Object.fromEntries(saved.map(item => [item.key, { ...item, role: item.key.split(':').at(-1) as DemoRole, saved: JSON.stringify(item.fields), status: 'saved' as const, error: '' }]));
  }

  get(key: string, role: DemoRole, initial: Partial<DraftFields> = {}): DraftEntry {
    if (!this.entries[key]) {
      const fields = { ...emptyFields(), ...initial };
      this.entries[key] = { key, role, version: 0, fields, saved: JSON.stringify(fields), status: 'saved', error: '' };
    }
    if (JSON.stringify(this.entries[key].fields) === JSON.stringify(emptyFields())) {
      this.entries[key].fields = { ...emptyFields(), ...initial };
    }
    return this.entries[key];
  }

  changed(entry: DraftEntry) {
    if (this.paused) return;
    if (JSON.stringify(entry.fields) === entry.saved || entry.status === 'conflict') return;
    if (entry.status !== 'saving') entry.status = 'pending';
    clearTimeout(this.timers.get(entry.key));
    this.timers.set(entry.key, setTimeout(() => { void this.save(entry); }, 350));
  }

  async save(entry: DraftEntry): Promise<void> {
    if (this.paused) return;
    clearTimeout(this.timers.get(entry.key));
    const flight = this.flights.get(entry.key);
    if (flight) { await flight; return this.save(entry); }
    if (entry.status === 'conflict' || JSON.stringify(entry.fields) === entry.saved) return;
    const operation = this.write(entry);
    this.flights.set(entry.key, operation);
    await operation;
    this.flights.delete(entry.key);
  }

  private async write(entry: DraftEntry) {
    const fields = JSON.parse(JSON.stringify(entry.fields)) as DraftFields;
    entry.status = 'saving';
    try {
      const saved = await request<SavedDraft>(`/demo/drafts/${encodeURIComponent(entry.key)}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Demo-Action': '1', 'X-Demo-Role': entry.role },
        body: JSON.stringify({ expected_version: entry.version, fields }),
      });
      entry.version = saved.version;
      entry.saved = JSON.stringify(saved.fields);
      entry.status = JSON.stringify(entry.fields) === entry.saved ? 'saved' : 'pending';
      entry.error = '';
    } catch (error) {
      entry.status = error instanceof ApiError && error.code === 'draft_conflict' ? 'conflict' : 'error';
      entry.error = error instanceof Error ? error.message : 'Не удалось сохранить черновик.';
    }
  }

  flush() { for (const entry of Object.values(this.entries)) if (entry.status === 'pending') void this.save(entry); }
  hasUnsaved() { return Object.values(this.entries).some(entry => JSON.stringify(entry.fields) !== entry.saved || entry.status === 'saving'); }

  async clear(entry: DraftEntry) {
    // Сохраняем пустую запись с новой версией: старое окно не вернёт отправленный ввод.
    entry.fields = emptyFields();
    await this.save(entry);
  }

  async compare(entry: DraftEntry) {
    try {
      const saved = await request<SavedDraft[]>('/demo/drafts', { headers: { 'X-Demo-Role': entry.role } });
      entry.remote = saved.find(item => item.key === entry.key);
    } catch (error) { entry.error = error instanceof Error ? error.message : 'Не удалось загрузить другой черновик.'; }
  }

  useRemote(entry: DraftEntry) {
    if (!entry.remote) return;
    entry.fields = structuredClone($state.snapshot(entry.remote.fields));
    entry.version = entry.remote.version;
    entry.saved = JSON.stringify(entry.fields);
    entry.status = 'saved'; entry.error = ''; entry.remote = undefined;
  }

  async keepMine(entry: DraftEntry) {
    if (!entry.remote) return;
    entry.version = entry.remote.version; entry.status = 'pending'; entry.remote = undefined;
    await this.save(entry);
  }

  reset() {
    for (const timer of this.timers.values()) clearTimeout(timer);
    this.timers.clear(); this.entries = {}; this.paused = false;
  }

  async pause() {
    this.paused = true;
    for (const timer of this.timers.values()) clearTimeout(timer);
    this.timers.clear();
    await Promise.all(this.flights.values());
  }
  resume() { this.paused = false; for (const entry of Object.values(this.entries)) this.changed(entry); }
}

export const createDraftStore = () => new DraftStore();
