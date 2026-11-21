// Run with Node 22+ and an existing local Chrome installation.
// Uses a temporary profile and read-only authenticated page navigation.
// Does not create customers, modify records, or print credentials.
import { spawn } from 'node:child_process';
import { openSync, closeSync } from 'node:fs';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const base = (process.env.AUDIT_BASE_URL || 'http://192.168.0.155:8043').replace(/\/$/, '');
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const credentialsFile = process.env.AUDIT_CREDENTIALS_FILE;
const fixtureFile = process.env.AUDIT_FIXTURE_FILE;
const directory = await mkdtemp(join(tmpdir(), 'creator-browser-smoke-'));
let chrome, socket;
let requestId = 0;
const pending = new Map();
const sleep = (n) => new Promise((resolve) => setTimeout(resolve, n));
const insist = (ok, message) => { if (!ok) throw Error(message); };

function connect(url) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url);
    ws.addEventListener('open', () => resolve(ws), { once: true });
    ws.addEventListener('error', reject, { once: true });
    ws.addEventListener('message', event => {
      const packet = JSON.parse(event.data);
      if (packet.id && pending.has(packet.id)) {
        const task = pending.get(packet.id);
        pending.delete(packet.id);
        if (packet.error) task.reject(Error(JSON.stringify(packet.error)));
        else task.resolve(packet.result);
      }
    });
  });
}
async function send(method, params = {}) {
  const id = ++requestId;
  const p = new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
  socket.send(JSON.stringify({ id, method, params }));
  return Promise.race([p, sleep(20000).then(() => { throw Error('CDP timed out: ' + method); })]);
}
async function evalPage(expression) {
  const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw Error(JSON.stringify(r.exceptionDetails));
  return r.result.value;
}
async function waitFor(predicate, detail, attempts = 65) {
  for (let i=0;i<attempts;i++) {
    if (await evalPage(predicate)) return;
    await sleep(200);
  }
  throw Error('Browser did not reach ' + detail);
}
async function navigate(path) {
  await send('Page.navigate', { url: base + path });
  await waitFor('document.readyState === "complete" && !!document.querySelector("main")', path);
}
function luminance(rgb) {
  const c = rgb.match(/[\d.]+/g)?.slice(0,3).map(Number) || [0,0,0];
  const linear = c.map(v => { v/=255; return v<=0.04045 ? v/12.92 : ((v+0.055)/1.055)**2.4; });
  return .2126*linear[0] + .7152*linear[1] + .0722*linear[2];
}
function ratio(a,b) {
  const x = luminance(a), y = luminance(b);
  return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05);
}
async function checkPage(name) {
  const state = await evalPage(`(() => ({
    title: document.title,
    heading: document.querySelector('main h1')?.textContent?.trim() || '',
    h1Color: getComputedStyle(document.querySelector('main h1')).color,
    bodyBackground: getComputedStyle(document.body).backgroundColor,
    viewport: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    skipLink: !!document.querySelector('a.skip[href="#main"]'),
    mainLandmarks: document.querySelectorAll('main, [role="main"]').length,
    missingImageAlt: document.querySelectorAll('img:not([alt])').length,
    invalidForms: Array.from(document.forms).filter(f => f.method.toLowerCase() === 'post' && !f.querySelector('input[name="csrfmiddlewaretoken"]')).length,
    focused: !!document.activeElement,
  }))()`);
  insist(state.heading, name + ': no main heading');
  insist(state.skipLink, name + ': missing skip-to-content link');
  insist(state.mainLandmarks===1, name + ': duplicate or missing main landmark');
  insist(state.invalidForms===0, name + ': form missing CSRF field');
  insist(state.missingImageAlt===0, name + ': images without alt text');
  insist(state.scrollWidth <= state.viewport + 2, name + ': horizontal document overflow');
  insist(ratio(state.h1Color,state.bodyBackground)>=3, name + ': heading/background contrast below 3:1');
  return { page: name, heading: state.heading, viewport: state.viewport, contrast: Number(ratio(state.h1Color,state.bodyBackground).toFixed(2)), horizontalOverflow: false };
}

try {
  // CI runner startup may be slow or Chrome may exit before writing the debugger port.
  // Keep an ephemeral profile for each attempt; never relax the browser sandbox.
  let port;
  let startupError = '';
  for (let attempt = 1; attempt <= 2 && !port; attempt++) {
    const profile = join(directory, 'profile-' + attempt);
    const logPath = join(directory, 'chrome-' + attempt + '.log');
    const stderrFd = openSync(logPath, 'w', 0o600);
    let spawnError;
    chrome = spawn(chromePath, [
      '--headless=new', '--disable-gpu', '--disable-extensions', '--disable-dev-shm-usage',
      '--no-first-run', '--no-default-browser-check', '--remote-debugging-address=127.0.0.1',
      '--remote-debugging-port=0', '--user-data-dir=' + profile,
      '--window-size=1280,900', 'about:blank',
    ], { stdio: ['ignore', 'ignore', stderrFd] });
    closeSync(stderrFd);
    chrome.on('error', error => { spawnError = error.message; });
    for (let i=0;i<200;i++) {
      try {
        const value = Number((await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]);
        if (Number.isInteger(value) && value > 0) { port = value; break; }
      } catch { /* startup still in progress */ }
      if (spawnError || chrome.exitCode !== null || chrome.signalCode !== null) break;
      await sleep(150);
    }
    if (!port) {
      const stderr = (await readFile(logPath,'utf8').catch(() => '')).slice(-1500);
      startupError = 'attempt ' + attempt + ': ' +
        (spawnError || 'exit=' + chrome.exitCode + ' signal=' + chrome.signalCode) +
        (stderr ? '; Chrome stderr: ' + stderr : '');
      chrome.kill('SIGTERM');
      await sleep(250);
    }
  }
  insist(port, 'Chrome did not start its debugging endpoint after two attempts. ' + startupError);
  const pages = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const page = pages.find(x=>x.type==='page');
  insist(page,'Chrome has no page target');
  socket = await connect(page.webSocketDebuggerUrl);
  await send('Page.enable'); await send('Runtime.enable');
  await navigate('/login/');
  const checks = [await checkPage('desktop login')];

  // Login deliberately autofocuses username. Shift+Tab must reach the skip link;
  // on pages without autofocus, ordinary Tab must reach it.
  const initialFocus = await evalPage("document.activeElement?.id");
  const modifiers = initialFocus==='username' ? 8 : 0;
  let focus;
  for (let i=0; i<8; i++) {
    await send('Input.dispatchKeyEvent', { type:'keyDown', key:'Tab', code:'Tab', windowsVirtualKeyCode:9, modifiers });
    await send('Input.dispatchKeyEvent', { type:'keyUp', key:'Tab', code:'Tab', windowsVirtualKeyCode:9, modifiers });
    focus = await evalPage("document.activeElement?.getAttribute('href')");
    if (focus==='#main') break;
  }
  insist(focus==='#main','keyboard navigation cannot reach skip link; starting field: '+initialFocus);

  if (credentialsFile) {
    const env = Object.fromEntries((await readFile(credentialsFile,'utf8'))
      .split(/\r?\n/).filter(v=>v && !v.startsWith('#') && v.includes('='))
      .map(s=>[s.slice(0,s.indexOf('=')),s.slice(s.indexOf('=')+1)]));
    insist(env.ADMIN_USERNAME && env.ADMIN_PASSWORD, 'Test credentials missing');
    await evalPage(`(() => { document.querySelector('input[name=username]').value=${JSON.stringify(env.ADMIN_USERNAME)};
      document.querySelector('input[name=password]').value=${JSON.stringify(env.ADMIN_PASSWORD)};
      document.querySelector('form').requestSubmit(); return true; })()`);
    await waitFor('location.pathname === "/" && !!document.querySelector("main h1")','authenticated dashboard',100);
    checks.push(await checkPage('desktop dashboard'));
    await navigate('/accounts/');
    checks.push(await checkPage('desktop accounts administration'));

    await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:2,mobile:true});
    await navigate('/');
    checks.push(await checkPage('mobile dashboard'));
    await navigate('/profile/');
    checks.push(await checkPage('mobile profile'));
    await navigate('/accounts/');
    checks.push(await checkPage('mobile accounts administration'));
    await navigate('/');
    const noOrganization = await evalPage("document.querySelectorAll('#customer-select option').length === 0");
    if (noOrganization) {
      insist(await evalPage("document.querySelector('main')?.innerText.includes('Create a customer organization first')"),
        'Admin missing first-organization onboarding guidance');
      insist(await evalPage("!document.querySelector('form[action*=projects]')"),
        'Create project form should not appear without a customer organization');
      checks.push({page:'empty-workspace onboarding',result:'passed'});
    }
    await send('Emulation.setEmulatedMedia',{media:'print'});
    insist(await evalPage("getComputedStyle(document.querySelector('header')).display === 'none'"),'print header remains visible');
    await send('Emulation.setEmulatedMedia',{media:''});
    checks.push({page:'print header hidden',result:'passed'});
    if (fixtureFile) {
      const fixture = JSON.parse(await readFile(fixtureFile,'utf8'));
      insist(fixture.synthetic === true, 'Only explicit synthetic fixtures may be tested');
      await navigate(fixture.project_path);
      checks.push(await checkPage('mobile synthetic project'));
      await navigate(fixture.review_path);
      checks.push(await checkPage('mobile synthetic review'));
      const unique = await evalPage("document.querySelector('main h1')?.textContent || ''");
      insist(unique.includes('2 unique links') && unique.includes('3 uses'), 'Incorrect unique link consolidation');
      const grouped = await evalPage("document.querySelectorAll('a[href*=unique]').length");
      insist(grouped===fixture.expected_unique,'Wrong count of unique review links');
      const exportResult = await evalPage(`(async()=> {
        const r=await fetch(${JSON.stringify(base)} + ${JSON.stringify(fixture.csv_path)}, {credentials:'same-origin'});
        return {status:r.status,body:await r.text(),type:r.headers.get('content-type')};
      })()`);
      insist(exportResult.status===200 && exportResult.type.includes('text/csv'),'Action list CSV inaccessible');
      const lines = exportResult.body.trim().split(/\r?\n/);
      insist(lines.length===3,'Action list CSV should have header and two distinct links');
      insist(exportResult.body.includes('synthetic-creator') && exportResult.body.includes('synthetic-other'), 'Different affiliate IDs incorrectly collapsed');
      checks.push({page:'authenticated CSV export',result:'passed',uniqueLinks:2,sourceOccurrences:3});
      await navigate(fixture.print_path);
      checks.push(await checkPage('mobile printable audit report'));
      await send('Emulation.setEmulatedMedia',{media:'print'});
      insist(await evalPage("getComputedStyle(document.querySelector('header')).display === 'none'"),'Print report header visible');
      await send('Emulation.setEmulatedMedia',{media:''});
      checks.push({page:'printed audit report header',result:'passed'});
    }
  }
  console.log(JSON.stringify({passed:true,checks},null,2));
} catch (error) {
  console.error('BROWSER_SMOKE_FAILED: ' + error.message);
  process.exitCode=1;
} finally {
  try { socket?.close(); } catch {}
  try { chrome?.kill('SIGTERM'); } catch {}
  await sleep(250);
  await rm(directory,{recursive:true,force:true,maxRetries:3,retryDelay:200});
}
