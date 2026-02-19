import { Link } from "inferno-router";
import { IconChevronRight } from "./Icons";

export default function PageHeader({ title, subtitle, breadcrumb, actions, className = "" }) {
  return (
    <div class={`mb-6 animate-fade-in ${className}`}>
      {breadcrumb && breadcrumb.length > 0 && (
        <nav class="flex items-center gap-1.5 text-sm mb-3">
          {breadcrumb.map((item, i) => (
            <span class="flex items-center gap-1.5">
              {i > 0 && <IconChevronRight size={14} class="text-gray-300" />}
              {item.to ? (
                <Link to={item.to} class="text-gray-400 hover:text-gray-600 transition-colors">
                  {item.label}
                </Link>
              ) : (
                <span class="font-medium text-gray-900">{item.label}</span>
              )}
            </span>
          ))}
        </nav>
      )}
      <div class="flex items-center justify-between gap-4">
        <div class="min-w-0">
          <h1 class="text-2xl font-bold text-gray-900 truncate">{title}</h1>
          {subtitle && (
            <p class="text-sm text-gray-500 mt-1">{subtitle}</p>
          )}
        </div>
        {actions && (
          <div class="flex items-center gap-3 shrink-0">
            {actions}
          </div>
        )}
      </div>
    </div>
  );
}
