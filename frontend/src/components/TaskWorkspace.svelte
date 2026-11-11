<script lang="ts">
  import { getContext, untrack, tick } from 'svelte';
  import { emptyFields } from '../lib/drafts.svelte';
  import type { DraftEntry, DraftStore } from '../lib/drafts.svelte';
  import DraftStatus from './DraftStatus.svelte';
  import MaterialView from './MaterialView.svelte';
  import BlockerNotice from './BlockerNotice.svelte';
  import { formatDate, formatTime, roleLabels, stageStatusLabels } from '../lib/types';
  import type { ActionFields, Activity, DemoRole, Employee, Material, Stage, StageAction } from '../lib/types';

  interface Props {
    employee: Employee;
    stage: Stage;
    material: Material | undefined;
    activities: Activity[];
    role: DemoRole;
    today: string;
    busy: boolean;
    actionError: string;
    onAction: (action: StageAction, fields?: ActionFields) => Promise<boolean>;
    onResolveBlocker: (comment: string) => Promise<boolean>;
    onSelectStage: (id: string) => void;
    onRoleChange: (role: DemoRole) => void;
  }
  let { employee, stage, material, activities, role, today, busy, actionError, onAction, onResolveBlocker, onSelectStage, onRoleChange }: Props = $props();
  const drafts = getContext<DraftStore>('drafts');
  let draft = $state<DraftEntry>();
  let form = $derived(draft?.fields ?? emptyFields());
  let localError: HTMLParagraphElement | undefined = $state();
  let error = $state('');
  let lastContext = $state('');
  let index = $derived(employee.stages.findIndex(item => item.id === stage.id));
  let nextStage = $derived(employee.stages[index + 1]);
  let previousStage = $derived(employee.stages[index - 1]);
  let allChecked = $derived(stage.criteria.length > 0 && stage.criteria.every(criterion => form.checked.includes(criterion.id)));
  let overdue = $derived(stage.status !== 'locked' && stage.status !== 'completed' && stage.due_date < today);
  let history = $derived(activities.filter(activity => activity.employee_id === employee.id).sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 10));

  $effect(() => {
    const context = `${employee.id}:${stage.id}:${role}`;
    if (context === lastContext) return;
    lastContext = context;
    const editable = stage.kind === 'assignment' && (role === 'employee' || role === 'mentor') || stage.kind === 'observation' && role === 'mentor' || stage.kind === 'decision' && role === 'manager';
    untrack(() => {
      draft = editable ? drafts.get(context, role, { answer: role === 'employee' && stage.status === 'revision_requested' ? stage.submission?.text ?? '' : '' }) : undefined;
    });
    error = '';
  });

  $effect(() => {
    const fields = JSON.stringify(form);
    if (draft && fields) untrack(() => drafts.changed(draft!));
  });

  $effect(() => {
    if (actionError || error) void tick().then(() => localError?.focus());
  });

  async function act(action: StageAction, fields: ActionFields = {}) {
    const current = draft;
    const successful = await onAction(action, fields);
    if (successful && current) await drafts.clear(current);
  }

  async function submitAnswer(event: SubmitEvent) {
    event.preventDefault();
    error = '';
    if (form.answer.trim().length < 30) { error = 'Добавьте объяснение выбора и следующий шаг: не меньше 30 символов.'; return; }
    await act('submit', { text: form.answer.trim() });
  }

  async function review(decision: 'approved' | 'changes_requested') {
    error = '';
    if (decision === 'changes_requested' && form.comment.trim().length < 10) { error = 'Напишите конкретное замечание для доработки: не меньше 10 символов.'; return; }
    if (decision === 'approved' && !allChecked) { error = 'Перед подтверждением проверьте все три критерия.'; return; }
    await act('review', { decision, comment: form.comment.trim(), checked_criteria: form.checked });
  }

  async function observe(event: SubmitEvent) {
    event.preventDefault();
    error = '';
    if (!allChecked) { error = 'Подтвердите каждый обязательный критерий наблюдения.'; return; }
    if (form.comment.trim().length < 10) { error = 'Опишите результат наблюдения: не меньше 10 символов.'; return; }
    await act('observe', { comment: form.comment.trim(), checked_criteria: form.checked });
  }

  async function approve(event: SubmitEvent) {
    event.preventDefault();
    error = '';
    if (form.comment.trim().length < 10) { error = 'Укажите основание решения: не меньше 10 символов.'; return; }
    await act('approve', { comment: form.comment.trim() });
  }
</script>

<section class="work-panel" aria-labelledby="task-title" aria-busy={busy}>
  <div class="work-header">
    <span class="eyebrow">{employee.full_name} <span aria-hidden="true">·</span> Этап {index + 1} из {employee.stages.length}</span>
    <h2 id="task-title" tabindex="-1">{stage.title}</h2>
    <p class="description">{stage.description}</p>
    <div class="work-meta">
      <span class="status-tag" class:completed={stage.status === 'completed'} class:returned={stage.status === 'revision_requested'} class:locked={stage.status === 'locked'}>{stageStatusLabels[stage.status]}</span>
      <span class:overdue>До {formatDate(stage.due_date)}{overdue ? ' · срок прошёл' : ''}</span>
      <span>{stage.owner_name}</span>
    </div>
  </div>
  <div class="work-body">
    {#if employee.blocker && stage.status !== 'completed' && stage.status !== 'locked'}
      <BlockerNotice {employee} {role} {busy} {actionError} onResolve={onResolveBlocker} {onRoleChange} />
    {/if}

    {#if stage.status === 'locked'}
      <div class="locked-state">
        <span class="eyebrow">Следующий шаг маршрута</span>
        <h3>Сначала подтвердите предыдущий этап</h3>
        <p>{previousStage ? `«${previousStage.title}» ещё не завершён. Срок сам по себе не открывает этот шаг.` : 'Этот этап пока недоступен.'}</p>
        {#if previousStage}<div class="form-actions"><button type="button" class="button button-secondary" onclick={() => onSelectStage(previousStage.id)}>К предыдущему этапу</button></div>{/if}
      </div>
    {:else if stage.status === 'completed'}
      <div class="notice success">
        <strong>{stage.kind === 'decision' ? 'Допуск к типовым задачам подтверждён' : 'Этап подтверждён'}</strong>
        <p>{stage.kind === 'decision' ? 'Учебный маршрут пройден. Допуск относится к типовым консультациям.' : nextStage ? `Открыт следующий шаг: «${nextStage.title}».` : 'Результат сохранён в истории.'}</p>
      </div>
      {#if material}<MaterialView {material} collapsed />{/if}
      {#if stage.review}
        <p class="section-label">{stage.review.reviewer_name} · {formatTime(stage.review.reviewed_at)}</p>
        {#if stage.review.comment}<div class="answer-block">{stage.review.comment}</div>{/if}
      {/if}
      {#if stage.submission}<p class="section-label">Ответ сотрудника</p><div class="answer-block">{stage.submission.text}</div>{/if}
      {#if nextStage}<button type="button" class="button button-primary" onclick={() => onSelectStage(nextStage.id)}>Перейти к следующему этапу <span aria-hidden="true">→</span></button>{/if}
    {:else}
      {#if stage.instructions}
        <div class="scenario"><p class="section-label">{stage.kind === 'assignment' ? 'Ситуация покупателя' : 'Что предстоит сделать'}</p><p>{stage.instructions}</p></div>
      {/if}
      {#if material && stage.kind !== 'assignment'}<MaterialView {material} collapsed={role !== 'employee'} />{/if}

      {#if stage.kind === 'acknowledgement'}
        {#if role === 'employee'}
          <p class="action-note">Подтвердите, что ознакомились с порядком первого дня. После этого откроется задание по подбору товара.</p>
          <div class="form-actions"><button type="button" class="button button-primary" onclick={() => act('acknowledge')} disabled={busy}>{busy ? 'Сохраняем…' : 'Подтвердить прочтение'}</button></div>
        {:else}
          <div class="notice"><strong>Сейчас действие сотрудника</strong><p>Он знакомится с первым днём и подтверждает прочтение.</p></div>
          <button type="button" class="button button-secondary" onclick={() => onRoleChange('employee')} disabled={busy}>Открыть в роли сотрудника</button>
        {/if}
      {:else if stage.kind === 'assignment'}
        {#if stage.status === 'revision_requested' && stage.review}
          <div class="notice warning"><strong>Что доработать · {stage.review.reviewer_name}</strong><p>{stage.review.comment}</p></div>
        {/if}
        {#if (stage.status === 'available' || stage.status === 'revision_requested') && role === 'employee'}
          <h3 class="section-label">Наставник проверит три вещи</h3>
          <ol class="requirements">{#each stage.criteria as criterion}<li>{criterion.label}</li>{/each}</ol>
          <form onsubmit={submitAnswer}>
            <label for="employee-answer" class="field-label">Ваш ответ покупателю</label>
            <textarea id="employee-answer" bind:value={form.answer} minlength="30" maxlength="2000" required disabled={busy} aria-describedby="answer-help" placeholder="Что вы уточните, какую модель предложите и почему? Чем закончите консультацию?"></textarea>
            {#if material}<MaterialView {material} collapsed label="Свериться с каталогом" />{/if}
            <div id="answer-help" class="field-help"><span>От 30 до 2000 символов. Ответ проверяет наставник.</span><span class="counter">{form.answer.length}/2000</span></div>
            {#if error || actionError}<p class="inline-error" role="alert" tabindex="-1" bind:this={localError}>{error || actionError}</p>{/if}
            <div class="form-actions"><button type="submit" class="button button-primary" disabled={busy}>{busy ? 'Отправляем…' : stage.status === 'revision_requested' ? 'Отправить доработанный ответ' : 'Отправить наставнику'}</button><span class="action-note">Практика откроется после проверки.</span></div>
          </form>
        {:else if stage.status === 'awaiting_review' && stage.submission}
          {#if material}<MaterialView {material} collapsed label="Свериться с каталогом" />{/if}
          <p class="section-label">Ответ сотрудника · попытка {stage.submission.attempt}</p>
          <div class="answer-block">{stage.submission.text}</div>
          {#if role === 'mentor'}
            <fieldset class="review-checks" disabled={busy}><legend>Подтвердите выполненные критерии</legend>{#each stage.criteria as criterion}<label class="criterion"><input type="checkbox" value={criterion.id} bind:group={form.checked} /><span class="criterion-label">{criterion.label}</span></label>{/each}</fieldset>
            <p class="review-hint">Для возврата напишите, что исправить.</p>
            <label for="review-comment" class="field-label">Комментарий наставника</label>
            <textarea id="review-comment" bind:value={form.comment} maxlength="1000" disabled={busy} rows="3" aria-describedby="review-help"></textarea>
            <div id="review-help" class="field-help"><span>При возврате — от 10 до 1000 символов.</span><span class="counter">{form.comment.length}/1000</span></div>
            {#if error || actionError}<p class="inline-error" role="alert" tabindex="-1" bind:this={localError}>{error || actionError}</p>{/if}
            <div class="form-actions"><button type="button" class="button button-primary" onclick={() => review('approved')} disabled={busy || !allChecked}>{busy ? 'Сохраняем…' : 'Подтвердить задание'}</button><button type="button" class="button button-return" onclick={() => review('changes_requested')} disabled={busy}>Вернуть с замечанием</button></div>
          {:else}
            <div class="notice"><strong>Ответ ждёт проверки</strong><p>Наставник сверит его с тремя критериями и подтвердит задание или вернёт с конкретным замечанием.</p></div>
            <button type="button" class="button button-secondary" onclick={() => onRoleChange('mentor')} disabled={busy}>Проверить в роли наставника</button>
          {/if}
        {:else}
          <div class="notice"><strong>{stage.status === 'revision_requested' ? 'Сотрудник дорабатывает ответ' : 'Сотрудник готовит ответ'}</strong><p>Проверка появится после отправки задания.</p></div>
          <button type="button" class="button button-secondary" onclick={() => onRoleChange('employee')} disabled={busy}>Открыть в роли сотрудника</button>
        {/if}
      {:else if stage.kind === 'observation'}
        {#if employee.blocker}
          <p class="action-note">Проверка практики пока недоступна: сначала руководитель фиксирует подготовку условий.</p>
        {:else if role === 'mentor'}
          <form onsubmit={observe}>
            <fieldset class="review-checks" disabled={busy}><legend>Что вы наблюдали в консультации</legend>{#each stage.criteria as criterion}<label class="criterion"><input type="checkbox" value={criterion.id} bind:group={form.checked} /><span class="criterion-label">{criterion.label}</span></label>{/each}</fieldset>
            <label for="practice-comment" class="field-label">Результат практики</label>
            <textarea id="practice-comment" bind:value={form.comment} minlength="10" maxlength="1000" required disabled={busy} rows="3" placeholder="Какие действия сотрудник выполнил самостоятельно? Что вы проверили?"></textarea>
            <div class="field-help"><span>От 10 до 1000 символов.</span><span class="counter">{form.comment.length}/1000</span></div>
            {#if error || actionError}<p class="inline-error" role="alert" tabindex="-1" bind:this={localError}>{error || actionError}</p>{/if}
            <div class="form-actions"><button type="submit" class="button button-primary" disabled={busy || !allChecked}>{busy ? 'Сохраняем…' : 'Подтвердить практику'}</button></div>
          </form>
        {:else}
          <h3 class="section-label">Критерии наблюдения</h3><ol class="requirements">{#each stage.criteria as criterion}<li>{criterion.label}</li>{/each}</ol>
          <div class="notice"><strong>Практику подтверждает наставник</strong><p>Он наблюдает консультацию и фиксирует результат по каждому критерию.</p></div>
          <button type="button" class="button button-secondary" onclick={() => onRoleChange('mentor')} disabled={busy}>Открыть в роли наставника</button>
        {/if}
      {:else if stage.kind === 'decision'}
        {#if employee.blocker}
          <p class="action-note">Для решения сначала нужно устранить препятствие со стороны магазина.</p>
        {:else if role === 'manager'}
          <div class="notice success"><strong>Предыдущие этапы подтверждены</strong><p>Ознакомление, подбор товара и наблюдаемая практика завершены. Решение о самостоятельности принимает руководитель.</p></div>
          <form onsubmit={approve}>
            <label for="decision-comment" class="field-label">Какие задачи сотрудник может выполнять сам?</label>
            <textarea id="decision-comment" bind:value={form.comment} minlength="10" maxlength="1000" required disabled={busy} rows="3" placeholder="К каким типовым задачам допускаете сотрудника? В каких случаях обращаться за помощью?"></textarea>
            <div class="field-help"><span>От 10 до 1000 символов.</span><span class="counter">{form.comment.length}/1000</span></div>
            {#if error || actionError}<p class="inline-error" role="alert" tabindex="-1" bind:this={localError}>{error || actionError}</p>{/if}
            <div class="form-actions"><button type="submit" class="button button-primary" disabled={busy}>{busy ? 'Сохраняем…' : 'Подтвердить самостоятельность'}</button></div>
          </form>
        {:else}
          <div class="notice"><strong>Практика подтверждена, нужно решение руководителя</strong><p>Он проверяет результаты и определяет границы самостоятельной работы.</p></div>
          <button type="button" class="button button-secondary" onclick={() => onRoleChange('manager')} disabled={busy}>Открыть в роли руководителя</button>
        {/if}
      {/if}
    {/if}

    <DraftStatus {draft} />
    {#if actionError && draft && (stage.status === 'completed' || stage.status === 'awaiting_review' && role === 'employee')}
      <p class="inline-error" role="alert" tabindex="-1" bind:this={localError}>{actionError}</p>
      <details><summary>Ввод из этой вкладки</summary><div class="answer-block">{form.answer || form.comment}</div></details>
    {/if}
    {#if history.length}
      <details class="history"><summary>История действий · {history.length}</summary><ol class="history-list">{#each history as activity (activity.id)}<li class="history-entry"><strong>{activity.actor_name}</strong><p>{activity.text}</p><time datetime={activity.created_at}>{formatTime(activity.created_at)}</time></li>{/each}</ol></details>
    {/if}
  </div>
</section>
