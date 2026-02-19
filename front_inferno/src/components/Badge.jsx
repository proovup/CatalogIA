const VARIANTS = {
  default: "bg-gray-100/80 text-gray-700 border-gray-200/60",
  success: "bg-green-100/80 text-green-800 border-green-200/60",
  warning: "bg-amber-100/80 text-amber-800 border-amber-200/60",
  danger: "bg-red-100/80 text-red-800 border-red-200/60",
  info: "bg-blue-100/80 text-blue-800 border-blue-200/60",
  purple: "bg-violet-100/80 text-violet-800 border-violet-200/60",
  indigo: "bg-indigo-100/80 text-indigo-800 border-indigo-200/60",
};

const SIZES = {
  default: "px-2 py-0.5 text-xs",
  sm: "px-1.5 py-0.5 text-[10px]",
};

export default function Badge({ children, variant = "default", size = "default", className = "", icon }) {
  return (
    <span class={`inline-flex items-center gap-1 rounded-full font-medium border backdrop-blur-sm transition-all hover:shadow-sm ${VARIANTS[variant] || VARIANTS.default} ${SIZES[size] || SIZES.default} ${className}`}>
      {icon && <span class="shrink-0">{icon}</span>}
      {children}
    </span>
  );
}
