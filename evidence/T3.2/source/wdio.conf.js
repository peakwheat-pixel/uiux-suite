export const config = {
  runner: "local",
  specs: ["./test/specs/**/*.js"],
  maxInstances: 1,
  services: ["@wdio/tauri-service"],
  capabilities: [
    {
      browserName: "tauri",
      "tauri:options": {
        application: "./src-tauri/target/release/tauri-lab.exe",
      },
    },
  ],
  framework: "mocha",
  reporters: ["spec"],
  mochaOpts: { ui: "bdd", timeout: 60000 },
  logLevel: "warn",
};
