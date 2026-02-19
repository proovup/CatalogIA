export default function Field({ label, value, onInput, textarea, type, required, placeholder, rows = 4, disabled }) {
  const cls = "w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all duration-200 focus-glow disabled:bg-gray-50 disabled:text-gray-400 disabled:border-gray-200 placeholder:text-gray-400";
  return (
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1.5">
        {label}
        {required && <span class="text-red-500 ml-0.5">*</span>}
      </label>
      {textarea ? (
        <textarea
          class={`${cls} resize-y`}
          rows={rows}
          value={value}
          placeholder={placeholder}
          disabled={disabled}
          onInput={(e) => onInput && onInput(e.target.value)}
        />
      ) : (
        <input
          class={cls}
          type={type || "text"}
          value={value}
          placeholder={placeholder}
          disabled={disabled}
          onInput={(e) => onInput && onInput(e.target.value)}
        />
      )}
    </div>
  );
}
