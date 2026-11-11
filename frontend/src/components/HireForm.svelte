<script lang="ts">
  import { getContext, untrack, tick } from 'svelte';
  import type { DraftStore } from '../lib/drafts.svelte';
  import DraftStatus from './DraftStatus.svelte';
  import type { HireFields } from '../lib/types';
  interface Props {
    departments: { id: string; name: string }[];
    today: string;
    busy: boolean;
    actionError: string;
    onSubmit: (fields: HireFields) => Promise<boolean>;
    onCancel: () => void;
  }
  let { departments, today, busy, actionError, onSubmit, onCancel }: Props = $props();
  const drafts = getContext<DraftStore>('drafts');
  const draft = drafts.get('hire:manager', 'manager', untrack(() => ({ department_id: departments[0]?.id ?? '', start_date: today, external_id: `demo-${Date.now().toString(36)}` })));
  let form = $derived(draft.fields);
  let error = $state('');
  let localError: HTMLParagraphElement | undefined = $state();
  $effect(() => { const fields = JSON.stringify(form); if (fields) untrack(() => drafts.changed(draft)); });
  $effect(() => { if (actionError || error) void tick().then(() => localError?.focus()); });
  let earliestDate = $derived.by(() => {
    const date = new Date(`${today}T12:00:00Z`);
    date.setUTCDate(date.getUTCDate() - 365);
    return date.toISOString().slice(0, 10);
  });

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    error = '';
    if (form.full_name.trim().length < 2) { error = 'Укажите имя вымышленного сотрудника.'; return; }
    if (!/^[A-Za-z0-9_.-]{3,64}$/.test(form.external_id.trim())) { error = 'Номер события: от 3 до 64 латинских букв, цифр, точек, дефисов или подчёркиваний.'; return; }
    const successful = await onSubmit({ full_name: form.full_name.trim(), department_id: form.department_id, start_date: form.start_date, external_id: form.external_id.trim() });
    if (successful) { await drafts.clear(draft); onCancel(); }
  }
</script>

<section class="hire-panel" aria-labelledby="hire-title">
  <div class="hire-header"><div><h2 id="hire-title">Новый сотрудник вышел на работу</h2><p>Имитируем кадровое событие. Введите вымышленные сведения.</p></div><button type="button" class="button button-quiet" onclick={onCancel} disabled={busy}>Отмена</button></div>
  <form onsubmit={submit}>
    <div class="hire-fields">
      <div class="hire-name"><label for="hire-name" class="field-label">Имя и фамилия</label><input id="hire-name" type="text" bind:value={form.full_name} minlength="2" maxlength="80" required placeholder="Например, Олег Данилов" autocomplete="off" disabled={busy} /></div>
      <div><label for="hire-department" class="field-label">Магазин</label><select id="hire-department" bind:value={form.department_id} required disabled={busy}>{#each departments as department}<option value={department.id}>{department.name}</option>{/each}</select></div>
      <div><label for="hire-date" class="field-label">Дата первого выхода</label><input id="hire-date" type="date" bind:value={form.start_date} min={earliestDate} max={today} required disabled={busy} /></div>
      <div><label for="hire-external" class="field-label">Номер события</label><input id="hire-external" type="text" bind:value={form.external_id} minlength="3" maxlength="64" pattern="[A-Za-z0-9_.\-]+" required disabled={busy} aria-describedby="event-help" /></div>
    </div>
    <p id="event-help" class="hire-help">Для повтора оставьте прежние сведения и номер. Исправление сведений в демо не предусмотрено.</p>
    {#if error || actionError}<p class="inline-error" role="alert" tabindex="-1" bind:this={localError}>{error || actionError}</p>{/if}
    <DraftStatus {draft} />
    <div class="form-actions"><button type="submit" class="button button-primary" disabled={busy}>{busy ? 'Сохраняем…' : 'Зафиксировать выход'}</button><span class="action-note">Начнётся маршрут из четырёх этапов.</span></div>
  </form>
</section>
