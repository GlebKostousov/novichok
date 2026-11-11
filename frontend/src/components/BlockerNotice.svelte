<script lang="ts">
  import type { DemoRole, Employee } from '../lib/types';
  import { getContext, untrack, tick } from 'svelte';
  import type { DraftEntry, DraftStore } from '../lib/drafts.svelte';
  import DraftStatus from './DraftStatus.svelte';
  interface Props { employee: Employee; role: DemoRole; busy: boolean; actionError: string; onResolve: (comment: string) => Promise<boolean>; onRoleChange: (role: DemoRole) => void; }
  let { employee, role, busy, actionError, onResolve, onRoleChange }: Props = $props();
  const drafts = getContext<DraftStore>('drafts');
  let draft = $state<DraftEntry>();
  let comment = $derived(draft?.fields.comment ?? '');
  let error = $state('');
  let localError: HTMLParagraphElement | undefined = $state();
  $effect(() => { const key = `${employee.id}:blocker:manager`; const active = role === 'manager'; untrack(() => { draft = active ? drafts.get(key, 'manager') : undefined; error = ''; }); });
  $effect(() => { const fields = draft && JSON.stringify(draft.fields); if (fields) untrack(() => drafts.changed(draft!)); });
  $effect(() => { if (actionError || error) void tick().then(() => localError?.focus()); });
  async function resolve(event: SubmitEvent) {
    event.preventDefault();
    error = '';
    if (comment.trim().length < 10) { error = 'Опишите, что подготовили. Нужно не меньше 10 символов.'; return; }
    const current = draft;
    const successful = await onResolve(comment.trim());
    if (successful && current) await drafts.clear(current);
  }
</script>

{#if employee.blocker}
  <section class="blocker-section" aria-labelledby="blocker-title">
    <span class="eyebrow">Условия со стороны магазина</span>
    <h3 id="blocker-title">{employee.blocker.reason}</h3>
    <p>Ответственный — {employee.blocker.owner_name}. Практику можно подтвердить после устранения препятствия.</p>
    {#if role === 'manager' && draft}
      <form onsubmit={resolve}>
        <label for="blocker-comment" class="field-label">Что подготовили</label>
        <textarea id="blocker-comment" bind:value={draft.fields.comment} minlength="10" maxlength="1000" required disabled={busy} placeholder="Например, согласовали время совместной консультации с наставником." rows="3"></textarea>
        {#if error || actionError}<p class="inline-error" role="alert" tabindex="-1" bind:this={localError}>{error || actionError}</p>{/if}
        <DraftStatus {draft} />
        <div class="form-actions"><button type="submit" class="button button-secondary" disabled={busy}>{busy ? 'Сохраняем…' : 'Препятствие устранено'}</button></div>
      </form>
    {:else}
      <button type="button" class="button button-small button-secondary" onclick={() => onRoleChange('manager')} disabled={busy}>Открыть в роли руководителя</button>
    {/if}
  </section>
{/if}
