import { IconX } from "./Icons";

export default function Modal({ open, onClose, title, children, wide }) {
  if (!open) return null;
  return (
    <div class={`fixed inset-0 z-50 ${wide ? "" : "flex items-center justify-center p-4"}`}>
      <div class="absolute inset-0 glass-dark animate-fade-in" onClick={onClose} />
      <div
        class={`relative bg-white w-full animate-scale-in border border-gray-200/50 flex flex-col ${
          wide
            ? "fixed inset-0 max-w-none max-h-none rounded-none shadow-2xl shadow-black/10"
            : "rounded-2xl shadow-2xl shadow-black/10 max-w-lg max-h-[90vh]"
        }`}
      >
        <div class={`flex items-center justify-between border-b border-gray-100 flex-shrink-0 ${wide ? "px-6 py-4" : "px-6 py-4"}`}>
          <h2 class="text-lg font-semibold text-gray-900">{title}</h2>
          <button
            class="w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            onClick={onClose}
          >
            <IconX size={18} />
          </button>
        </div>
        <div class={`overflow-auto flex-1 ${wide ? "px-6 py-5" : "px-6 py-5"}`}>{children}</div>
      </div>
    </div>
  );
}
