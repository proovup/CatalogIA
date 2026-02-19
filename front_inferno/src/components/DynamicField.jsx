import { Component } from "inferno";
import Badge from "./Badge";
import { IconPencil, IconSparkles, IconDatabase, IconChevronDown, IconWand, IconSpinner } from "./Icons";

const MODES = [
  { id: "manual", label: "Manuel", icon: IconPencil, color: "text-gray-600", bg: "bg-gray-100", activeBg: "bg-gray-600", activeText: "text-white" },
  { id: "ai", label: "IA", icon: IconSparkles, color: "text-violet-600", bg: "bg-violet-50", activeBg: "bg-violet-600", activeText: "text-white" },
  { id: "raw", label: "Brut", icon: IconDatabase, color: "text-amber-600", bg: "bg-amber-50", activeBg: "bg-amber-600", activeText: "text-white" },
];

export default function DynamicField({ field, value, onChange, mode, aiHint, onModeChange, onAiHintChange, rawDataEntries, onGenerate, generating }) {
  const { name, type, label, required, options, ai_instruction, fields: subFields, unit } = field;
  const displayLabel = label || name;
  const currentMode = mode || "manual";
  const shortName = name.indexOf(".") !== -1 ? name.split(".").pop() : null;

  const cls = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500";

  return (
    <div class="group/field rounded-xl border border-gray-100 bg-white p-4 transition-all hover:border-gray-200 hover:shadow-sm">
      {/* Header: label + mode selector */}
      <div class="flex items-center justify-between mb-2.5">
        <label class="flex items-center gap-2 text-sm font-medium text-gray-700">
          {displayLabel}
          {unit && <span class="text-[10px] font-medium text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded">{unit}</span>}
          {required && <span class="text-red-500">*</span>}
          {ai_instruction && <Badge variant="purple">IA</Badge>}
          {shortName && <span class="text-[10px] text-gray-400 font-mono">{name}</span>}
        </label>

        {/* Mode toggle buttons */}
        <div class="flex items-center gap-0.5 p-0.5 bg-gray-50 rounded-lg border border-gray-100">
          {MODES.map((m) => {
            const Icon = m.icon;
            const active = currentMode === m.id;
            return (
              <button
                type="button"
                class={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium transition-all ${
                  active
                    ? `${m.activeBg} ${m.activeText} shadow-sm`
                    : `text-gray-400 hover:text-gray-600 hover:bg-white`
                }`}
                onClick={() => onModeChange && onModeChange(name, m.id)}
                title={m.label}
              >
                <Icon size={12} />
                <span class="hidden sm:inline">{m.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Mode: Manual — standard input */}
      {currentMode === "manual" && (
        <div>
          <FieldInput type={type} name={name} value={value} onChange={onChange} options={options} cls={cls} />
        </div>
      )}

      {/* Mode: AI — field value (read-only preview) + helper text */}
      {currentMode === "ai" && (
        <div class="space-y-2.5">
          <div class="relative">
            <FieldInput type={type} name={name} value={value} onChange={onChange} options={options} cls={`${cls} bg-violet-50/30 border-violet-200`} />
            <div class="absolute top-2 right-2">
              <Badge variant="purple">IA</Badge>
            </div>
          </div>
          {ai_instruction && (
            <p class="text-xs text-violet-500 italic">{ai_instruction}</p>
          )}
          <div class="bg-violet-50/50 rounded-lg border border-violet-100 p-3">
            <label class="block text-xs font-medium text-violet-600 mb-1.5">
              Indication pour l'IA
            </label>
            <textarea
              class="w-full border border-violet-200 rounded-lg px-3 py-2 text-xs bg-white focus:ring-2 focus:ring-violet-400 focus:border-violet-400 resize-y placeholder:text-violet-300"
              rows={2}
              placeholder="Ex: Utiliser un ton marketing, max 50 mots..."
              value={aiHint || ""}
              onInput={(e) => onAiHintChange && onAiHintChange(name, e.target.value)}
            />
            <button
              type="button"
              class="mt-2 inline-flex items-center gap-1.5 bg-violet-600 hover:bg-violet-700 text-white font-medium rounded-lg px-3.5 py-1.5 text-xs transition-all hover:shadow-md hover:shadow-violet-500/25 disabled:opacity-50"
              disabled={generating}
              onClick={() => onGenerate && onGenerate(field)}
            >
              {generating ? (
                <><IconSpinner size={12} /> Génération...</>
              ) : (
                <><IconWand size={12} /> Générer ce champ</>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Mode: Raw data — picker from raw data entries */}
      {currentMode === "raw" && (
        <div class="space-y-2.5">
          <RawDataPicker
            entries={rawDataEntries || []}
            value={value}
            onSelect={(v) => onChange(name, v)}
            cls={cls}
          />
          {/* Show current value */}
          {value != null && value !== "" && (
            <div class="bg-amber-50/50 rounded-lg border border-amber-100 px-3 py-2">
              <span class="text-xs font-medium text-amber-700">Valeur sélectionnée : </span>
              <span class="text-xs text-amber-900 font-mono">
                {typeof value === "object" ? JSON.stringify(value) : String(value)}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


function FieldInput({ type, name, value, onChange, options, cls }) {
  switch (type) {
    case "text":
    case "html":
      return (
        <textarea
          class={`${cls} resize-y`}
          rows={type === "html" ? 6 : 3}
          value={value || ""}
          onInput={(e) => onChange(name, e.target.value)}
        />
      );

    case "float":
    case "integer":
      return (
        <input
          class={cls}
          type="number"
          step={type === "float" ? "0.01" : "1"}
          value={value != null ? value : ""}
          onInput={(e) => {
            const v = e.target.value;
            onChange(name, v === "" ? null : type === "float" ? parseFloat(v) : parseInt(v));
          }}
        />
      );

    case "boolean":
      return (
        <label class="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            class="w-4 h-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            checked={!!value}
            onChange={(e) => onChange(name, e.target.checked)}
          />
          <span class="text-sm text-gray-600">{value ? "Oui" : "Non"}</span>
        </label>
      );

    case "enum":
      return (
        <select
          class={cls}
          value={value || ""}
          onChange={(e) => onChange(name, e.target.value)}
        >
          <option value="">-- Sélectionner --</option>
          {(options || []).map((opt) => (
            <option value={opt}>{opt}</option>
          ))}
        </select>
      );

    case "array":
      return <ArrayField value={value} onChange={(v) => onChange(name, v)} />;

    case "object":
    case "json":
      return (
        <textarea
          class={`${cls} resize-y font-mono text-xs`}
          rows={4}
          value={typeof value === "object" ? JSON.stringify(value, null, 2) : value || ""}
          onInput={(e) => {
            try {
              onChange(name, JSON.parse(e.target.value));
            } catch {
              // keep raw string while typing
            }
          }}
        />
      );

    default:
      return (
        <input
          class={cls}
          type="text"
          value={value || ""}
          onInput={(e) => onChange(name, e.target.value)}
        />
      );
  }
}


function RawDataPicker({ entries, value, onSelect, cls }) {
  if (!entries.length) {
    return (
      <div class="text-xs text-gray-400 italic py-2">
        Aucune donnée brute disponible pour ce produit.
      </div>
    );
  }

  return (
    <div class="space-y-1.5">
      <select
        class={`${cls} bg-amber-50/30 border-amber-200`}
        onChange={(e) => {
          const idx = parseInt(e.target.value);
          if (!isNaN(idx) && entries[idx]) {
            onSelect(entries[idx].value);
          }
        }}
      >
        <option value="">-- Sélectionner une donnée brute --</option>
        {entries.map((entry, i) => {
          const display = typeof entry.value === "object"
            ? JSON.stringify(entry.value).slice(0, 80)
            : String(entry.value).slice(0, 80);
          return (
            <option value={i}>
              {entry.key}: {display}
            </option>
          );
        })}
      </select>
      {entries.length > 5 && (
        <p class="text-[10px] text-amber-500">{entries.length} valeurs disponibles</p>
      )}
    </div>
  );
}


class ArrayField extends Component {
  render() {
    const items = Array.isArray(this.props.value) ? this.props.value : [];
    const onChange = this.props.onChange;

    return (
      <div class="space-y-1">
        {items.map((item, i) => (
          <div class="flex gap-2">
            <input
              class="flex-1 border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-indigo-500"
              value={item}
              onInput={(e) => {
                const next = [...items];
                next[i] = e.target.value;
                onChange(next);
              }}
            />
            <button
              class="text-red-400 hover:text-red-600 text-sm px-2"
              onClick={() => onChange(items.filter((_, j) => j !== i))}
            >
              &times;
            </button>
          </div>
        ))}
        <button
          class="text-indigo-600 hover:text-indigo-800 text-xs font-medium"
          onClick={() => onChange([...items, ""])}
        >
          + Ajouter
        </button>
      </div>
    );
  }
}
