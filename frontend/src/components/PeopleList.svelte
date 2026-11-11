<script lang="ts">
  import { formatDate, stageStatusLabels, workingStage } from '../lib/types';
  import type { DemoRole, Employee } from '../lib/types';

  interface Props {
    employees: Employee[];
    selectedId: string;
    role: DemoRole;
    onSelect: (id: string) => void;
  }
  let { employees, selectedId, role, onSelect }: Props = $props();
  let title = $derived(role === 'employee' ? 'Сотрудники в демо' : role === 'mentor' ? 'Подопечные' : 'Команда');

  function initials(name: string): string {
    return name.split(' ').filter(Boolean).slice(0, 2).map(part => part[0]).join('');
  }
</script>

<aside class="people-panel" aria-label={title}>
  <div class="panel-label"><h2>{title}</h2><span>{employees.length}</span></div>
  <div class="mobile-person-select">
    <label for="employee-select">{title}</label>
    <select id="employee-select" value={selectedId} onchange={(event) => onSelect(event.currentTarget.value)}>
      {#each employees as employee}
        <option value={employee.id}>{employee.full_name} · {employee.blocker ? employee.blocker.reason : workingStage(employee, role) ? stageStatusLabels[workingStage(employee, role)!.status] : 'Маршрут не назначен'} · {employee.department_name}</option>
      {/each}
    </select>
  </div>
  <div class="people-list">
    {#each employees as employee (employee.id)}
      {@const current = workingStage(employee, role)}
      <button type="button" class="person-button" class:selected={selectedId === employee.id} aria-label={`Открыть сотрудника ${employee.full_name}`} aria-pressed={selectedId === employee.id} onclick={() => onSelect(employee.id)}>
        <span class="person-initials" aria-hidden="true">{initials(employee.full_name)}</span>
        <span class="person-info">
          <span class="person-name">{employee.full_name}</span>
          <span class="person-detail">{employee.department_name}</span>
          <span class="person-detail">Выход {formatDate(employee.start_date)}</span>
          <span class="person-state" class:returned={employee.blocker !== null || current?.status === 'revision_requested'}>
            {employee.blocker ? employee.blocker.reason : current ? stageStatusLabels[current.status] : 'Маршрут не назначен'}
          </span>
        </span>
      </button>
    {/each}
  </div>
  <p class="sidebar-note">Выберите человека и пройдите его маршрут в разных ролях. Изменения сохраняются в вашем учебном примере.</p>
</aside>
