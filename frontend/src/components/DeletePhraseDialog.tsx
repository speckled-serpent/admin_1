import { useState } from "react";

const DELETE_PHRASE = "DELETE";

export function DeletePhraseDialog({
  title,
  lede,
  titleId,
  busy,
  error,
  onCancel,
  onConfirm,
}: {
  title: string;
  lede: string;
  titleId: string;
  busy: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const [phrase, setPhrase] = useState("");
  const ready = phrase === DELETE_PHRASE && !busy;

  return (
    <div className="modal-backdrop">
      <form
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onSubmit={(event) => {
          event.preventDefault();
          if (ready) {
            onConfirm();
          }
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            onCancel();
          }
        }}
      >
        <h2 id={titleId}>{title}</h2>
        <p className="lede">{lede}</p>
        <label>
          Confirmation
          <input value={phrase} autoComplete="off" spellCheck={false} onChange={(event) => setPhrase(event.target.value)} autoFocus />
        </label>
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
        <div className="modal-actions">
          <button type="button" className="ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button type="submit" disabled={!ready}>
            Delete
          </button>
        </div>
      </form>
    </div>
  );
}
