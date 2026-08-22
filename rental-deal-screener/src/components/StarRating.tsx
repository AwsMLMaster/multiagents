interface Props {
  value: number; // 0-5, supports halves
  outOf?: number;
}

export default function StarRating({ value, outOf = 5 }: Props) {
  const stars = [];
  for (let i = 1; i <= outOf; i++) {
    const filled = value >= i;
    const half = !filled && value >= i - 0.5;
    stars.push(
      <span key={i} className="relative inline-block w-4 text-amber-400">
        <span className="text-slate-700">★</span>
        {(filled || half) && (
          <span
            className="absolute inset-0 overflow-hidden"
            style={{ width: filled ? "100%" : "50%" }}
          >
            ★
          </span>
        )}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-0.5" title={`${value} / ${outOf}`}>
      {stars}
    </span>
  );
}
