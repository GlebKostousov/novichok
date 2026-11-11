<script lang="ts">
  import type { DemoRole } from '../lib/types';

  interface Props {
    role: DemoRole;
    onRoleChange: (role: DemoRole) => void;
    onReset: () => void;
    busy?: boolean;
  }

  let { role, onRoleChange, onReset, busy = false }: Props = $props();

  const roles: { id: DemoRole; label: string }[] = [
    { id: 'employee', label: 'Сотрудник' },
    { id: 'mentor', label: 'Наставник' },
    { id: 'manager', label: 'Руководитель' },
  ];
</script>

<header class="app-header">
  <div class="header-top">
    <a class="brand" href="#main-content" aria-label="Новичок — перейти к работе">
      <span class="brand-mark" aria-hidden="true">н</span>
      <span>Новичок</span>
    </a>
    <p class="demo-notice">Учебная версия <span aria-hidden="true">·</span> вымышленные данные</p>
    <button type="button" class="button button-quiet reset-trigger" onclick={onReset} disabled={busy}>
      <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <path d="M3.5 7.5A6.6 6.6 0 1 1 3.6 13M3.5 3.8v3.9h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      Начать заново
    </button>
  </div>
  <div class="header-controls">
    <div class="role-controls">
      <span class="control-caption" id="demo-role-label">Роль в демо</span>
      <div class="role-switcher" role="group" aria-labelledby="demo-role-label">
        {#each roles as item}
          <button
            type="button"
            class:active={role === item.id}
            aria-pressed={role === item.id}
            onclick={() => onRoleChange(item.id)}
            disabled={busy}
          >{item.label}</button>
        {/each}
      </div>
    </div>
    <span class="header-context">Магазин спорттоваров · адаптация продавца</span>
  </div>
</header>
