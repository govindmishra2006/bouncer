// Captures the real running app into submission/screenshots/. Run with the Playwright MCP
// `browser_run_code` tool (or adapt to @playwright/test) while `make api` and `make web` are up.
async (page) => {
  const dir = '/Users/govindmishra/Nvidia Hackathon/submission/screenshots/';
  const main = (y) => page.locator('main').evaluate((el, y) => el.scrollTo(0, y), y);
  const open = async (text) => { await page.getByRole('button', { name: new RegExp(text) }).first().click(); await page.waitForTimeout(900); };
  const tab = async (name, y = 560) => { await page.getByRole('tab', { name }).click(); await page.waitForTimeout(300); await main(y); await page.waitForTimeout(300); };
  await page.emulateMedia({ colorScheme: 'light' });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.request.post('http://localhost:8000/api/demo/reset');
  await page.goto('http://localhost:3000/');
  const run = page.getByRole('button', { name: 'Run 10 test reports' });
  await run.waitFor();
  await page.screenshot({ path: dir + '01-first-run.png' });
  await run.click();
  await page.waitForTimeout(900);
  await page.screenshot({ path: dir + '02-queue-sorting-live.png' });
  await page.waitForFunction(async () => {
    const r = await fetch('http://localhost:8000/api/reports').then((r) => r.json());
    return r.stats.decided === 10 && r.stats.in_progress === 0;
  }, null, { timeout: 120000, polling: 1000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: dir + '03-queue-sorted.png' });
  await open('CRITICAL: Heap overflow');
  await page.screenshot({ path: dir + '04-fabricated-card.png' });
  await main(620); await page.waitForTimeout(300);
  await page.screenshot({ path: dir + '05-fabricated-evidence.png' });
  await open('Heap buffer over-read');
  await page.screenshot({ path: dir + '06-reproduced-card.png' });
  await tab('Sandbox'); await page.screenshot({ path: dir + '07-sandbox-asan.png' });
  await tab('Fix'); await page.screenshot({ path: dir + '08-patch-loop.png' });
  await main(1500); await page.waitForTimeout(300);
  await page.screenshot({ path: dir + '09-patch-checks.png' });
  await tab('Private advisory'); await page.screenshot({ path: dir + '10-private-advisory.png' });
  await tab('Models'); await page.screenshot({ path: dir + '11-model-panel.png' });
  await open('Use-after-free in tp_ini_free');
  await page.screenshot({ path: dir + '12-prompt-injection.png' });
  await page.emulateMedia({ colorScheme: 'dark' }); await page.waitForTimeout(300);
  await page.screenshot({ path: dir + '13-dark-mode.png' });
  await page.emulateMedia({ colorScheme: 'light' });
  await page.setViewportSize({ width: 390, height: 844 }); await page.waitForTimeout(500);
  await page.screenshot({ path: dir + '14-mobile.png' });
  await page.setViewportSize({ width: 1440, height: 900 });
  return 'ok';
}
