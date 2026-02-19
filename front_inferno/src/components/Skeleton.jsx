export function Skeleton({ width, height = 16, rounded = "rounded-lg", className = "" }) {
  return (
    <div
      class={`skeleton ${rounded} ${className}`}
      style={{ width: width || "100%", height: typeof height === "number" ? `${height}px` : height }}
    />
  );
}

export function SkeletonCard({ lines = 3 }) {
  return (
    <div class="bg-white rounded-xl border border-gray-200 p-6 space-y-3 animate-scale-in">
      <Skeleton height={20} width="60%" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton height={14} width={i === lines - 1 ? "40%" : "100%"} />
      ))}
    </div>
  );
}

export function SkeletonTable({ rows = 5, cols = 4 }) {
  return (
    <div class="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div class="bg-gray-50 border-b border-gray-200 px-4 py-3 flex gap-4">
        {Array.from({ length: cols }).map(() => (
          <Skeleton height={14} width={`${100 / cols}%`} />
        ))}
      </div>
      {Array.from({ length: rows }).map(() => (
        <div class="px-4 py-3 flex gap-4 border-b border-gray-50">
          {Array.from({ length: cols }).map((_, i) => (
            <Skeleton height={14} width={i === 0 ? "30%" : `${70 / (cols - 1)}%`} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function SkeletonMetrics({ count = 4 }) {
  return (
    <div class={`grid grid-cols-2 md:grid-cols-${count} gap-4`}>
      {Array.from({ length: count }).map(() => (
        <div class="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
          <Skeleton height={24} width={24} rounded="rounded-lg" />
          <Skeleton height={28} width="50%" />
          <Skeleton height={12} width="70%" />
        </div>
      ))}
    </div>
  );
}

export default Skeleton;
