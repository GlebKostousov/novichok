export type DemoRole = 'employee' | 'mentor' | 'manager';
export type StageStatus = 'locked' | 'available' | 'awaiting_review' | 'revision_requested' | 'completed';
export type StageKind = 'acknowledgement' | 'assignment' | 'observation' | 'decision';

export interface Stage {
  id: string;
  key: 'welcome' | 'product' | 'practice' | 'independent';
  title: string;
  description: string;
  kind: StageKind;
  status: StageStatus;
  owner_role: DemoRole;
  owner_name: string;
  due_date: string;
  material_id: string | null;
  instructions: string;
  criteria: { id: string; label: string }[];
  submission: { text: string; submitted_at: string; attempt: number } | null;
  review: {
    decision: 'approved' | 'changes_requested';
    comment: string;
    checked_criteria: string[];
    reviewed_at: string;
    reviewer_name: string;
  } | null;
  completed_at: string | null;
}

export interface Employee {
  id: string;
  full_name: string;
  position: string;
  department_id: string;
  department_name: string;
  start_date: string;
  mentor_name: string;
  manager_name: string;
  external_id: string;
  stages: Stage[];
  blocker: { reason: string; owner_name: string; created_at: string } | null;
}

export interface Material {
  id: string;
  title: string;
  version: string;
  paragraphs: string[];
  products: { id: string; name: string; price: number; purpose: string; features: string[] }[];
}

export interface Activity {
  id: string;
  employee_id: string;
  actor_name: string;
  text: string;
  created_at: string;
}

export interface DemoState {
  revision: number;
  today: string;
  expires_at: string;
  departments: { id: string; name: string }[];
  employees: Employee[];
  materials: Material[];
  activities: Activity[];
  metrics: {
    employees_total: number;
    completed_stages: number;
    stages_total: number;
    awaiting_review: number;
    overdue_stages: number;
    blocked_employees: number;
    independent_employees: number;
  };
  last_event: { external_id: string; outcome: 'created' | 'already_processed' } | null;
}

export interface HireFields {
  external_id: string;
  full_name: string;
  department_id: string;
  start_date: string;
}

export type StageAction = 'acknowledge' | 'submit' | 'review' | 'observe' | 'approve';
export interface ActionFields {
  text?: string;
  decision?: 'approved' | 'changes_requested';
  comment?: string;
  checked_criteria?: string[];
}

export const stageStatusLabels: Record<StageStatus, string> = {
  locked: 'После предыдущего этапа',
  available: 'Можно начать',
  awaiting_review: 'Ждёт проверки',
  revision_requested: 'Нужна доработка',
  completed: 'Подтверждено',
};

export const roleLabels: Record<DemoRole, string> = {
  employee: 'Сотрудник',
  mentor: 'Наставник',
  manager: 'Руководитель',
};

export function formatDate(value: string): string {
  const date = new Date(value.includes('T') ? value : `${value}T12:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', timeZone: 'Europe/Moscow' }).format(date);
}

export function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Moscow' }).format(date);
}

export function workingStage(employee: Employee, role: DemoRole): Stage | undefined {
  if (role === 'mentor') {
    const review = employee.stages.find(stage => stage.status === 'awaiting_review');
    if (review) return review;
  }
  return employee.stages.find(stage => stage.status !== 'completed' && stage.status !== 'locked')
    ?? employee.stages.find(stage => stage.status !== 'completed')
    ?? employee.stages.at(-1);
}
