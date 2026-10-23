import fs from "node:fs";
import crypto from "node:crypto";

describe("Tauri native IPC", () => {
  it("invokes the Rust greet command from the WebView", async () => {
    const input = await $("#greet-input");
    await input.setValue("DSH-Native-IPC");
    await $("button[type=submit]").click();
    const message = await $("#greet-msg");
    await browser.waitUntil(
      async () => (await message.getText()).includes("DSH-Native-IPC"),
      { timeout: 15000, timeoutMsg: "greet message not updated" },
    );
    const text = await message.getText();
    expect(text).toContain("DSH-Native-IPC");
    const dir = "G:/AI/universal-uiux-engineering/evidence/T3.2";
    fs.mkdirSync(dir, { recursive: true });
    await browser.saveScreenshot(`${dir}/tauri-wdio-ipc.png`);
    const digest = crypto
      .createHash("sha256")
      .update(fs.readFileSync(`${dir}/tauri-wdio-ipc.png`))
      .digest("hex");
    fs.writeFileSync(
      `${dir}/tauri-wdio-run.json`,
      JSON.stringify({ ok: true, text, screenshot: "tauri-wdio-ipc.png", screenshot_sha256: digest }, null, 2) + "\n",
    );
  });
});
