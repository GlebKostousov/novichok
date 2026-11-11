<script lang="ts">
  import { formatDate } from '../lib/types';
  import type { DemoState } from '../lib/types';
  interface Props { state: DemoState; onOpen: (employeeId: string, stageId: string) => void; }
  let { state, onOpen }: Props = $props();

  let rows = $derived.by(() => state.employees.flatMap(employee => {
    const result: { id: string; employeeId: string; stageId: string; name: string; department: string; reason: string; owner: string; status: string }[] = [];
    if (employee.blocker) {
      const stage = employee.stages.find(item => item.status === 'available') ?? employee.stages[0];
      if (stage) result.push({ id: `${employee.id}-blocker`, employeeId: employee.id, stageId: stage.id, name: employee.full_name, department: employee.department_name, reason: employee.blocker.reason, owner: employee.blocker.owner_name, status: 'Со стороны магазина' });
    }
    for (const stage of employee.stages) {
      if (stage.status === 'awaiting_review') result.push({ id: stage.id, employeeId: employee.id, stageId: stage.id, name: employee.full_name, department: employee.department_name, reason: stage.title, owner: stage.owner_name, status: stage.due_date < state.today ? `Ждёт проверки · срок ${formatDate(stage.due_date)}` : 'Ждёт проверки' });
      else if (stage.status === 'revision_requested') result.push({ id: stage.id, employeeId: employee.id, stageId: stage.id, name: employee.full_name, department: employee.department_name, reason: stage.review?.comment || stage.title, owner: employee.full_name, status: 'Нужна доработка' });
      else if (stage.kind === 'decision' && stage.status === 'available') result.push({ id: stage.id, employeeId: employee.id, stageId: stage.id, name: employee.full_name, department: employee.department_name, reason: 'Практика подтверждена. Нужно решение о самостоятельности.', owner: stage.owner_name, status: 'Ждёт решения' });
      else if (stage.status === 'available' && stage.due_date < state.today && !employee.blocker) result.push({ id: stage.id, employeeId: employee.id, stageId: stage.id, name: employee.full_name, department: employee.department_name, reason: stage.title, owner: stage.owner_name, status: `Срок прошёл · ${formatDate(stage.due_date)}` });
    }
    return result;
  }));
</script>

<section class="manager-queue" aria-labelledby="queue-title">
  <div class="queue-heading"><h2 id="queue-title">Требует внимания</h2><span>{rows.length} {rows.length === 1 ? 'вопрос' : rows.length > 1 && rows.length < 5 ? 'вопроса' : 'вопросов'} в учебном примере</span></div>
  {#if rows.length}
    <ul class="queue-list">
      {#each rows as row (row.id)}
        <li><button type="button" class="queue-item" onclick={() => onOpen(row.employeeId, row.stageId)}>
          <span><strong>{row.name}</strong><small>{row.department}</small></span>
          <span class="queue-reason">{row.reason}<small>{row.status}</small></span>
          <span class="queue-owner">Ответственный — {row.owner}</span>
          <span class="queue-arrow" aria-hidden="true">→</span>
        </button></li>
      {/each}
    </ul>
  {:else}
    <p class="queue-empty">Нет ожидающих решений и просроченных действий. Текущие этапы сотрудников доступны ниже.</p>
  {/if}
</section>
