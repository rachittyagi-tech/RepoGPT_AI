/** Three blinking dots shown while waiting for the first streamed token to arrive. */
export function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 py-1" role="status" aria-label="RepoGPT AI is typing">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-amber animate-blink"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}
