// Violating TSX: inline style object drifts from every token scale.
export function Badge() {
  return (
    <span
      style={{
        color: '#ff0000',
        padding: '5px 8px',
        fontSize: '15px',
        lineHeight: 1.15,
        transition: 'opacity 250ms linear',
      }}
    >
      Badge
    </span>
  );
}
