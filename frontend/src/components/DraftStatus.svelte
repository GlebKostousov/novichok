<script lang="ts">
  import { getContext } from 'svelte';
  import type { DraftEntry, DraftStore } from '../lib/drafts.svelte';
  const drafts = getContext<DraftStore>('drafts');
  let { draft }: { draft: DraftEntry | undefined } = $props();
  function preview(fields: DraftEntry['fields']) {
    const labels: Record<string, string> = { answer: 'Ответ', comment: 'Комментарий', checked: 'Отмечено критериев', full_name: 'Имя', department_id: 'Магазин', start_date: 'Дата', external_id: 'Событие' };
    const departments: Record<string, string> = { center: 'Магазин · Центр', north: 'Магазин · Север' };
    return Object.entries(fields).filter(([, value]) => Array.isArray(value) ? value.length : value).map(([key, value]) => `${labels[key]}: ${key === 'checked' ? (value as string[]).length : key === 'department_id' ? departments[String(value)] ?? 'Выбран магазин' : value}`).join('\n');
  }
</script>

{#if draft}
  <div class="draft-status" aria-live="polite">
    {#if draft.status === 'saved'}<span>{draft.version ? 'Черновик сохранён на сервере' : 'Ввод сохраняется на сервере'}</span>
    {:else if draft.status === 'pending' || draft.status === 'saving'}<span>Сохраняем черновик… Перед обновлением страницы дождитесь подтверждения.</span>
    {:else if draft.status === 'conflict'}
      <p class="inline-error">{draft.error} Сначала сравните обе версии.</p>
      <button class="button button-small button-secondary" type="button" onclick={() => draft && drafts.compare(draft)}>Сравнить черновики</button>
      {#if draft.remote}
        <details open><summary>Черновик из другого окна</summary><pre>{preview(draft.remote.fields)}</pre></details>
        <p>Ваш ввод остаётся в форме. Замена серверной версии произойдёт только по вашему выбору.</p>
        <button class="button button-small button-secondary" type="button" onclick={() => draft && drafts.useRemote(draft)}>Взять версию из другого окна</button>
        <button class="button button-small button-return" type="button" onclick={() => draft && drafts.keepMine(draft)}>Сохранить мой ввод вместо неё</button>
      {/if}
    {:else}
      <p class="inline-error">{draft.error} Ввод остаётся в этой вкладке; при закрытии без связи он может потеряться.</p>
      <button class="button button-small button-secondary" type="button" onclick={() => draft && drafts.save(draft)}>Повторить сохранение черновика</button>
    {/if}
  </div>
{/if}
