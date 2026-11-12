// Renders the archify diagrams in docs/diagrams/*.html to looping GIFs in
// docs/diagrams/gif/, so the animated trace can be embedded inline in markdown
// (GitHub renders GIFs, not the interactive HTML).
//
// Drives the viewer's own export menu to get a real WebM recording, then
// converts that to a GIF with ffmpeg.
//
//   npm install                       # once
//   node render-gifs.mjs              # all diagrams
//   node render-gifs.mjs hermes-agent-architecture terraform-aws-architecture
//
// Knobs (env). Defaults are tuned for clarity on flat-colour diagrams: record
// at 2x and downscale, so text is supersampled rather than rasterised once at
// final size; a full 256-entry palette with dithering OFF keeps flat fills and
// glyph edges clean (dithering only adds speckle to art with no gradients).
//
//   GIF_CAPTURE_SCALE=2 GIF_BITRATE=24000000
//   GIF_FPS=12 GIF_WIDTH=1400 GIF_COLORS=256 GIF_DITHER=none
//   WEBM_DIR=/some/dir    keep the source recordings, so the encode can be
//                         re-tuned without paying for another browser capture
//   CHROME=/path/to/chrome
import puppeteer from 'puppeteer-core';
import ffmpegPath from 'ffmpeg-static';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const execFileAsync = promisify(execFile);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(__dirname, '../..');
const DIAGRAMS = path.join(REPO, 'docs/diagrams');
const GIF_DIR = path.join(DIAGRAMS, 'gif');

const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const FPS = Number(process.env.GIF_FPS || 12);
const WIDTH = Number(process.env.GIF_WIDTH || 1400);
const COLORS = Number(process.env.GIF_COLORS || 256);

const CAPTURE_SCALE = Number(process.env.GIF_CAPTURE_SCALE || 2);
const BITRATE = Number(process.env.GIF_BITRATE || 24000000);
const DITHER = process.env.GIF_DITHER || 'none';

async function captureWebm(htmlPath, downloadDir) {
  fs.mkdirSync(downloadDir, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-gpu', '--window-size=1600,1000'],
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1600, height: 1000 });
    const client = await page.createCDPSession();
    await client.send('Browser.setDownloadBehavior', {
      behavior: 'allow',
      downloadPath: downloadDir,
    });
    await page.goto(pathToFileURL(path.resolve(htmlPath)).href, { waitUntil: 'networkidle0' });

    // Close any first-run overlay so the export button is clickable.
    await page.evaluate(() => {
      document.querySelectorAll('[data-dismiss], .archify-tour-close, .archify-onboarding-close')
        .forEach((el) => el.click());
    });

    await page.waitForSelector('#btn-export', { timeout: 15000 });
    await page.click('#btn-export');
    await page.waitForSelector('button[data-format="webm"]:not([disabled])', { timeout: 15000 });
    await page.click('button[data-format="webm"]');

    // Recording runs ~6s in-page, plus encode/flush time; poll for the download.
    const deadline = Date.now() + 20000;
    while (Date.now() < deadline) {
      const files = fs.readdirSync(downloadDir).filter((f) => f.endsWith('.webm'));
      if (files.length && !files.some((f) => f.endsWith('.crdownload'))) {
        return path.join(downloadDir, files[0]);
      }
      await new Promise((r) => setTimeout(r, 500));
    }
    throw new Error(`no .webm appeared in ${downloadDir} within timeout`);
  } finally {
    await browser.close();
  }
}

async function webmToGif(webmPath, gifPath) {
  const paletteDir = fs.mkdtempSync(path.join(path.dirname(gifPath), '.palette-'));
  const palette = path.join(paletteDir, 'palette.png');
  const filters = `fps=${FPS},scale=${WIDTH}:-1:flags=lanczos`;
  try {
    await execFileAsync(ffmpegPath, [
      '-y', '-i', webmPath,
      '-vf', `${filters},palettegen=stats_mode=diff:max_colors=${COLORS}`,
      palette,
    ]);
    await execFileAsync(ffmpegPath, [
      '-y', '-i', webmPath, '-i', palette,
      '-lavfi', `${filters}[x];[x][1:v]paletteuse=dither=${DITHER}:diff_mode=rectangle`,
      '-loop', '0',
      gifPath,
    ]);
  } finally {
    fs.rmSync(paletteDir, { recursive: true, force: true });
  }
}

// A silent failure here means a diagram doc embeds a broken image, so check the
// bytes rather than trusting that ffmpeg exited 0. The marker is the GIF
// graphic-control extension that precedes each frame.
function assertAnimatedGif(gifPath) {
  const d = fs.readFileSync(gifPath);
  const header = d.subarray(0, 6).toString('latin1');
  if (header !== 'GIF89a') throw new Error(`bad header ${JSON.stringify(header)}`);
  const marker = Buffer.from([0x00, 0x21, 0xf9, 0x04]);
  let frames = 0;
  for (let i = d.indexOf(marker); i !== -1; i = d.indexOf(marker, i + marker.length)) frames += 1;
  if (frames < 2) throw new Error(`${frames} frame(s), expected an animation`);
  return { frames, bytes: d.length };
}

// The viewer caps its own recording at 1x ("Math.min(1, 1280 / vb.width)") and
// at 6Mbps, which is the real limit on GIF sharpness -- not the encode. Record a
// patched throwaway copy at CAPTURE_SCALE instead and downscale afterwards, so
// the text is supersampled rather than rasterised once at final size. The
// committed diagram HTML is never touched.
const SCALE_CAP = 'Math.min(1, 1280 / vb.width)';
const BITRATE_CAP = 'videoBitsPerSecond: 6000000';

function patchForCapture(htmlPath, tmpDir, slug) {
  if (CAPTURE_SCALE <= 1) return htmlPath;
  const src = fs.readFileSync(htmlPath, 'utf8');
  if (!src.includes(SCALE_CAP)) throw new Error('capture-scale patch point not found in viewer');
  const out = path.join(tmpDir, `${slug}.capture.html`);
  fs.writeFileSync(out, src.replace(SCALE_CAP, String(CAPTURE_SCALE))
                          .replace(BITRATE_CAP, `videoBitsPerSecond: ${BITRATE}`));
  return out;
}

async function render(slug) {
  const source = path.join(DIAGRAMS, `${slug}.html`);
  if (!fs.existsSync(source)) throw new Error(`no such diagram: ${source}`);
  const gif = path.join(GIF_DIR, `${slug}.gif`);
  fs.mkdirSync(GIF_DIR, { recursive: true });

  const keepDir = process.env.WEBM_DIR;
  const tmpDir = keepDir ? path.join(keepDir, slug) : fs.mkdtempSync(path.join(GIF_DIR, '.webm-'));
  if (keepDir) fs.mkdirSync(tmpDir, { recursive: true });
  try {
    const webm = await captureWebm(patchForCapture(source, tmpDir, slug), tmpDir);
    await webmToGif(webm, gif);
    const { frames, bytes } = assertAnimatedGif(gif);
    return `${(bytes / 1024).toFixed(0)}KB, ${frames} frames`;
  } finally {
    if (!keepDir) fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

const slugs = process.argv.slice(2).length
  ? process.argv.slice(2)
  : fs.readdirSync(DIAGRAMS).filter((f) => f.endsWith('.html')).map((f) => f.slice(0, -5)).sort();

let failed = 0;
for (const slug of slugs) {
  process.stdout.write(`${slug} ... `);
  try {
    console.log(await render(slug));
  } catch (err) {
    failed += 1;
    console.log(`FAILED: ${err.message}`);
  }
}
console.log(`\n${slugs.length - failed}/${slugs.length} rendered${failed ? `, ${failed} failed` : ''}`);
process.exit(failed ? 1 : 0);
