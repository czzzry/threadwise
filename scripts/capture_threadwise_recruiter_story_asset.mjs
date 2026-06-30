import { spawn } from "node:child_process";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const stageRelativePath = "docs/assets/demo-stage/threadwise-recruiter-story-stage.html";
const outputDir = path.join(repoRoot, "docs/assets");
const workDir = path.join("/private/tmp", `threadwise-recruiter-story-${Date.now()}`);
const fps = 10;
const viewport = { width: 1280, height: 800 };
const duration = 9.6;
const retimeFactor = 1.5;
const includeMp4 = process.argv.includes("--include-mp4");

async function main() {
  await mkdir(outputDir, { recursive: true });
  await mkdir(workDir, { recursive: true });

  const staticPort = await freePort();
  const staticServer = spawn(
    "python3",
    ["-m", "http.server", String(staticPort), "--bind", "127.0.0.1"],
    { cwd: repoRoot, stdio: "ignore" },
  );

  const chromePort = await freePort();
  const chrome = spawn(
    chromePath,
    [
      "--headless=new",
      "--disable-gpu",
      "--hide-scrollbars",
      "--no-first-run",
      "--no-default-browser-check",
      `--remote-debugging-port=${chromePort}`,
      `--user-data-dir=${path.join(workDir, "chrome-profile")}`,
      "about:blank",
    ],
    { stdio: "ignore" },
  );

  try {
    await sleep(900);
    const target = await waitForChrome(chromePort);
    const client = await connectCdp(target.webSocketDebuggerUrl);
    await client.send("Page.enable");
    await client.send("Runtime.enable");
    await client.send("Emulation.setDeviceMetricsOverride", {
      width: viewport.width,
      height: viewport.height,
      deviceScaleFactor: 1,
      mobile: false,
    });

    const frameDir = await captureFrames(client, staticPort);
    await writePoster(client, duration * 0.52);
    await encodeGif(frameDir);
    if (includeMp4) {
      await encodeMp4(frameDir);
    }
    await writeCaptureNotes();
  } finally {
    chrome.kill("SIGTERM");
    staticServer.kill("SIGTERM");
    await sleep(500);
    await rm(workDir, { recursive: true, force: true }).catch(() => {});
  }
}

async function captureFrames(client, staticPort) {
  const frameDir = path.join(workDir, "frames");
  await mkdir(frameDir, { recursive: true });

  const stageUrl = new URL(`http://127.0.0.1:${staticPort}/${stageRelativePath}`);
  stageUrl.searchParams.set("t", "0");
  await client.send("Page.navigate", { url: stageUrl.toString() });
  await waitFor(() => client.evaluate("document.readyState === 'complete'"), 15000);
  await waitFor(() => client.evaluate("typeof window.setDemoTime === 'function'"), 15000);

  const frameCount = Math.ceil(duration * fps) + 1;
  for (let frame = 0; frame < frameCount; frame += 1) {
    const t = Math.min(duration, frame / fps);
    await client.evaluate(`window.setDemoTime(${JSON.stringify(t)})`);
    const screenshot = await client.send("Page.captureScreenshot", {
      format: "png",
      captureBeyondViewport: false,
      fromSurface: true,
    });
    await writeFile(path.join(frameDir, `${String(frame).padStart(4, "0")}.png`), screenshot.data, "base64");
  }

  return frameDir;
}

async function writePoster(client, t) {
  await client.evaluate(`window.setDemoTime(${JSON.stringify(t)})`);
  const screenshot = await client.send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: false,
    fromSurface: true,
  });
  await writeFile(path.join(outputDir, "threadwise-recruiter-story.png"), screenshot.data, "base64");
}

async function encodeGif(frameDir) {
  const palettePath = path.join(workDir, "palette.png");
  const framePattern = path.join(frameDir, "%04d.png");
  const gifPath = path.join(outputDir, "threadwise-recruiter-story.gif");
  await run("ffmpeg", [
    "-y",
    "-framerate",
    String(fps),
    "-i",
    framePattern,
    "-vf",
    "scale=960:-1:flags=lanczos,palettegen=max_colors=160",
    palettePath,
  ]);
  await run("ffmpeg", [
    "-y",
    "-framerate",
    String(fps),
    "-i",
    framePattern,
    "-i",
    palettePath,
    "-filter_complex",
    `setpts=${retimeFactor}*PTS,scale=960:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4`,
    gifPath,
  ]);
}

async function encodeMp4(frameDir) {
  const framePattern = path.join(frameDir, "%04d.png");
  const mp4Path = path.join(outputDir, "threadwise-recruiter-story.mp4");
  await run("ffmpeg", [
    "-y",
    "-framerate",
    String(fps),
    "-i",
    framePattern,
    "-vf",
    `setpts=${retimeFactor}*PTS,format=yuv420p`,
    "-movflags",
    "+faststart",
    mp4Path,
  ]);
}

async function writeCaptureNotes() {
  const lines = [
    "# Threadwise Recruiter Story Capture Notes",
    "",
    "Status: Generated asset notes",
    "Current as of: 2026-06-30",
    "",
    "Generated assets:",
    "",
    "- `docs/assets/threadwise-recruiter-story.gif`",
    "- `docs/assets/threadwise-recruiter-story.png`",
  ];
  if (includeMp4) {
    lines.push("- `docs/assets/threadwise-recruiter-story.mp4`");
  } else {
    lines.push("- MP4 generation is pending founder approval of the GIF direction.");
  }
  lines.push(
    "",
    "Capture method:",
    "",
    "- deterministic browser-rendered stage at `docs/assets/demo-stage/threadwise-recruiter-story-stage.html`",
    `- ${fps} fps source capture, ${duration}s source timeline retimed to roughly ${(duration * retimeFactor).toFixed(1)}s, output GIF scaled to 960px wide`,
    "- one calm story covering selected email, teach correction, approval, unsubscribe confirmation, and roadmap",
    "",
    "Storyboard constraints followed:",
    "",
    "- no cursor",
    "- no rings, outlines, highlight boxes, spotlights, or flashing effects",
    "- only plain narration text plus smooth UI state transitions",
    "- new asset path; existing GIFs were not overwritten",
    "",
    "Safety:",
    "",
    "- all visible email content is synthetic demo content",
    "- no live Gmail account, OAuth, credentials, or real unsubscribe execution is involved",
    "- roadmap content is labeled as coming next, not shipped current behavior",
  );
  await writeFile(path.join(outputDir, "threadwise-recruiter-story-capture-notes.md"), `${lines.join("\n")}\n`);
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
  throw new Error("Timed out waiting for condition.");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function run(command, args) {
  await new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd: repoRoot, stdio: "inherit" });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`${command} exited with ${code}`));
      }
    });
  });
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
