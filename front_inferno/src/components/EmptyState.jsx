import { Link } from "inferno-router";

export default function EmptyState({ icon, title, description, actionLabel, actionTo, onAction, className = "" }) {
  return (
    <div class={`flex flex-col items-center justify-center py-16 px-4 animate-scale-in ${className}`}>
      {icon && (
        <div class="w-16 h-16 rounded-2xl gradient-primary-subtle flex items-center justify-center mb-5 text-indigo-500">
          {icon}
        </div>
      )}
      <h3 class="text-lg font-semibold text-gray-900 mb-1">{title}</h3>
      {description && (
        <p class="text-sm text-gray-500 text-center max-w-sm mb-5">{description}</p>
      )}
      {actionLabel && actionTo && (
        <Link
          to={actionTo}
          class="inline-flex items-center gap-2 gradient-primary text-white font-medium rounded-lg px-5 py-2.5 text-sm transition-all hover:shadow-lg hover:shadow-indigo-500/25 no-underline"
        >
          {actionLabel}
        </Link>
      )}
      {actionLabel && onAction && !actionTo && (
        <button
          class="inline-flex items-center gap-2 gradient-primary text-white font-medium rounded-lg px-5 py-2.5 text-sm transition-all hover:shadow-lg hover:shadow-indigo-500/25"
          onClick={onAction}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
