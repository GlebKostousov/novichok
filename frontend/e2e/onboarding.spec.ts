import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const initialAnswer = 'Предложу модель для зала до 6000 рублей и приглашу покупателя на примерку.';
const revisedAnswer = 'Уточню вид тренировок и размер. Для занятий в зале предложу модель из каталога в пределах 6000 рублей: объясню устойчивость подошвы и фиксацию стопы. Затем приглашу примерить обе полупары и пройтись.';

async function openEmployee(page: Page, name: string): Promise<void> {
  await expect(page.locator('#employee-select option').filter({ hasText: name })).toHaveCount(1);
  const button = page.getByRole('button', { name: `Открыть сотрудника ${name}`, exact: true });
  if (await button.isVisible()) {
    await button.click();
    return;
  }
  const select = page.locator('#employee-select');
  const option = select.locator('option').filter({ hasText: name });
  await select.selectOption(await option.getAttribute('value') ?? '');
}

async function openStage(page: Page, title: string): Promise<void> {
  const route = page.getByRole('navigation', { name: 'Маршрут адаптации' });
  const toggle = route.getByRole('button', { name: 'Весь маршрут ↓' });
  if (await toggle.isVisible()) await toggle.click();
  await route.getByRole('button', { name: new RegExp(title) }).click();
  await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
}

async function role(page: Page, name: string): Promise<void> {
  const current = (await page.locator('#employee-select option:checked').textContent())?.split(' · ')[0] ?? '';
  const suffix = ({ 'Сотрудник': 'сотрудника', 'Наставник': 'наставника', 'Руководитель': 'руководителя' } as Record<string, string>)[name];
  const contextual = page.locator('.work-panel').getByRole('button', { name: new RegExp(`в роли ${suffix}$`) });
  if (await contextual.count() && await contextual.first().isVisible()) await contextual.first().click();
  else {
    await page.getByRole('button', { name, exact: true }).click();
    if (current) await openEmployee(page, current);
  }
}

async function checkCriteria(page: Page): Promise<void> {
  const boxes = page.getByRole('checkbox');
  await expect(boxes).toHaveCount(3);
  for (const checkbox of await boxes.all()) await checkbox.check();
}

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await openEmployee(page, 'Анна Синицына');
  await expect(page.getByRole('heading', { name: 'Знание товара', exact: true })).toBeVisible();
});

test('замечание, повторная отправка, практика и решение сохраняются после перезагрузки', async ({ page }) => {
  await page.getByLabel('Ваш ответ покупателю').fill(initialAnswer);
  await page.getByRole('button', { name: 'Отправить наставнику', exact: true }).click();
  await expect(page.getByText('Ответ ждёт проверки', { exact: true })).toBeVisible();
  await role(page, 'Наставник');
  await expect(page.getByRole('button', { name: 'Подтвердить задание' })).toBeDisabled();
  await page.getByLabel('Комментарий наставника').fill('Уточните, какие именно тренировки планирует покупатель.');
  await page.getByRole('button', { name: 'Вернуть с замечанием' }).click();
  await role(page, 'Сотрудник');
  await expect(page.getByLabel('Ваш ответ покупателю')).toHaveValue(initialAnswer);
  await page.getByLabel('Ваш ответ покупателю').fill(revisedAnswer);
  await page.getByRole('button', { name: 'Отправить доработанный ответ' }).click();
  await role(page, 'Наставник');
  await expect(page.getByText('Ответ сотрудника · попытка 2')).toBeVisible();
  await checkCriteria(page);
  await page.getByRole('button', { name: 'Подтвердить задание' }).click();
  await openStage(page, 'Практика с наставником');
  await checkCriteria(page);
  await page.getByLabel('Результат практики').fill('Самостоятельно выяснила задачу, объяснила выбор и провела примерку.');
  await page.getByRole('button', { name: 'Подтвердить практику' }).click();
  await role(page, 'Руководитель');
  await page.getByLabel('Какие задачи сотрудник может выполнять сам?').fill('Допускаю к типовым консультациям. По нестандартному запросу обращается к наставнику.');
  await page.getByRole('button', { name: 'Подтвердить самостоятельность' }).click();
  await expect(page.getByText('Допуск к типовым задачам подтверждён', { exact: true })).toBeVisible();
  await page.reload();
  await openEmployee(page, 'Анна Синицына');
  await expect(page.getByText('Допуск к типовым задачам подтверждён', { exact: true })).toBeVisible();
  await expect(page.getByText('Подтверждено 4 из 4 этапов')).toBeVisible();
});

test('неподготовленные условия устраняет руководитель, затем наставник подтверждает практику', async ({ page }) => {
  await openEmployee(page, 'Мила Орлова');
  await role(page, 'Наставник');
  await expect(page.getByRole('heading', { name: 'Наставнику не выделено время для совместной консультации' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Подтвердить практику' })).toHaveCount(0);
  await role(page, 'Руководитель');
  await page.getByLabel('Что подготовили').fill('Согласовали время совместной консультации с наставником.');
  await page.getByRole('button', { name: 'Препятствие устранено' }).click();
  await expect(page.getByRole('heading', { name: 'Наставнику не выделено время для совместной консультации' })).toHaveCount(0);
  await role(page, 'Наставник');
  await checkCriteria(page);
  await page.getByLabel('Результат практики').fill('Провела консультацию и примерку без подсказок по стандартному запросу.');
  await page.getByRole('button', { name: 'Подтвердить практику' }).click();
  await expect(page.getByText('Этап подтверждён', { exact: true })).toBeVisible();
});

test('повтор кадрового события сохраняет одного новичка и его текущий маршрут', async ({ page }) => {
  await role(page, 'Руководитель');
  await page.getByRole('button', { name: 'Добавить новичка' }).click();
  await page.getByLabel('Имя и фамилия').fill('Олег Данилов');
  await page.getByLabel('Номер события').fill('browser-demo-hire');
  await page.getByRole('button', { name: 'Зафиксировать выход' }).click();
  await expect(page.getByRole('heading', { name: 'Первый день', exact: true })).toBeVisible();
  await role(page, 'Сотрудник');
  await page.getByRole('button', { name: 'Подтвердить прочтение' }).click();
  await expect(page.getByRole('heading', { name: 'Знание товара', exact: true })).toBeVisible();
  await role(page, 'Руководитель');
  await page.getByRole('button', { name: 'Повторить последнее событие' }).click();
  await expect(page.getByText(/Повтор события не создал второго сотрудника/)).toBeVisible();
  await expect(page.locator('#employee-select option').filter({ hasText: 'Олег Данилов' })).toHaveCount(1);
  await expect(page.getByText('Подтверждено 1 из 4 этапов')).toBeVisible();
});

test('устаревшее окно не перезаписывает отправленный ответ', async ({ page, context }) => {
  const second = await context.newPage();
  await second.goto('/');
  await openEmployee(second, 'Анна Синицына');
  await second.getByLabel('Ваш ответ покупателю').fill(initialAnswer);
  await page.getByLabel('Ваш ответ покупателю').fill(revisedAnswer);
  await page.getByRole('button', { name: 'Отправить наставнику', exact: true }).click();
  await expect(page.getByText('Ответ ждёт проверки', { exact: true })).toBeVisible();
  await second.getByRole('button', { name: 'Отправить наставнику', exact: true }).click();
  await expect(second.locator('.work-panel').getByRole('alert')).toContainText('Данные изменились в другом окне');
  await expect(second.getByText(revisedAnswer, { exact: true })).toBeVisible();
  await second.close();
});

test('сбой загрузки объясняется и позволяет повторить запрос', async ({ page }) => {
  await page.route('**/api/demo', route => route.abort('failed'));
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Не удалось загрузить данные' })).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('Не удалось связаться с сервисом');
  await page.unroute('**/api/demo');
  await page.getByRole('button', { name: 'Попробовать ещё раз' }).click();
  await openEmployee(page, 'Анна Синицына');
  await expect(page.getByLabel('Ваш ответ покупателю')).toBeVisible();
});

test('сброс подтверждается, другой браузер остаётся независимым', async ({ page, browser }) => {
  await page.getByLabel('Ваш ответ покупателю').fill(revisedAnswer);
  await page.getByRole('button', { name: 'Отправить наставнику', exact: true }).click();
  const otherContext = await browser.newContext();
  const other = await otherContext.newPage();
  await other.goto(page.url());
  await openEmployee(other, 'Анна Синицына');
  await expect(other.getByLabel('Ваш ответ покупателю')).toBeVisible();
  await page.getByRole('button', { name: 'Начать заново', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('button', { name: 'Продолжить работу' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(page.getByText('Ответ ждёт проверки', { exact: true })).toBeVisible();
  await other.getByLabel('Ваш ответ покупателю').fill(initialAnswer);
  await other.getByRole('button', { name: 'Отправить наставнику', exact: true }).click();
  await page.getByRole('button', { name: 'Начать заново', exact: true }).click();
  await dialog.getByRole('button', { name: 'Начать заново', exact: true }).click();
  await expect(page.getByLabel('Ваш ответ покупателю')).toBeVisible();
  await other.reload();
  await openEmployee(other, 'Анна Синицына');
  await expect(other.getByText(initialAnswer, { exact: true })).toBeVisible();
  await otherContext.close();
});
