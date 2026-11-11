import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

async function selectPerson(page: Page, name: string) {
  const button = page.getByRole('button', { name: `Открыть сотрудника ${name}`, exact: true });
  if (await button.isVisible()) await button.click();
  else {
    const option = page.locator('#employee-select option').filter({ hasText: name });
    await page.locator('#employee-select').selectOption(await option.getAttribute('value') ?? '');
  }
}

test('черновик ответа восстанавливается после перехода и F5', async ({ page }) => {
  await page.goto('/');
  const answer = page.getByLabel('Ваш ответ покупателю');
  await answer.fill('Уточню вид тренировок и предложу подходящую модель из учебного каталога.');
  await expect(page.getByText('Черновик сохранён на сервере', { exact: true })).toBeVisible();
  const route = page.getByRole('navigation', { name: 'Маршрут адаптации' });
  const toggle = route.getByRole('button', { name: 'Весь маршрут ↓' });
  if (await toggle.isVisible()) await toggle.click();
  await route.getByRole('button', { name: /Первый день/ }).click();
  await expect(page.getByText('Первый день в магазине', { exact: true })).toBeVisible();
  if (await toggle.isVisible()) await toggle.click();
  await route.getByRole('button', { name: /Знание товара/ }).click();
  await expect(answer).toHaveValue(/Уточню вид тренировок/);
  await page.reload();
  await expect(answer).toHaveValue(/Уточню вид тренировок/);
});

test('ошибка отправки доступна возле формы и ввод сохраняется', async ({ page }) => {
  await page.goto('/');
  const answer = page.getByLabel('Ваш ответ покупателю');
  await answer.fill('Предложу Arena Flex для тренировок в зале и приглашу примерить обе полупары.');
  await page.route('**/api/employees/**/submit', route => route.abort());
  await page.getByRole('button', { name: 'Отправить наставнику', exact: true }).click();
  const error = page.locator('.work-panel .inline-error').filter({ hasText: 'Проверьте соединение' });
  await expect(error).toBeVisible();
  await expect(error).toBeFocused();
  await expect(answer).toHaveValue(/Arena Flex/);
});

test('черновик наставника сохраняет комментарий и критерии при F5', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Наставник', exact: true }).click();
  await expect(page.locator('.work-header')).toContainText('Дмитрий Белов');
  await expect(page.locator('#employee-select option:checked')).toContainText('Ждёт проверки');
  await page.getByLabel('Комментарий наставника').fill('Добавьте приглашение примерить обе полупары.');
  await page.getByRole('checkbox').first().check();
  await expect(page.getByText('Черновик сохранён на сервере', { exact: true })).toBeVisible();
  await selectPerson(page, 'Анна Синицына');
  await selectPerson(page, 'Дмитрий Белов');
  await expect(page.getByLabel('Комментарий наставника')).toHaveValue(/приглашение примерить/);
  await page.reload();
  await expect(page.getByLabel('Комментарий наставника')).toHaveValue(/приглашение примерить/);
  await expect(page.getByRole('checkbox').first()).toBeChecked();
});

test('черновики найма и устранения препятствия переживают F5', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Руководитель', exact: true }).click();
  await expect(page.locator('.queue-owner').filter({ hasText: 'Павел Соколов' })).toBeVisible();
  await page.getByRole('button', { name: 'Добавить новичка' }).click();
  await page.getByLabel('Имя и фамилия').fill('Учебный Сотрудник');
  await page.getByLabel('Номер события').fill('draft-hire');
  await expect(page.locator('.hire-panel').getByText('Черновик сохранён на сервере', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Отмена', exact: true }).click();
  await page.getByRole('button', { name: 'Добавить новичка' }).click();
  await expect(page.getByLabel('Номер события')).toHaveValue('draft-hire');
  await page.reload();
  await page.getByRole('button', { name: 'Добавить новичка' }).click();
  await expect(page.getByLabel('Имя и фамилия')).toHaveValue('Учебный Сотрудник');
  await selectPerson(page, 'Мила Орлова');
  await page.getByLabel('Что подготовили').fill('Согласовано время консультации с наставником.');
  await expect(page.locator('.blocker-section').getByText('Черновик сохранён на сервере', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('Что подготовили')).toHaveValue(/Согласовано время консультации/);
});
