import { spawn } from "node:child_process";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const stagePath = path.join(repoRoot, "docs/assets/demo-stage/threadwise-demo-stage.html");
const outputDir = path.join(repoRoot, "docs/assets");
const workDir = path.join("/private/tmp", `threadwise-demo-capture-${Date.now()}`);
const fps = 8;
const viewport = { width: 1280, height: 800 };
const includeMp4 = process.argv.includes("--include-mp4");

const clips = [
  {
    id: "daily",
    duration: 18,
    gif: "threadwise-daily-briefing.gif",
    mp4: "threadwise-daily-briefing.mp4",
    screenshot: { file: "threadwise-daily-dashboard.png", at: 13.2 },
  },
  {
    id: "teach",
    duration: 20,
    gif: "threadwise-teach-safely.gif",
    mp4: "threadwise-teach-safely.mp4",
    screenshot: { file: "threadwise-teach-preview.png", at: 14.2 },
  },
  {
    id: "unsubscribe",
    duration: 16,
    gif: "threadwise-unsubscribe-approval.gif",
    mp4: "threadwise-unsubscribe-approval.mp4",
    screenshot: { file: "threadwise-unsubscribe-review.png", at: 10.8 },
  },
  {
    id: "roadmap",
    duration: 9,
    gif: "threadwise-roadmap-next.gif",
    mp4: "threadwise-roadmap-next.mp4",
    screenshot: { file: "threadwise-roadmap-next.png", at: 6.5 },
  },
];

async function main() {
  await mkdir(outputDir, { recursive: true });
  await mkdir(workDir, { recursive: true });
  const port = await freePort();
  const profileDir = path.join(workDir, "chrome-profile");
  const chrome = spawn(chromePath, [
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    "--no-first-run",
    "--no-default-browser-check",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profileDir}`,
    "about:blank",
  ], {
    stdio: "ignore",
  });

  try {
    const target = await waitForChrome(port);
    const client = await connectCdp(target.webSocketDebuggerUrl);
    await client.send("Page.enable");
    await client.send("Runtime.enable");
    await client.send("Emulation.setDeviceMetricsOverride", {
      width: viewport.width,
      height: viewport.height,
      deviceScaleFactor: 1,
      mobile: false,
    });

    for (const clip of clips) {
      console.log(`Capturing ${clip.id}...`);
      await captureClip(client, clip);
      console.log(`Encoding ${clip.id} GIF...`);
      await encodeGif(clip);
      if (includeMp4) {
        console.log(`Encoding ${clip.id} MP4...`);
        await encodeMp4(clip);
        console.log(`Wrote ${clip.gif} and ${clip.mp4}`);
      } else {
        console.log(`Wrote ${clip.gif}`);
      }
    }

    console.log("Writing capture notes...");
    await writeCaptureNotes();
  } finally {
    chrome.kill("SIGTERM");
    await sleep(500);
    await rm(workDir, { recursive: true, force: true }).catch(() => {});
  }
}

async function captureClip(client, clip) {
  const frameDir = path.join(workDir, clip.id);
  await mkdir(frameDir, { recursive: true });
  const fileUrl = new URL(pathToFileURL(stagePath));
  fileUrl.searchParams.set("clip", clip.id);
  fileUrl.searchParams.set("t", "0");
  await client.send("Page.navigate", { url: fileUrl.toString() });
  await waitFor(() => client.evaluate("document.readyState === 'complete'"), 15000);
  await waitFor(() => client.evaluate("typeof window.setDemoTime === 'function'"), 15000);

  const frameCount = Math.ceil(clip.duration * fps) + 1;
  for (let frame = 0; frame < frameCount; frame += 1) {
    const t = Math.min(clip.duration, frame / fps);
    await client.evaluate(`window.setDemoTime(${JSON.stringify(t)}, ${JSON.stringify(clip.id)})`);
    const screenshot = await client.send("Page.captureScreenshot", {
      format: "png",
      captureBeyondViewport: false,
      fromSurface: true,
    });
    await writeFile(path.join(frameDir, `${String(frame).padStart(4, "0")}.png`), screenshot.data, "base64");
  }

  await captureStill(client, clip);
}

async function captureStill(client, clip) {
  await client.evaluate(`window.setDemoTime(${JSON.stringify(clip.screenshot.at)}, ${JSON.stringify(clip.id)})`);
  const screenshot = await client.send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: false,
    fromSurface: true,
  });
  await writeFile(path.join(outputDir, clip.screenshot.file), screenshot.data, "base64");
}

async function encodeGif(clip) {
  const framePattern = path.join(workDir, clip.id, "%04d.png");
  const palettePath = path.join(workDir, `${clip.id}-palette.png`);
  const gifPath = path.join(outputDir, clip.gif);

  await run("ffmpeg", [
    "-y",
    "-framerate", String(fps),
    "-i", framePattern,
    "-vf", "scale=960:-1:flags=lanczos,palettegen=max_colors=128",
    palettePath,
  ]);
  await run("ffmpeg", [
    "-y",
    "-framerate", String(fps),
    "-i", framePattern,
    "-i", palettePath,
    "-filter_complex", "scale=960:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4",
    gifPath,
  ]);
}

async function encodeMp4(clip) {
  const framePattern = path.join(workDir, clip.id, "%04d.png");
  const mp4Path = path.join(outputDir, clip.mp4);

  await run("ffmpeg", [
    "-y",
    "-framerate", String(fps),
    "-i", framePattern,
    "-vf", "format=yuv420p",
    "-movflags", "+faststart",
    mp4Path,
  ]);
}

async function writeCaptureNotes() {
  const lines = [
    "# Threadwise Demo Capture Notes",
    "",
    "Status: Generated asset notes",
    "Current as of: 2026-06-30",
    "Builds on: `docs/demo-script.md`, `docs/issues/071-capture-recruiter-ready-demo-assets.md`",
    "",
    "Generated assets:",
    "",
    "- `docs/assets/threadwise-daily-briefing.gif`",
    "- `docs/assets/threadwise-teach-safely.gif`",
    "- `docs/assets/threadwise-unsubscribe-approval.gif`",
    "- `docs/assets/threadwise-roadmap-next.gif`",
    "- `docs/assets/threadwise-daily-dashboard.png`",
    "- `docs/assets/threadwise-teach-preview.png`",
    "- `docs/assets/threadwise-unsubscribe-review.png`",
    "- `docs/assets/threadwise-roadmap-next.png`",
  ];
  if (includeMp4) {
    lines.push(
      "- `docs/assets/threadwise-daily-briefing.mp4`",
      "- `docs/assets/threadwise-teach-safely.mp4`",
      "- `docs/assets/threadwise-unsubscribe-approval.mp4`",
      "- `docs/assets/threadwise-roadmap-next.mp4`",
    );
  } else {
    lines.push("- MP4 versions are pending GIF approval.");
  }
  lines.push(
    "",
    "Capture method:",
    "",
    `- deterministic synthetic capture stage: \`docs/assets/demo-stage/threadwise-demo-stage.html\``,
    `- Chrome DevTools screenshots at \`${fps}\` fps`,
    "- GIF encoding via `ffmpeg`",
    "- MP4 encoding via `ffmpeg` when `--include-mp4` is passed",
    `- output viewport: \`${viewport.width}x${viewport.height}\``,
    "- GIF scale: `960px` wide",
    "",
    "Safety:",
    "",
    "- all visible emails, senders, domains, and account labels are synthetic demo data",
    "- no private inbox, credentials, OAuth screen, account settings, delete, archive, send, reply, or real unsubscribe execution is shown",
    "- roadmap asset is explicitly labeled as future direction, not shipped behavior",
    "",
    "Review notes:",
    "",
    "- first pass intentionally uses a controlled Gmail-like synthetic stage so cursor movement, zooms, captions, and typing/caret visibility are deterministic",
    "- MP4 generation is gated behind `--include-mp4` so the founder can approve the GIF direction before long-form exports are produced",
    "- final README placement can choose GIF or MP4 depending on GitHub rendering and file size",
  );
  const body = lines.join("\n");
  await writeFile(path.join(outputDir, "threadwise-capture-notes.md"), body);
}

async function freePort() {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() => resolve(address.port));
    });
    server.on("error", reject);
  });
}

async function waitForChrome(port) {
  const deadline = Date.now() + 15000;
  let lastError = null;
  while (Date.now() < deadline) {
    try {
      const list = await fetch(`http://127.0.0.1:${port}/json/list`).then((response) => response.json());
      const page = list.find((target) => target.type === "page");
      if (page && page.webSocketDebuggerUrl) {
        return page;
      }
    } catch (error) {
      lastError = error;
    }
    await sleep(150);
  }
  throw lastError || new Error("Chrome did not expose a page target.");
}

async function connectCdp(webSocketUrl) {
  const socket = new WebSocket(webSocketUrl);
  let nextId = 1;
  const pending = new Map();
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) {
        reject(new Error(message.error.message));
      } else {
        resolve(message.result);
      }
    }
  });
  return {
    send(method, params = {}) {
      const id = nextId++;
      socket.send(JSON.stringify({ id, method, params }));
      return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject });
      });
    },
    async evaluate(expression) {
      const result = await this.send("Runtime.evaluate", {
        expression,
        awaitPromise: true,
        returnByValue: true,
      });
      if (result.exceptionDetails) {
        const details = result.exceptionDetails;
        const description = details.exception?.description || details.text || "Evaluation failed.";
        throw new Error(description);
      }
      return result.result.value;
    },
  };
}

async function waitFor(fn, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await fn()) {
      return;
    }
    await sleep(100);
  }
  throw new Error("Timed out waiting for browser condition.");
}

function run(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: "pipe" });
    let stderr = "";
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`${command} ${args.join(" ")} failed with ${code}\n${stderr}`));
      }
    });
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

main().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
