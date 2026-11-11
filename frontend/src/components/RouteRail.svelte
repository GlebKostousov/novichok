<script lang="ts">
  import { stageStatusLabels } from '../lib/types';
  import type { Employee } from '../lib/types';
  interface Props { employee: Employee; selectedId: string; onSelect: (id: string) => void; }
  let { employee, selectedId, onSelect }: Props = $props();
  let expanded = $state(false);
  let completed = $derived(employee.stages.filter(stage => stage.status === 'completed').length);
</script>

<nav class="route-panel" aria-label="Маршрут адаптации">
  <div class="route-heading">
    <div><h2>Первые смены</h2><p>Подтверждено {completed} из {employee.stages.length} этапов</p></div>
    <button type="button" class="route-mobile-toggle" aria-expanded={expanded} aria-controls="route-list" onclick={() => expanded = !expanded}>{expanded ? 'Свернуть ↑' : 'Весь маршрут ↓'}</button>
  </div>
  <div class="route-content" class:mobile-expanded={expanded} id="route-list">
    <ol class="route-list">
      {#each employee.stages as stage, index (stage.id)}
        <li>
          <button type="button" class="route-step" class:active={selectedId === stage.id} class:locked={stage.status === 'locked'} aria-current={selectedId === stage.id ? 'step' : undefined} onclick={() => { onSelect(stage.id); expanded = false; }}>
            <span class="step-number" class:completed={stage.status === 'completed'} class:active={selectedId === stage.id && stage.status !== 'completed'} aria-hidden="true">{stage.status === 'completed' ? '✓' : String(index + 1).padStart(2, '0')}</span>
            <span class="step-info">
              <span class="step-title">{stage.title}</span>
              <span class="step-state" class:submitted={stage.status === 'awaiting_review'} class:returned={stage.status === 'revision_requested'} class:completed={stage.status === 'completed'}>{stageStatusLabels[stage.status]}</span>
            </span>
          </button>
        </li>
      {/each}
    </ol>
    <div class="route-footer">Следующий этап открывается после подтверждения предыдущего.</div>
  </div>
</nav>
