const fs = require("fs");
const { chromium } = require("playwright-core");

(async () => {
  const browser = await chromium.connectOverCDP("http://127.0.0.1:9222");
  const page = browser.contexts()[0].pages()[0];
  const result = await page.evaluate(async () => {
    const inv = window.__TAURI__.core.invoke;
    const pageId = "740e2b7db0f24641a721dd64cdeb7264";
    const regionId = "85072ecd4e2d45838e385db6e07e2135";
    const before = await inv("list_regions", { pageId });
    const beforeRegion = before.regions[0];
    const set = await inv("set_region_type", {
      regionId,
      newRegionType: beforeRegion.region_type === "speech" ? "sfx" : "speech",
      expectedRevision: beforeRegion.revision_no,
    });
    const mid = await inv("list_regions", { pageId });
    const revisions = await inv("list_region_revisions", { regionId });
    const restore = await inv("restore_region_revision", {
      regionId,
      revisionNo: beforeRegion.revision_no,
      expectedRevision: set.revision_no,
    });
    const after = await inv("list_regions", { pageId });
    return { before, set, mid, revisions, restore, after };
  });
  await browser.close();
  const evidence = {
    schema_version: "1.3.3",
    evidence_id: "EV-T5.3-UNDO-RESTORE",
    kind: "tool_log",
    runtime_level: "NATIVE_APP",
    generated_at: new Date().toISOString(),
    command: "node scripts/run_undo_check.js (CDP -> Tauri IPC set_region_type / restore_region_revision)",
    page_id: "740e2b7db0f24641a721dd64cdeb7264",
    region_id: "85072ecd4e2d45838e385db6e07e2135",
    transcript: result,
    result: {
      before_type: result.before.regions[0].region_type,
      before_revision: result.before.regions[0].revision_no,
      retyped_type: result.mid.regions[0].region_type,
      retyped_revision: result.mid.regions[0].revision_no,
      restored_type: result.after.regions[0].region_type,
      restored_revision: result.after.regions[0].revision_no,
      restore_origin: result.after.regions[0].origin,
      undo_ok:
        result.after.regions[0].region_type === result.before.regions[0].region_type &&
        result.after.regions[0].origin === "restored",
    },
    limitation: "Undo exercised through the real product IPC/domain path; the workbench overlay measured 0x0 in this run so the UI button click itself was not reachable. UI wiring is covered by WorkbenchPage.test.tsx.",
  };
  fs.writeFileSync(
    "G:/AI/universal-uiux-engineering/evidence/T5.3/undo-restore.json",
    JSON.stringify(evidence, null, 2) + "\n",
    "utf8",
  );
  console.log(JSON.stringify(evidence.result));
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
