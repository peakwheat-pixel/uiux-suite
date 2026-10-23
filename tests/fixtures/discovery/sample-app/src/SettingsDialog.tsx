import { useState } from "react";

export function SettingsDialog({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  return (
    <div role="dialog" aria-labelledby="settings-title" className="modal">
      <h2 id="settings-title">Settings</h2>
      <form onSubmit={(event) => { event.preventDefault(); onClose(); }}>
        <input data-testid="settings-name" value={name} onChange={(e) => setName(e.target.value)} />
        <button type="submit">保存</button>
      </form>
      <button onClick={onClose}>Cancel</button>
    </div>
  );
}
