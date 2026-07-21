import { expect, test, type Page, type Route } from '@playwright/test';

const productConfig = {
  id: 'e2e-products',
  version: 1,
  environments: [
    { label: '测试环境一', value: 'env-1' },
    { label: '测试环境二', value: 'env-2' },
  ],
  products: [
    {
      label: '测试产品',
      value: 'product-a',
      environments: ['env-1', 'env-2'],
      locations: [
        {
          label: '测试地区',
          value: 'location-a',
          branches: [
            {
              label: '测试机构',
              value: 'branch-a',
              outlets: [{ label: '测试网点', value: 'outlet-a' }],
            },
          ],
        },
      ],
      fieldSets: ['customer'],
      requiredFields: ['personName'],
    },
  ],
  fields: [
    { name: 'environment' },
    { name: 'product' },
    { name: 'location' },
    { name: 'branch' },
    { name: 'outlet' },
    { name: 'personName' },
    { name: 'whitelistEnabled', defaultValue: false },
  ],
  fieldSets: { customer: ['personName', 'whitelistEnabled'] },
  cascadeResetMap: {
    environment: ['product', 'location', 'branch', 'outlet'],
    product: ['location', 'branch', 'outlet'],
    location: ['branch', 'outlet'],
    branch: ['outlet'],
  },
};

const now = '2026-07-22T10:00:00+08:00';

function ok(data: unknown) {
  return { ok: true, message: '', data };
}

async function mockProductConfig(page: Page) {
  await page.route('**/api/product-data/applications/config', (route) =>
    route.fulfill({ json: ok(productConfig) }),
  );
}

function jobSubmission(id: number) {
  return { id, status: 'pending', stage: 'submitted', progress: 0 };
}

function verificationTask(overrides: Record<string, unknown> = {}) {
  return {
    id: 'task-e2e-1',
    contractNo: 'HT-E2E-001',
    ownershipStatus: 'unclaimed',
    taskStatus: '待核实',
    node: '核实审批',
    tellerNo: 'TELLER-007',
    organizationNo: 'ORG-001',
    productName: '测试产品',
    items: [{ id: 'item-1', title: '身份核实', status: 'pending' }],
    ...overrides,
  };
}

function verificationDetail(id: number, task: ReturnType<typeof verificationTask>, digest: string) {
  return {
    id,
    status: 'success',
    stage: 'completed',
    progress: 100,
    result: {
      task,
      contextProof: { sourceJobId: id, version: 1, digest },
    },
  };
}

async function readJson(route: Route) {
  return route.request().postDataJSON() as Record<string, unknown>;
}

test('产品申请提交后展示 Job 结果', async ({ page }) => {
  await mockProductConfig(page);
  let submittedPayload: Record<string, unknown> | undefined;
  await page.route('**/api/jobs/101', (route) =>
    route.fulfill({
      json: ok({
        id: 101,
        name: '测试产品-产品申请',
        workflowId: 'workflow-e2e-101',
        status: 'success',
        stage: 'completed',
        progress: 100,
        result: {},
        traceId: 'trace-e2e-101',
        idempotencyKey: 'e2e-101',
        attemptCount: 1,
        timeoutSeconds: 60,
        createdAt: now,
      }),
    }),
  );
  await page.route('**/api/jobs/101/logs/stream*', (route) =>
    route.fulfill({
      contentType: 'text/event-stream',
      body: 'event: status\ndata: {"status":"success","progress":100}\n\n',
    }),
  );
  await page.route('**/api/product-data/applications', async (route) => {
    submittedPayload = await readJson(route);
    await route.fulfill({
      json: ok({
        id: 101,
        name: '测试产品-产品申请',
        product: 'product-a',
        status: 'success',
        stage: 'completed',
        progress: 100,
        createdAt: now,
        logs: [],
        traceId: 'trace-e2e-101',
        idempotencyKey: 'e2e-101',
        attemptCount: 1,
      }),
    });
  });

  await page.goto('/#/product-data/product-application');
  await page.getByLabel('客户姓名').fill('端到端客户');
  await page.getByRole('button', { name: '执行' }).click();

  await expect(page.getByText('测试产品-产品申请').first()).toBeVisible();
  expect(submittedPayload).toMatchObject({
    product: 'product-a',
    payload: { personName: '端到端客户' },
  });
});

test('核实审批操作复用查询返回的完整上下文', async ({ page }) => {
  const actionBodies: Record<string, Record<string, unknown>> = {};
  const details = new Map<number, ReturnType<typeof verificationDetail>>();
  details.set(201, verificationDetail(201, verificationTask(), 'digest-search'));
  details.set(
    202,
    verificationDetail(
      202,
      verificationTask({ ownershipStatus: 'claimed', taskStatus: '核实中' }),
      'digest-claim',
    ),
  );
  details.set(
    203,
    verificationDetail(
      203,
      verificationTask({
        ownershipStatus: 'claimed',
        taskStatus: '核实完成',
        items: [{ id: 'item-1', title: '身份核实', status: 'completed' }],
      }),
      'digest-complete',
    ),
  );
  details.set(
    204,
    verificationDetail(
      204,
      verificationTask({
        ownershipStatus: 'claimed',
        taskStatus: '已提交',
        items: [{ id: 'item-1', title: '身份核实', status: 'completed' }],
      }),
      'digest-submit',
    ),
  );

  await page.route('**/api/product-data/verification-approval/config', (route) =>
    route.fulfill({ json: ok({ environments: ['测试环境'], categories: ['贷款'] }) }),
  );
  await page.route('**/api/product-data/verification-approval/search', (route) =>
    route.fulfill({ json: ok(jobSubmission(201)) }),
  );
  await page.route('**/api/product-data/verification-approval/task-e2e-1/claim', async (route) => {
    actionBodies.claim = await readJson(route);
    await route.fulfill({ json: ok(jobSubmission(202)) });
  });
  await page.route(
    '**/api/product-data/verification-approval/task-e2e-1/actions/complete',
    async (route) => {
      actionBodies.complete = await readJson(route);
      await route.fulfill({ json: ok(jobSubmission(203)) });
    },
  );
  await page.route(
    '**/api/product-data/verification-approval/task-e2e-1/actions/submit',
    async (route) => {
      actionBodies.submit = await readJson(route);
      await route.fulfill({ json: ok(jobSubmission(204)) });
    },
  );
  await page.route('**/api/jobs/*', (route) => {
    const id = Number(new URL(route.request().url()).pathname.split('/').pop());
    return route.fulfill({ json: ok(details.get(id)) });
  });

  await page.goto('/#/product-data/verification-approval');
  await page.getByLabel('合同号').fill('HT-E2E-001');
  await page.getByRole('button', { name: '搜索' }).click();
  await expect(page.getByText('柜员号：TELLER-007')).toBeVisible();

  await page.getByRole('button', { name: '领取', exact: true }).click();
  await expect(page.getByText('领取状态：已领取')).toBeVisible();

  await page.getByRole('button', { name: '一键完成' }).click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /^确\s*定$/ })
    .click();
  await expect(page.getByText('任务状态：核实完成')).toBeVisible();

  await page.getByRole('button', { name: '一键提交' }).click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /^确\s*定$/ })
    .click();
  await expect(page.getByText('任务状态：已提交')).toBeVisible();

  expect(actionBodies.claim).toMatchObject({
    context: { tellerNo: 'TELLER-007', organizationNo: 'ORG-001' },
    contextProof: { sourceJobId: 201, digest: 'digest-search' },
  });
  expect(actionBodies.complete).toMatchObject({
    context: { tellerNo: 'TELLER-007', organizationNo: 'ORG-001' },
    contextProof: { sourceJobId: 202, digest: 'digest-claim' },
  });
  expect(actionBodies.submit).toMatchObject({
    context: { tellerNo: 'TELLER-007', organizationNo: 'ORG-001' },
    contextProof: { sourceJobId: 203, digest: 'digest-complete' },
  });
});

test('同一菜单多标签切换时隔离并恢复表单缓存', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem(
      'alioth_page_multi_open_by_menu',
      JSON.stringify({ 'product-application': true }),
    );
  });
  await mockProductConfig(page);
  await page.goto('/#/product-data/product-application');

  await page.getByLabel('环境').focus();
  await page.getByLabel('环境').press('ArrowDown');
  await page.getByText('测试环境二', { exact: true }).last().click();
  await page.getByText('产品申请', { exact: true }).first().click();

  await expect(page.getByRole('tab', { name: '产品申请-1' })).toBeVisible();
  await expect(page.getByRole('tab', { name: '产品申请-2' })).toBeVisible();
  await expect(page.locator('.ant-tabs-tabpane-active [title="测试环境一"]')).toBeVisible();

  await page.getByRole('tab', { name: '产品申请-1' }).click();
  await expect(page.locator('.ant-tabs-tabpane-active [title="测试环境二"]')).toBeVisible();
  const cachedDrafts = await page.evaluate(() =>
    Object.keys(sessionStorage)
      .filter((key) => key.startsWith('alioth:product-application-form:'))
      .map((key) => sessionStorage.getItem(key)),
  );
  expect(cachedDrafts.some((value) => value?.includes('env-2'))).toBe(true);
});
