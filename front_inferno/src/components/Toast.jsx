import { IconCheckCircle, IconXCircle, IconInfo, IconX } from "./Icons";

const TOAST_STYLES = {
  success: "bg-white border-green-200 text-green-800",
  error: "bg-white border-red-200 text-red-800",
  info: "bg-white border-blue-200 text-blue-800",
};

const TOAST_ICONS = {
  success: <IconCheckCircle size={18} class="text-green-500 shrink-0" />,
  error: <IconXCircle size={18} class="text-red-500 shrink-0" />,
  info: <IconInfo size={18} class="text-blue-500 shrink-0" />,
};

const TOAST_PROGRESS = {
  success: "bg-green-500",
  error: "bg-red-500",
  info: "bg-blue-500",
};

export default function Toast({ message, type = "success", onClose }) {
  if (!message) return null;
  return (
    <div class={`fixed top-4 right-4 z-50 border rounded-xl px-4 py-3 text-sm shadow-xl shadow-black/5 flex items-center gap-3 max-w-md animate-slide-in-right overflow-hidden ${TOAST_STYLES[type] || TOAST_STYLES.info}`}>
      {TOAST_ICONS[type]}
      <span class="flex-1 font-medium">{message}</span>
      {onClose && (
        <button class="opacity-40 hover:opacity-100 transition-opacity" onClick={onClose}>
          <IconX size={16} />
        </button>
      )}
      <div class={`absolute bottom-0 left-0 h-0.5 toast-progress ${TOAST_PROGRESS[type] || TOAST_PROGRESS.info}`} />
    </div>
  );
}
