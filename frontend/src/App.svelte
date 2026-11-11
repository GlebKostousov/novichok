<script lang="ts">
  import { onMount, tick, setContext } from 'svelte';
  import AppHeader from './components/AppHeader.svelte';
  import PeopleList from './components/PeopleList.svelte';
  import RouteRail from './components/RouteRail.svelte';
  import TaskWorkspace from './components/TaskWorkspace.svelte';
  import ManagerQueue from './components/ManagerQueue.svelte';
  import HireForm from './components/HireForm.svelte';
  import ResetDialog from './components/ResetDialog.svelte';
  import { ApiError, loadDemo, updateDemo } from './lib/api';
  import { createDraftStore } from './lib/drafts.svelte';
  import { formatDate, workingStage } from './lib/types';
  import type { ActionFields, DemoRole, DemoState, HireFields, StageAction } from './lib/types';

  type Message = { kind: 'success' | 'error' | 'info'; text: string };
  const drafts = createDraftStore();
  setContext('drafts', drafts);

  function savedRole(): DemoRole {
    try {
      const value = localStorage.getItem('novichok-demo-role');
      return value === 'employee' || value === 'mentor' || value === 'manager' ? value : 'employee';
    } catch { return 'employee'; }
  }

  let role = $state<DemoRole>(savedRole());
  let demo = $state<DemoState | null>(null);
  let loading = $state(true);
  let pending = $state<string | null>(null);
  let loadError = $state('');
  let message = $state<Message | null>(null);
  let employeeId = $state('');
  let stageId = $state('');
  let resetOpen = $state(false);
  let showHire = $state(false);
  let actionError = $state('');
  let busy = $derived(loading || pending !== null);
  let employee = $derived(demo?.employees.find(item => item.id === employeeId));
  let stage = $derived(employee?.stages.find(item => item.id === stageId));
  let material = $derived(demo?.materials.find(item => item.id === stage?.material_id));
  let lastEventEmployee = $derived(demo?.employees.find(item => item.external_id === demo?.last_event?.external_id));
  let pageTitle = $derived(role === 'employee' ? employee?.full_name ?? 'Первые смены' : role === 'mentor' ? 'Практика и проверки' : 'Адаптация продавцов');
  let pageDescription = $derived(role === 'employee' ? 'Выберите этап.' : role === 'mentor' ? 'Проверьте ответ, дайте замечание или подтвердите готовность.' : 'Что ждёт решения руководителя.');

  function selectEmployee(id: string, requestedStageId?: string) {
    const person = demo?.employees.find(item => item.id === id);
    if (!person) return;
    drafts.flush();
    actionError = '';
    employeeId = person.id;
    stageId = requestedStageId && person.stages.some(item => item.id === requestedStageId)
      ? requestedStageId
      : workingStage(person, role)?.id ?? '';
  }

  function firstEmployee(next: DemoState) {
    const preferred = next.employees.find(person => {
      if (role === 'mentor') return person.stages.some(task => task.status === 'awaiting_review');
      if (role === 'manager') return person.blocker !== null;
      return person.stages.some(task => task.owner_role === 'employee' &&
        (task.status === 'available' || task.status === 'revision_requested'));
    });
    return preferred ?? next.employees[0];
  }

  function applyState(next: DemoState) {
    demo = next;
    const current = next.employees.find(item => item.id === employeeId);
    if (current) {
      if (!current.stages.some(item => item.id === stageId)) stageId = workingStage(current, role)?.id ?? '';
      return;
    }
    const first = firstEmployee(next);
    if (first) selectEmployee(first.id);
  }

  async function openQueueItem(personId: string, taskId: string) {
    selectEmployee(personId, taskId);
    await tick();
    const heading = document.getElementById('task-title');
    heading?.focus({ preventScroll: true });
    heading?.scrollIntoView({ block: 'start' });
  }

  async function refresh() {
    if (!demo) loading = true;
    else pending = 'refresh';
    loadError = '';
    try {
      const next = await loadDemo();
      if (!demo) await drafts.load();
      applyState(next);
      if (pending === 'refresh') message = { kind: 'info', text: 'Данные обновлены. Все сохранённые действия на месте.' };
    } catch (error) {
      const text = error instanceof Error ? error.message : 'Не удалось загрузить учебный пример.';
      if (demo) message = { kind: 'error', text };
      else loadError = text;
    } finally { loading = false; pending = null; }
  }

  function changeRole(value: DemoRole, contextual = true) {
    if (busy) return;
    role = value;
    drafts.flush();
    actionError = '';
    showHire = false;
    try { localStorage.setItem('novichok-demo-role', value); } catch { /* Демо работает и без localStorage. */ }
    if (!contextual && demo) {
      const first = firstEmployee(demo);
      if (first) selectEmployee(first.id);
    } else if (employee) stageId = workingStage(employee, value)?.id ?? stageId;
    message = null;
  }

  async function mutate(path: string, fields: object = {}): Promise<DemoState | null> {
    if (!demo || pending !== null) return null;
    pending = path;
    actionError = '';
    message = null;
    try {
      const next = await updateDemo(path, role, { ...fields, expected_revision: demo.revision });
      applyState(next);
      return next;
    } catch (error) {
      if (error instanceof ApiError && error.code === 'stale_state') {
        try {
          applyState(await loadDemo());
          message = { kind: 'error', text: 'Данные изменились в другом окне. Мы загрузили актуальное состояние. Проверьте его перед повтором действия.' };
        } catch {
          message = { kind: 'error', text: 'Данные изменились, но обновить их не удалось. Нажмите «Обновить данные» перед повтором действия.' };
        }
      } else message = { kind: 'error', text: error instanceof Error ? error.message : 'Не удалось сохранить действие.' };
      actionError = message?.text ?? 'Не удалось сохранить действие. Повторите отправку.';
      return null;
    } finally { pending = null; }
  }

  async function stageAction(action: StageAction, fields: ActionFields = {}): Promise<boolean> {
    if (!employee || !stage) return false;
    const personId = employee.id;
    const taskId = stage.id;
    const next = await mutate(`/employees/${encodeURIComponent(personId)}/stages/${encodeURIComponent(taskId)}/${action}`, fields);
    if (!next) return false;
    const messages: Record<StageAction, string> = {
      acknowledge: 'Ознакомление сохранено. Открыто задание по подбору товара.',
      submit: 'Ответ отправлен наставнику. Практика откроется после подтверждения критериев.',
      review: fields.decision === 'changes_requested' ? 'Задание возвращено с замечанием. Сотрудник может доработать ответ.' : 'Задание подтверждено. Открыта практика с наставником.',
      observe: 'Практика подтверждена. Теперь руководитель может принять решение о самостоятельности.',
      approve: 'Решение сохранено. Учебный маршрут пройден.',
    };
    message = { kind: 'success', text: messages[action] };
    if (action === 'acknowledge' && employeeId === personId) selectEmployee(personId);
    return true;
  }

  async function resolveBlocker(comment: string): Promise<boolean> {
    if (!employee) return false;
    const next = await mutate(`/employees/${encodeURIComponent(employee.id)}/blocker/resolve`, { comment });
    if (!next) return false;
    message = { kind: 'success', text: 'Препятствие устранено. Наставник может провести и подтвердить практику.' };
    return true;
  }

  async function hire(fields: HireFields): Promise<boolean> {
    const next = await mutate('/demo/hire', fields);
    if (!next) return false;
    const person = next.employees.find(item => item.external_id === fields.external_id);
    if (person) selectEmployee(person.id);
    message = next.last_event?.outcome === 'already_processed'
      ? { kind: 'info', text: 'Уже обработано. Повтор события не создал второго сотрудника; существующий маршрут сохранён.' }
      : { kind: 'success', text: `Маршрут создан. Сотрудник — ${fields.full_name}.` };
    return true;
  }

  async function repeatEvent() {
    if (!lastEventEmployee) return;
    await hire({ external_id: lastEventEmployee.external_id, full_name: lastEventEmployee.full_name, department_id: lastEventEmployee.department_id, start_date: lastEventEmployee.start_date });
  }

  async function reset() {
    pending = 'draft-flush';
    await drafts.pause();
    pending = null;
    const next = await mutate('/demo/reset');
    if (!next) { drafts.resume(); return; }
    drafts.reset();
    resetOpen = false;
    showHire = false;
    const first = firstEmployee(next);
    if (first) selectEmployee(first.id);
    message = { kind: 'success', text: 'Учебный пример восстановлен. Можно пройти сценарий заново.' };
  }

  function beforeUnload(event: BeforeUnloadEvent) {
    if (!drafts.hasUnsaved()) return;
    drafts.flush();
    event.preventDefault();
    event.returnValue = '';
  }

  onMount(() => { void refresh(); });
</script>

<svelte:head><title>{pageTitle} — Новичок</title></svelte:head>

<a class="skip-link" href="#main-content">Перейти к работе</a>
<svelte:window onbeforeunload={beforeUnload} />
<AppHeader {role} onRoleChange={(value) => changeRole(value, false)} onReset={() => resetOpen = true} {busy} />

<main class="app-shell" id="main-content">
  {#if loading}
    <section class="state-panel" role="status" aria-live="polite"><span class="eyebrow">Новичок</span><h1>Загружаем учебный пример…</h1><p>Подготовим сотрудников, их маршруты и сохранённые ответы.</p></section>
  {:else if loadError}
    <section class="state-panel" role="alert"><span class="eyebrow">Учебный пример</span><h1>Не удалось загрузить данные</h1><p>{loadError}</p><button type="button" class="button button-primary" onclick={refresh}>Попробовать ещё раз</button></section>
  {:else if demo}
    <div class="page-heading"><div><h1>{pageTitle}</h1><p>{pageDescription}</p></div><div class="heading-meta">{role === 'employee' && employee ? employee.department_name : 'Демонстрационный магазин'}<br />{formatDate(demo.today)}</div></div>

    {#if message}
      <div class="notice app-message" class:success={message.kind === 'success'} class:error={message.kind === 'error'} role={message.kind === 'error' ? 'alert' : 'status'}><p>{message.text}</p><button type="button" aria-label="Закрыть сообщение" onclick={() => message = null}>×</button></div>
    {/if}

    {#if role === 'manager'}
      <div class="manager-actions">
        <button type="button" class="button button-secondary" onclick={() => showHire = !showHire} aria-expanded={showHire} aria-controls="hire-area" disabled={busy || demo.employees.length >= 20}>Добавить новичка</button>
        {#if demo.employees.length >= 20}<p>В этом примере уже 20 сотрудников.</p>{/if}
        {#if demo.last_event && lastEventEmployee}
          <div class="last-event"><span>{demo.last_event.outcome === 'already_processed' ? 'Последнее событие уже обработано' : 'Последний выход сохранён'} · {lastEventEmployee.full_name}</span><button type="button" class="button button-quiet button-small" onclick={repeatEvent} disabled={busy}>Повторить последнее событие</button></div>
        {:else}<p>Можно показать выход нового сотрудника и повтор события без дубля.</p>{/if}
      </div>
      <div id="hire-area">{#if showHire}<HireForm departments={demo.departments} today={demo.today} {busy} {actionError} onSubmit={hire} onCancel={() => { drafts.flush(); showHire = false; }} />{/if}</div>
      <ManagerQueue state={demo} onOpen={openQueueItem} />
    {/if}

    {#if employee && stage}
      <div class="workspace-layout">
        <PeopleList employees={demo.employees} selectedId={employeeId} {role} onSelect={selectEmployee} />
        <RouteRail {employee} selectedId={stageId} onSelect={(id) => { drafts.flush(); actionError = ''; stageId = id; }} />
        <TaskWorkspace {employee} {stage} {material} activities={demo.activities} {role} today={demo.today} {busy} {actionError} onAction={stageAction} onResolveBlocker={resolveBlocker} onSelectStage={(id) => { drafts.flush(); actionError = ''; stageId = id; }} onRoleChange={changeRole} />
      </div>
    {:else}
      <section class="state-panel"><h2>Пока нет маршрутов</h2><p>Руководитель может добавить вымышленного сотрудника. Для возврата исходного примера нажмите «Начать заново».</p><button type="button" class="button button-secondary" onclick={() => changeRole('manager')}>Открыть роль руководителя</button></section>
    {/if}

    <footer class="workspace-footer"><span>Роли переключаются для показа. Реального подключения к Битрикс24 и отправки уведомлений нет.</span><button type="button" onclick={refresh} disabled={busy}>Обновить данные</button></footer>
  {/if}
</main>

<ResetDialog open={resetOpen} busy={pending === '/demo/reset'} onCancel={() => { if (pending !== '/demo/reset') resetOpen = false; }} onConfirm={reset} />
