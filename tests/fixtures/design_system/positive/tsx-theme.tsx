// Compliant TSX: inline style object uses design-token references only.
export function Card() {
  return (
    <div
      style={{
        color: 'var(--color-text-primary)',
        backgroundColor: 'var(--color-bg-canvas)',
        padding: '16px',
        gap: '8px',
        fontSize: 14,
        lineHeight: 1.5,
        borderRadius: 8,
      }}
    >
      Card
    </div>
  );
}
