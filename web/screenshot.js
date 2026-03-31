import puppeteer from 'puppeteer';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

(async () => {
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });

  // 截图 - 总览页面
  await page.goto('http://localhost:4173', { waitUntil: 'networkidle0' });
  await sleep(2000);
  await page.screenshot({
    path: path.join(__dirname, 'screenshot-overview.png'),
    fullPage: true
  });
  console.log('截图 1: 总览页面已保存');

  // 点击因子 Tab 截图
  await page.evaluate(() => {
    const buttons = document.querySelectorAll('button');
    buttons.forEach(btn => {
      if (btn.textContent.includes('因子')) btn.click();
    });
  });
  await sleep(1000);
  await page.screenshot({
    path: path.join(__dirname, 'screenshot-factors.png'),
    fullPage: true
  });
  console.log('截图 2: 因子页面已保存');

  // 点击回测 Tab 截图
  await page.evaluate(() => {
    const buttons = document.querySelectorAll('button');
    buttons.forEach(btn => {
      if (btn.textContent.includes('回测')) btn.click();
    });
  });
  await sleep(1000);
  await page.screenshot({
    path: path.join(__dirname, 'screenshot-backtest.png'),
    fullPage: true
  });
  console.log('截图 3: 回测页面已保存');

  await browser.close();
  console.log('所有截图已完成');
})();
