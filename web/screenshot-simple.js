const puppeteer = require('puppeteer');
const path = require('path');

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

(async () => {
  console.log('启动浏览器...');
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/usr/bin/chromium',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  }).catch(async () => {
    console.log('Chromium 未找到，使用默认浏览器...');
    return puppeteer.launch({
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
    });
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  console.log('访问页面...');
  await page.goto('http://localhost:4173', {
    waitUntil: 'networkidle0',
    timeout: 30000
  });

  console.log('等待页面渲染...');
  await sleep(3000);

  // 截图 - 总览页面
  console.log('截图 1: 总览页面');
  await page.screenshot({
    path: path.join(__dirname, 'screenshot-overview.png'),
    fullPage: false
  });

  await browser.close();
  console.log('截图完成！');
})();
