import { Component } from "inferno";
import { api } from "../api";
import Card from "../components/Card";
import Badge from "../components/Badge";
import Modal from "../components/Modal";
import DropZone from "../components/DropZone";
import Toast from "../components/Toast";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import { SkeletonCard } from "../components/Skeleton";
import { IconLayers, IconEye, IconEdit, IconTrash, IconSpinner, IconChevronDown, IconChevronRight, IconPlus, IconDownload } from "../components/Icons";

export default class Formats extends Component {
  constructor(props) {
    super(props);
    this.state = {
      formats: [],
      loading: true,
      error: null,
      toast: null,
      toastType: "success",
      uploading: false,
      // Preview
      previewFormat: null,
      // Edit
      editFormat: null,
      editFields: [],
      editVersion: "1.0",
      editTargetEntity: "product",
      saving: false,
      // Create
      createOpen: false,
      createName: "",
      createDescription: "",
      createFields: [],
      createVersion: "1.0",
      createTargetEntity: "product",
      creating: false,
    };
  }

  componentDidMount() {
    this.load();
  }

  async load() {
    this.setState({ loading: true, error: null });
    try {
      const res = await api.listFormats();
      this.setState({ formats: res.formats || [], loading: false });
    } catch (e) {
      this.setState({ error: e.message, loading: false });
    }
  }

  renderEditorFields(scope = "create", fieldsOverride = null, depth = 0, parentPath = []) {
    const isEdit = scope === "edit";
    const fields = fieldsOverride || (isEdit ? this.state.editFields : this.state.createFields);

    if (!fields.length) {
      return (
        <div class={`rounded-xl border border-dashed ${depth > 0 ? "border-indigo-200 bg-indigo-50/50" : "border-gray-300 bg-gray-50"} p-5 text-center text-sm text-gray-500`}>
          {depth > 0 ? "Aucun sous-champ pour cet objet." : "Aucun champ pour le moment."}
        </div>
      );
    }

    return (
      <div class={`space-y-3 ${depth > 0 ? "pl-3 border-l-2 border-indigo-100" : ""}`}>
        {fields.map((field, idx) => this.renderEditorFieldCard(scope, field, [...parentPath, idx], depth))}
      </div>
    );
  }

  renderEditorFieldCard(scope, field, path, depth = 0) {
    const isObject = (field.type || "string") === "object";

    return (
      <div class={`rounded-xl border p-4 ${depth > 0 ? "border-indigo-100 bg-indigo-50/30" : "border-gray-200 bg-white"}`}>
        <div class="grid grid-cols-1 md:grid-cols-12 gap-3">
          <div class="md:col-span-4">
            <label class="block text-xs font-medium text-gray-500 mb-1">Nom champ</label>
            <input
              class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus-glow"
              value={field.name}
              onInput={(e) => this.updateEditorField(scope, path, "name", e.target.value)}
              placeholder="ex: name"
            />
          </div>
          <div class="md:col-span-2">
            <label class="block text-xs font-medium text-gray-500 mb-1">Type</label>
            <select
              class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus-glow"
              value={field.type}
              onChange={(e) => this.updateEditorField(scope, path, "type", e.target.value)}
            >
              {[
                "string", "text", "html", "integer", "float", "boolean", "enum", "array", "object", "json",
              ].map((t) => <option value={t}>{t}</option>)}
            </select>
          </div>
          <div class="md:col-span-6">
            <label class="block text-xs font-medium text-gray-500 mb-1">Description</label>
            <input
              class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus-glow"
              value={field.description}
              onInput={(e) => this.updateEditorField(scope, path, "description", e.target.value)}
              placeholder="Description lisible du champ"
            />
          </div>
          <div class="md:col-span-12">
            <label class="block text-xs font-medium text-violet-600 mb-1">Instruction IA</label>
            <textarea
              class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus-glow resize-y"
              rows={2}
              value={field.aiInstruction}
              onInput={(e) => this.updateEditorField(scope, path, "aiInstruction", e.target.value)}
              placeholder="Instruction pour l'IA lors de la génération de ce champ (ex: 'Génère un titre SEO optimisé < 70 caractères')"
            />
          </div>
          {!isObject && (
            <div class="md:col-span-8">
              <label class="block text-xs font-medium text-gray-500 mb-1">Valeur par défaut</label>
              <input
                class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono focus-glow"
                value={field.defaultValue}
                onInput={(e) => this.updateEditorField(scope, path, "defaultValue", e.target.value)}
                placeholder='string ou JSON (ex: true, 12.5, {"a":1})'
              />
            </div>
          )}
          <div class={`${isObject ? "md:col-span-12" : "md:col-span-4"} flex items-end justify-end`}>
            <button
              class="inline-flex items-center gap-2 text-xs text-red-600 hover:text-red-700 bg-red-50 hover:bg-red-100 rounded-lg px-3 py-2"
              onClick={() => this.removeEditorField(scope, path)}
            >
              <IconTrash size={12} /> Supprimer
            </button>
          </div>
        </div>

        <div class="mt-3 flex flex-wrap gap-3">
          <label class="inline-flex items-center gap-2 text-xs text-gray-600">
            <input
              type="checkbox"
              checked={!!field.required}
              onChange={(e) => this.updateEditorField(scope, path, "required", e.target.checked)}
            />
            Requis
          </label>
          {!isObject && (
            <label class="inline-flex items-center gap-2 text-xs text-gray-600">
              <input
                type="checkbox"
                checked={!!field.hasDefault}
                onChange={(e) => this.updateEditorField(scope, path, "hasDefault", e.target.checked)}
              />
              Activer défaut
            </label>
          )}
          <label class="inline-flex items-center gap-2 text-xs text-gray-600">
            <input
              type="checkbox"
              checked={!!field.excludeFromExtraction}
              onChange={(e) => this.updateEditorField(scope, path, "excludeFromExtraction", e.target.checked)}
            />
            Exclure extraction
          </label>
        </div>

        {isObject && (
          <div class="mt-4 space-y-2">
            <div class="flex items-center justify-between">
              <h4 class="text-xs font-semibold uppercase tracking-wide text-indigo-700">Sous-champs</h4>
              <button
                class="inline-flex items-center gap-1.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded-lg px-3 py-1.5 text-xs font-medium"
                onClick={() => this.addEditorField(scope, path)}
              >
                <IconPlus size={12} /> Ajouter un sous-champ
              </button>
            </div>
            {this.renderEditorFields(scope, field.subFields || [], depth + 1, path)}
          </div>
        )}
      </div>
    );
  }

  yamlScalar(value) {
    if (value === null) return "null";
    if (typeof value === "boolean") return value ? "true" : "false";
    if (typeof value === "number") return String(value);
    const str = String(value);
    if (str === "" || /[:#\-\n\[\]\{\}]/.test(str)) {
      return JSON.stringify(str);
    }
    return str;
  }

  toYaml(value, indent = 0) {
    const space = "  ".repeat(indent);
    if (Array.isArray(value)) {
      if (value.length === 0) return "[]";
      return value
        .map((item) => {
          if (item && typeof item === "object") {
            const nested = this.toYaml(item, indent + 1);
            return `${space}-\n${nested}`;
          }
          return `${space}- ${this.yamlScalar(item)}`;
        })
        .join("\n");
    }

    if (value && typeof value === "object") {
      const entries = Object.entries(value);
      if (entries.length === 0) return "{}";
      return entries
        .map(([k, v]) => {
          if (v && typeof v === "object") {
            const nested = this.toYaml(v, indent + 1);
            if (nested === "{}" || nested === "[]") {
              return `${space}${k}: ${nested}`;
            }
            return `${space}${k}:\n${nested}`;
          }
          return `${space}${k}: ${this.yamlScalar(v)}`;
        })
        .join("\n");
    }

    return `${space}${this.yamlScalar(value)}`;
  }

  handleDownloadFormat(formatItem) {
    const payload = formatItem?.yaml_content || {};
    const yaml = this.toYaml(payload);
    const blob = new Blob([yaml], { type: "text/yaml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const safeName = (formatItem?.name || "format").toLowerCase().replace(/[^a-z0-9-_]+/g, "-");
    a.href = url;
    a.download = `${safeName || "format"}.yaml`;
    a.click();
    URL.revokeObjectURL(url);
    this.showToast("Format téléchargé");
  }

  newEditorField(overrides = {}) {
    const base = {
      name: "",
      type: "string",
      description: "",
      required: false,
      defaultValue: "",
      hasDefault: false,
      aiInstruction: "",
      excludeFromExtraction: false,
      subFields: [],
    };
    return {
      ...base,
      ...overrides,
      subFields: Array.isArray(overrides.subFields) ? overrides.subFields : base.subFields,
    };
  }

  normalizeEditorFields(rawFields) {
    if (!rawFields) return [];

    let list = [];
    if (Array.isArray(rawFields)) {
      list = rawFields;
    } else if (typeof rawFields === "object") {
      list = Object.entries(rawFields).map(([name, value]) => ({ name, ...(typeof value === "object" ? value : {}) }));
    }

    return list
      .filter((f) => f && (f.name || "").trim())
      .map((f) => {
        const type = f.type || "string";
        const subFields = type === "object" ? this.normalizeEditorFields(f.fields || []) : [];
        return this.newEditorField({
          name: String(f.name || "").trim(),
          type,
          description: f.description || f.label || "",
          required: !!f.required,
          hasDefault: Object.prototype.hasOwnProperty.call(f, "default"),
          defaultValue: Object.prototype.hasOwnProperty.call(f, "default")
            ? (typeof f.default === "string" ? f.default : JSON.stringify(f.default))
            : "",
          aiInstruction: f.ai_instruction || "",
          excludeFromExtraction: !!f.exclude_from_extraction,
          subFields,
        });
      });
  }

  denormalizeEditorFields(editorFields) {
    const out = {};
    for (const f of editorFields) {
      const name = (f.name || "").trim();
      if (!name) continue;

      const item = {
        type: f.type || "string",
      };

      if (f.description && f.description.trim()) item.description = f.description.trim();
      if (f.required) item.required = true;
      if (f.aiInstruction && f.aiInstruction.trim()) item.ai_instruction = f.aiInstruction.trim();
      if (f.excludeFromExtraction) item.exclude_from_extraction = true;

      if (f.hasDefault && f.type !== "object") {
        const raw = (f.defaultValue || "").trim();
        if (raw === "") {
          item.default = "";
        } else {
          try {
            item.default = JSON.parse(raw);
          } catch {
            item.default = raw;
          }
        }
      }

      if (f.type === "object") {
        item.fields = this.denormalizeEditorFields(f.subFields || []);
      }

      out[name] = item;
    }
    return out;
  }

  buildYamlFromEditor(scope, fallback = {}) {
    const isEdit = scope === "edit";
    const version = isEdit ? this.state.editVersion : this.state.createVersion;
    const targetEntity = isEdit ? this.state.editTargetEntity : this.state.createTargetEntity;
    const fields = isEdit ? this.state.editFields : this.state.createFields;

    return {
      ...fallback,
      format_version: version || fallback.format_version || "1.0",
      target_entity: targetEntity || fallback.target_entity || "product",
      fields: this.denormalizeEditorFields(fields),
    };
  }

  updateFieldTree(fields, path, updater) {
    const [head, ...rest] = path;
    return fields.map((field, idx) => {
      if (idx !== head) return field;
      if (!rest.length) return updater(field);
      return {
        ...field,
        subFields: this.updateFieldTree(field.subFields || [], rest, updater),
      };
    });
  }

  addEditorField(scope, parentPath = null) {
    const key = scope === "edit" ? "editFields" : "createFields";
    if (!parentPath || parentPath.length === 0) {
      this.setState((prev) => ({ [key]: [...prev[key], this.newEditorField()] }));
      return;
    }

    this.setState((prev) => ({
      [key]: this.updateFieldTree(prev[key], parentPath, (field) => ({
        ...field,
        subFields: [...(field.subFields || []), this.newEditorField()],
      })),
    }));
  }

  removeEditorField(scope, path) {
    const key = scope === "edit" ? "editFields" : "createFields";
    if (path.length === 1) {
      const index = path[0];
      this.setState((prev) => ({ [key]: prev[key].filter((_, i) => i !== index) }));
      return;
    }

    const parentPath = path.slice(0, -1);
    const removeIndex = path[path.length - 1];
    this.setState((prev) => ({
      [key]: this.updateFieldTree(prev[key], parentPath, (field) => ({
        ...field,
        subFields: (field.subFields || []).filter((_, i) => i !== removeIndex),
      })),
    }));
  }

  updateEditorField(scope, path, field, value) {
    const key = scope === "edit" ? "editFields" : "createFields";
    this.setState((prev) => {
      const next = this.updateFieldTree(prev[key], path, (current) => {
        const updated = { ...current, [field]: value };
        if (field === "type" && value !== "object") {
          updated.subFields = [];
        }
        if (field === "type" && value === "object" && !Array.isArray(updated.subFields)) {
          updated.subFields = [];
        }
        if (field === "type" && value === "object") {
          updated.hasDefault = false;
          updated.defaultValue = "";
        }
        return updated;
      });
      return { [key]: next };
    });
  }

  async handleCreateFormat() {
    const { createName, createDescription } = this.state;

    this.setState({ creating: true, error: null });
    try {
      await api.createFormat({
        name: createName.trim(),
        description: createDescription.trim() || null,
        yaml_content: this.buildYamlFromEditor("create"),
      });
      this.showToast("Format créé");
      this.setState({
        createOpen: false,
        createName: "",
        createDescription: "",
        createFields: [],
        createVersion: "1.0",
        createTargetEntity: "product",
        creating: false,
      });
      await this.load();
    } catch (e) {
      this.setState({ error: e.message, creating: false });
    }
  }

  showToast(message, type = "success") {
    this.setState({ toast: message, toastType: type });
    setTimeout(() => this.setState({ toast: null }), 4000);
  }

  async handleUpload(files) {
    this.setState({ uploading: true, error: null });
    try {
      for (const file of files) {
        await api.uploadFormat(file);
      }
      this.showToast(`${files.length} format${files.length > 1 ? "s" : ""} importé${files.length > 1 ? "s" : ""}`);
      this.setState({ uploading: false });
      await this.load();
    } catch (e) {
      this.setState({ error: e.message, uploading: false });
    }
  }

  async handleDelete(id) {
    if (!confirm("Supprimer ce format ?")) return;
    try {
      await api.deleteFormat(id);
      this.showToast("Format supprimé");
      await this.load();
      this.setState({ previewFormat: null });
    } catch (e) {
      this.setState({ error: e.message });
    }
  }

  async openPreview(formatItem) {
    try {
      const full = await api.getFormat(formatItem.id);
      this.setState({ previewFormat: full });
    } catch (e) {
      this.setState({ error: e.message });
    }
  }

  async openEdit(formatItem) {
    try {
      const full = await api.getFormat(formatItem.id);
      this.setState({
        editFormat: full,
        editFields: this.normalizeEditorFields(full.yaml_content?.fields),
        editVersion: full.yaml_content?.format_version || "1.0",
        editTargetEntity: full.yaml_content?.target_entity || "product",
      });
    } catch (e) {
      this.setState({ error: e.message });
    }
  }

  async handleSaveEdit() {
    const { editFormat } = this.state;
    this.setState({ saving: true, error: null });
    try {
      const yamlPayload = this.buildYamlFromEditor("edit", editFormat.yaml_content || {});
      await api.updateFormat(editFormat.id, {
        name: editFormat.name,
        description: editFormat.description,
        yaml_content: yamlPayload,
      });
      this.showToast("Format mis à jour");
      this.setState({ editFormat: null, saving: false });
      await this.load();
    } catch (e) {
      this.setState({ error: e.message, saving: false });
    }
  }

  renderFieldList(yamlContent, depth = 0) {
    const fields = yamlContent?.fields;
    if (!fields) return <p class="text-sm text-gray-400">Aucun champ défini</p>;

    let fieldList = [];
    if (Array.isArray(fields)) {
      fieldList = fields;
    } else if (typeof fields === "object") {
      fieldList = Object.entries(fields).map(([key, val]) => ({ name: key, ...(typeof val === "object" ? val : { type: "string" }) }));
    }

    return (
      <div class={depth > 0 ? "ml-4 pl-3 border-l-2 border-gray-100 space-y-1" : "space-y-1"}>
        {fieldList.map((f) => this.renderFieldItem(f, depth))}
      </div>
    );
  }

  renderFieldItem(f, depth = 0) {
    const name = f.name || "?";
    const type = f.type || "string";
    const hasSubFields = Array.isArray(f.fields)
      ? f.fields.length > 0
      : !!(f.fields && typeof f.fields === "object" && Object.keys(f.fields).length > 0);
    const typeBg = type === "object" ? "bg-blue-50 text-blue-700" : type === "array" ? "bg-emerald-50 text-emerald-700" : type === "html" ? "bg-orange-50 text-orange-700" : type === "enum" ? "bg-pink-50 text-pink-700" : type === "boolean" ? "bg-cyan-50 text-cyan-700" : type === "float" || type === "integer" ? "bg-amber-50 text-amber-700" : "bg-gray-50 text-gray-600";

    return (
      <div class={`rounded-lg ${depth === 0 ? "border border-gray-100 bg-white" : ""} ${hasSubFields ? "" : ""}`}>
        <div class={`flex items-start gap-2 text-sm ${depth === 0 ? "p-2.5" : "py-1.5 px-1"}`}>
          <div class="flex items-center gap-2 flex-1 min-w-0">
            {hasSubFields && <IconChevronDown size={12} class="text-gray-400 shrink-0 mt-0.5" />}
            <span class="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded text-gray-700 shrink-0">{name}</span>
            <span class={`text-[10px] font-medium px-1.5 py-0.5 rounded ${typeBg} shrink-0`}>{type}{f.item_type ? `<${f.item_type}>` : ""}</span>
            {f.required && <span class="text-[10px] font-medium px-1.5 py-0.5 rounded bg-red-50 text-red-600 shrink-0">requis</span>}
            {f.const && <span class="text-[10px] font-medium px-1.5 py-0.5 rounded bg-gray-200 text-gray-600 shrink-0">const</span>}
            {f.ai_instruction && <Badge variant="purple">IA</Badge>}
            {f.exclude_from_extraction && <span class="text-[10px] font-medium px-1.5 py-0.5 rounded bg-yellow-50 text-yellow-600 shrink-0">exclu IA</span>}
            {f.description && <span class="text-gray-400 text-xs truncate">{f.description}</span>}
          </div>
        </div>

        {/* Meta details */}
        {(f.default !== undefined || f.ai_instruction || f.validation || f.transform || f.mapping || f.unit || f.calculation) && (
          <div class={`flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-gray-500 ${depth === 0 ? "px-2.5 pb-2" : "px-1 pb-1"}`}>
            {f.default !== undefined && <span>défaut: <code class="bg-gray-50 px-1 rounded">{JSON.stringify(f.default)}</code></span>}
            {f.unit && <span>unité: <code class="bg-gray-50 px-1 rounded">{f.unit}</code></span>}
            {f.validation && <span>validation: <code class="bg-gray-50 px-1 rounded">{typeof f.validation === "object" ? Object.entries(f.validation).map(([k, v]) => `${k}=${v}`).join(", ") : f.validation}</code></span>}
            {f.transform && <span>transform: <code class="bg-gray-50 px-1 rounded">{Array.isArray(f.transform) ? f.transform.join(", ") : f.transform}</code></span>}
            {f.mapping && <span>mapping: <code class="bg-gray-50 px-1 rounded">{Object.keys(f.mapping).length} valeurs</code></span>}
            {f.calculation && <span>calcul: <code class="bg-gray-50 px-1 rounded">{f.calculation}</code></span>}
            {f.ai_instruction && <span class="text-violet-500 italic">{f.ai_instruction}</span>}
          </div>
        )}

        {/* Options for enum */}
        {f.options && f.options.length > 0 && (
          <div class={`flex flex-wrap gap-1 ${depth === 0 ? "px-2.5 pb-2" : "px-1 pb-1"}`}>
            {f.options.map((opt) => <span class="text-[10px] bg-pink-50 text-pink-600 px-1.5 py-0.5 rounded">{opt}</span>)}
          </div>
        )}

        {/* Sub-fields for object type */}
        {hasSubFields && (
          <div class={`${depth === 0 ? "px-2.5 pb-2.5" : "pb-1"}`}>
            {this.renderFieldList(f, depth + 1)}
          </div>
        )}
      </div>
    );
  }

  render() {
    const {
      formats, loading, error, toast, toastType, uploading, previewFormat,
      editFormat, editFields, editVersion, editTargetEntity, saving,
      createOpen, createName, createDescription, createFields, createVersion, createTargetEntity, creating,
    } = this.state;

    const editPreview = editFormat ? this.buildYamlFromEditor("edit", editFormat.yaml_content || {}) : null;
    const createPreview = this.buildYamlFromEditor("create");

    return (
      <div class="max-w-7xl mx-auto px-4 py-8">
        <Toast message={toast} type={toastType} onClose={() => this.setState({ toast: null })} />

        <PageHeader
          title="Formats Custom"
          subtitle={`${formats.length} format${formats.length !== 1 ? "s" : ""} disponible${formats.length !== 1 ? "s" : ""}`}
        />

        <div class="mb-4 flex justify-end">
          <button
            class="inline-flex items-center gap-2 gradient-primary text-white font-medium rounded-lg px-4 py-2 text-sm transition-all hover:shadow-lg hover:shadow-indigo-500/25"
            onClick={() => this.setState({ createOpen: true, createFields: [], createVersion: "1.0", createTargetEntity: "product" })}
          >
            <IconPlus size={14} /> Nouveau format
          </button>
        </div>

        {error && (
          <div class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-6 text-sm flex items-center justify-between">
            {error}
            <button class="text-red-400 hover:text-red-600" onClick={() => this.setState({ error: null })}>✕</button>
          </div>
        )}

        {/* Upload zone */}
        <div class="mb-6">
          <DropZone
            onFiles={(files) => this.handleUpload(files)}
            uploading={uploading}
            accept=".yaml,.yml"
            label="Glissez un fichier YAML ici pour ajouter un format custom"
          />
        </div>

        {loading ? (
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-5">
            {[1, 2, 3].map(() => <SkeletonCard lines={3} />)}
          </div>
        ) : formats.length === 0 ? (
          <EmptyState
            icon={<IconLayers size={28} />}
            title="Aucun format"
            description="Uploadez un fichier YAML pour définir la structure de vos fiches produits custom."
          />
        ) : (
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-5 stagger-children">
            {formats.map((f) => (
              <Card class="min-h-[260px] flex flex-col">
                <div class="flex items-start justify-between mb-3">
                  <div class="flex items-center gap-2 flex-1 min-w-0">
                    <div class="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center flex-shrink-0">
                      <IconLayers size={18} class="text-indigo-500" />
                    </div>
                    <h3 class="font-semibold text-gray-900 truncate text-sm flex-1 min-w-0">{f.name}</h3>
                  </div>
                  <div class="flex-shrink-0 ml-2">
                    <Badge variant="indigo" size="sm">{f.field_count} champs</Badge>
                  </div>
                </div>
                {f.description && (
                  <p class="text-sm text-gray-500 line-clamp-2 mb-4 flex-1">{f.description}</p>
                )}
                <p class="text-xs text-gray-400 mb-4">
                  {f.created_at ? new Date(f.created_at).toLocaleDateString("fr-FR") : ""}
                </p>
                <div class="flex items-center gap-2 pt-4 border-t border-gray-100 mt-auto">
                  <button
                    class="inline-flex items-center gap-2 text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 text-sm font-medium px-3 py-2 rounded-md transition-colors"
                    onClick={() => this.openPreview(f)}
                  >
                    <IconEye size={13} /> Preview
                  </button>
                  <button
                    class="inline-flex items-center gap-2 text-gray-500 hover:text-gray-700 hover:bg-gray-50 text-sm font-medium px-3 py-2 rounded-md transition-colors"
                    onClick={() => this.openEdit(f)}
                  >
                    <IconEdit size={13} /> Modifier
                  </button>
                  <button
                    class="inline-flex items-center gap-2 text-red-500 hover:text-red-700 hover:bg-red-50 text-sm font-medium px-3 py-2 rounded-md transition-colors"
                    onClick={() => this.handleDelete(f.id)}
                  >
                    <IconTrash size={13} /> Supprimer
                  </button>
                </div>
              </Card>
            ))}
          </div>
        )}

        {/* Preview modal */}
        <Modal
          open={!!previewFormat}
          onClose={() => this.setState({ previewFormat: null })}
          title={previewFormat ? `Preview : ${previewFormat.name}` : ""}
          wide
        >
          {previewFormat && (
            <div>
              {previewFormat.description && (
                <p class="text-sm text-gray-500 mb-3">{previewFormat.description}</p>
              )}
              <div class="mb-4 flex items-center gap-2">
                <button
                  class="inline-flex items-center gap-2 text-sm bg-indigo-50 text-indigo-700 hover:bg-indigo-100 px-3 py-1.5 rounded-md"
                  onClick={() => this.handleDownloadFormat(previewFormat)}
                >
                  <IconDownload size={13} /> Télécharger YAML
                </button>
                <button
                  class="inline-flex items-center gap-2 text-sm bg-gray-100 text-gray-700 hover:bg-gray-200 px-3 py-1.5 rounded-md"
                  onClick={() => this.setState({ previewFormat: null }, () => this.openEdit(previewFormat))}
                >
                  <IconEdit size={13} /> Modifier
                </button>
              </div>
              {/* Format metadata */}
              {previewFormat.yaml_content && (
                <div class="flex flex-wrap gap-2 mb-4">
                  {previewFormat.yaml_content.format_version && <span class="text-[10px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">v{previewFormat.yaml_content.format_version}</span>}
                  {previewFormat.yaml_content.target_entity && <span class="text-[10px] bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full">{previewFormat.yaml_content.target_entity}</span>}
                  {previewFormat.yaml_content.processing?.translate_to && <span class="text-[10px] bg-green-50 text-green-600 px-2 py-0.5 rounded-full">Langue: {previewFormat.yaml_content.processing.translate_to}</span>}
                  {previewFormat.yaml_content.processing?.currency && <span class="text-[10px] bg-yellow-50 text-yellow-600 px-2 py-0.5 rounded-full">{previewFormat.yaml_content.processing.currency}</span>}
                  {previewFormat.yaml_content.processing?.clean_html && <span class="text-[10px] bg-orange-50 text-orange-600 px-2 py-0.5 rounded-full">clean HTML</span>}
                </div>
              )}
              <h4 class="text-sm font-semibold mb-2">Champs</h4>
              {this.renderFieldList(previewFormat.yaml_content)}
            </div>
          )}
        </Modal>

        {/* Edit modal */}
        <Modal
          open={!!editFormat}
          onClose={() => this.setState({ editFormat: null })}
          title={editFormat ? `Modifier : ${editFormat.name}` : ""}
          wide
        >
          {editFormat && (
            <div class="grid grid-cols-1 xl:grid-cols-2 gap-6 min-h-[calc(100vh-170px)]">
              <div class="space-y-4 overflow-auto pr-1">
                <div class="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
                  <h3 class="text-sm font-semibold text-gray-800">Métadonnées format</h3>
                  <div>
                    <label class="block text-xs font-medium text-gray-500 mb-1">Nom</label>
                    <input
                      class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus-glow"
                      value={editFormat.name || ""}
                      onInput={(e) => this.setState({ editFormat: { ...editFormat, name: e.target.value } })}
                    />
                  </div>
                  <div>
                    <label class="block text-xs font-medium text-gray-500 mb-1">Description</label>
                    <textarea
                      rows={2}
                      class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-y focus-glow"
                      value={editFormat.description || ""}
                      onInput={(e) => this.setState({ editFormat: { ...editFormat, description: e.target.value } })}
                    />
                  </div>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label class="block text-xs font-medium text-gray-500 mb-1">Version</label>
                      <input
                        class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus-glow"
                        value={editVersion}
                        onInput={(e) => this.setState({ editVersion: e.target.value })}
                      />
                    </div>
                    <div>
                      <label class="block text-xs font-medium text-gray-500 mb-1">Entité cible</label>
                      <input
                        class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus-glow"
                        value={editTargetEntity}
                        onInput={(e) => this.setState({ editTargetEntity: e.target.value })}
                      />
                    </div>
                  </div>
                </div>

                <div class="bg-white rounded-xl border border-gray-200 p-4">
                  <div class="flex items-center justify-between mb-3">
                    <h3 class="text-sm font-semibold text-gray-800">Champs ({editFields.length})</h3>
                    <button
                      class="inline-flex items-center gap-1.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded-lg px-3 py-1.5 text-xs font-medium"
                      onClick={() => this.addEditorField("edit")}
                    >
                      <IconPlus size={12} /> Ajouter un champ
                    </button>
                  </div>
                  {this.renderEditorFields("edit")}
                </div>

                <div class="flex justify-end gap-3 pt-2">
                  <button
                    class="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
                    onClick={() => this.setState({ editFormat: null })}
                  >
                    Annuler
                  </button>
                  <button
                    class="bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg px-5 py-2 text-sm transition-colors disabled:opacity-50"
                    disabled={saving || !(editFormat.name || "").trim()}
                    onClick={() => this.handleSaveEdit()}
                  >
                    {saving ? <span class="flex items-center gap-2"><IconSpinner size={14} /> Sauvegarde...</span> : "Sauvegarder"}
                  </button>
                </div>
              </div>

              <div class="bg-gradient-to-b from-indigo-50/60 to-white rounded-2xl border border-indigo-100 p-4 overflow-auto">
                <h3 class="text-sm font-semibold text-indigo-800 mb-2">Preview en direct</h3>
                <p class="text-xs text-indigo-600 mb-3">Aperçu de rendu de la fiche format pendant l'édition.</p>
                <div class="bg-white rounded-xl border border-gray-100 p-4">
                  <div class="flex flex-wrap gap-2 mb-4">
                    <span class="text-[10px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">v{editPreview?.format_version || "1.0"}</span>
                    <span class="text-[10px] bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full">{editPreview?.target_entity || "product"}</span>
                  </div>
                  {this.renderFieldList(editPreview)}
                </div>
              </div>
            </div>
          )}
        </Modal>

        {/* Create modal */}
        <Modal
          open={createOpen}
          onClose={() => this.setState({ createOpen: false })}
          title="Nouveau format"
          wide
        >
          <div class="grid grid-cols-1 xl:grid-cols-2 gap-6 min-h-[calc(100vh-170px)]">
            <div class="space-y-4 overflow-auto pr-1">
              <div class="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
                <h3 class="text-sm font-semibold text-gray-800">Métadonnées format</h3>
                <div>
                  <label class="block text-xs font-medium text-gray-500 mb-1">Nom</label>
                  <input
                    class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus-glow"
                    value={createName}
                    onInput={(e) => this.setState({ createName: e.target.value })}
                    placeholder="Ex: Fiche Prestashop"
                  />
                </div>
                <div>
                  <label class="block text-xs font-medium text-gray-500 mb-1">Description</label>
                  <textarea
                    class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus-glow resize-y"
                    rows={2}
                    value={createDescription}
                    onInput={(e) => this.setState({ createDescription: e.target.value })}
                  />
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label class="block text-xs font-medium text-gray-500 mb-1">Version</label>
                    <input
                      class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus-glow"
                      value={createVersion}
                      onInput={(e) => this.setState({ createVersion: e.target.value })}
                    />
                  </div>
                  <div>
                    <label class="block text-xs font-medium text-gray-500 mb-1">Entité cible</label>
                    <input
                      class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus-glow"
                      value={createTargetEntity}
                      onInput={(e) => this.setState({ createTargetEntity: e.target.value })}
                    />
                  </div>
                </div>
              </div>

              <div class="bg-white rounded-xl border border-gray-200 p-4">
                <div class="flex items-center justify-between mb-3">
                  <h3 class="text-sm font-semibold text-gray-800">Champs ({createFields.length})</h3>
                  <button
                    class="inline-flex items-center gap-1.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded-lg px-3 py-1.5 text-xs font-medium"
                    onClick={() => this.addEditorField("create")}
                  >
                    <IconPlus size={12} /> Ajouter un champ
                  </button>
                </div>
                {this.renderEditorFields("create")}
              </div>

              <div class="flex justify-end gap-3 pt-2">
                <button
                  class="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
                  onClick={() => this.setState({ createOpen: false })}
                >
                  Annuler
                </button>
                <button
                  class="bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg px-5 py-2 text-sm transition-colors disabled:opacity-50"
                  disabled={creating || !createName.trim()}
                  onClick={() => this.handleCreateFormat()}
                >
                  {creating ? <span class="flex items-center gap-2"><IconSpinner size={14} /> Création...</span> : "Créer"}
                </button>
              </div>
            </div>

            <div class="bg-gradient-to-b from-indigo-50/60 to-white rounded-2xl border border-indigo-100 p-4 overflow-auto">
              <h3 class="text-sm font-semibold text-indigo-800 mb-2">Preview en direct</h3>
              <p class="text-xs text-indigo-600 mb-3">Visualisez instantanément le rendu du format en création.</p>
              <div class="bg-white rounded-xl border border-gray-100 p-4">
                <div class="flex flex-wrap gap-2 mb-4">
                  <span class="text-[10px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">v{createPreview?.format_version || "1.0"}</span>
                  <span class="text-[10px] bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full">{createPreview?.target_entity || "product"}</span>
                </div>
                {this.renderFieldList(createPreview)}
              </div>
            </div>
          </div>
        </Modal>
      </div>
    );
  }
}
