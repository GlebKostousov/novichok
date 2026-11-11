<script lang="ts">
  interface Props {
    open: boolean;
    busy: boolean;
    onCancel: () => void;
    onConfirm: () => void;
  }

  let { open, busy, onCancel, onConfirm }: Props = $props();
  let dialog: HTMLDialogElement;
  let cancelButton: HTMLButtonElement;

  $effect(() => {
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
      cancelButton?.focus();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  });
</script>

<dialog
  bind:this={dialog}
  class="reset-dialog"
  aria-labelledby="reset-title"
  aria-describedby="reset-description"
  oncancel={(event) => { event.preventDefault(); if (!busy) onCancel(); }}
  onclose={onCancel}
>
  <span class="eyebrow">Ваш учебный пример</span>
  <h2 id="reset-title">Начать демо заново?</h2>
  <p id="reset-description">Ответы, проверки и изменения в вашем примере будут удалены. Вернутся исходные вымышленные сотрудники и задания.</p>
  <div class="dialog-actions">
    <button bind:this={cancelButton} type="button" class="button button-secondary" onclick={onCancel} disabled={busy}>Продолжить работу</button>
    <button type="button" class="button button-primary" onclick={onConfirm} disabled={busy}>{busy ? 'Восстанавливаем…' : 'Начать заново'}</button>
  </div>
</dialog>
