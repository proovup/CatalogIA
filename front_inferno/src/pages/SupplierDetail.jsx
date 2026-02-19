import { Component } from "inferno";
import { Link } from "inferno-router";
import { api } from "../api";
import { DEFAULT_PROVIDER, DEFAULT_MODEL } from "../constants";
import Card from "../components/Card";
import Badge from "../components/Badge";
import Field from "../components/Field";
import DropZone from "../components/DropZone";
import Toast from "../components/Toast";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import { IconSpinner, IconFileText, IconSave, IconTrash, IconZap, IconSearch, IconArrowRight, IconPackage, IconUpload as IconUploadIcon, IconCheckCircle, IconAlertCircle, IconClock } from "../components/Icons";

const ROLE_LABELS = {
  master: "Feuille principale",
  logistique: "Logistique",
  media: "Médias",
  technique: "Technique",
  reglementaire: "Réglementaire",
  config: "Configuration",
  metadata: "Métadonnées",
  enrichment: "Enrichissement",
};

const ROLE_COLORS = {
  master: "bg-indigo-100 text-indigo-800",
  logistique: "bg-blue-100 text-blue-800",
  media: "bg-purple-100 text-purple-800",
  technique: "bg-teal-100 text-teal-800",
  reglementaire: "bg-orange-100 text-orange-800",
  config: "bg-gray-100 text-gray-700",
  metadata: "bg-gray-100 text-gray-500",
  enrichment: "bg-cyan-100 text-cyan-800",
};

const RELATION_LABELS = {
  master: "Principal",
  "1:1": "1 pour 1",
  "1:N": "1 vers N",
};

export default class SupplierDetail extends Component {
  constructor(props) {
    super(props);
    this.state = {
      supplier: null,
      documents: [],
      activeTab: "documents",
      loading: true,
      saving: false,
      uploading: false,
      error: null,
      toast: null,
      toastType: "success",
      // Editable
      name: "",
      description: "",
      is_active: "active",
      // Extraction
      extractingDocId: null,
      extractionProgress: null,
      formats: [],
      selectedFormat: "default",
      sourceMode: "document",
      presentedMode: "docling_ocr",
      websiteStartUrl: "",
      websiteCrawlMode: "manual",
      websiteUrlsText: "",
      websiteMaxPages: 30,
      websiteMaxDepth: 2,
      websiteMaxProductsInput: "",
      websiteExtracting: false,
      // Analysis
      analyzingDocId: null,
      analysis: null,
      analysisDocId: null,
      analysisStep: "selection",
      fieldMappingOverride: {},
      maxProductsInput: "",
      previewRowsCount: 10,
    };
  }

  componentDidMount() {
    this.load();
    this.loadFormats();
  }

  async load() {
    const id = this.props.match.params.id;
    this.setState({ loading: true, error: null });
    try {
      const [supplier, documents] = await Promise.all([
        api.getSupplier(id),
        api.getSupplierDocuments(id),
      ]);
      this.setState({
        supplier,
        documents,
        loading: false,
        name: supplier.name || "",
        description: supplier.description || "",
        is_active: supplier.is_active || "active",
      });
    } catch (e) {
      this.setState({ error: e.message, loading: false });
    }
  }

  async loadFormats() {
    try {
      const res = await api.listFormats();
      const list = res.formats || [];
      const detailed = await Promise.all(
        list.map(async (f) => {
          const id = f.id || f.key;
          if (!id) return f;
          try {
            const full = await api.getFormat(id);
            return {
              ...f,
              id: full.id || f.id,
              fields: this.extractFieldNamesFromYaml(full.yaml_content),
              yaml_content: full.yaml_content,
            };
          } catch {
            return f;
          }
        }),
      );
      this.setState({ formats: detailed });
    } catch {
      try {
        const legacy = await api.listFormatsLegacy();
        this.setState({ formats: legacy || [] });
      } catch {}
    }
  }

  showToast(message, type = "success") {
    this.setState({ toast: message, toastType: type });
    setTimeout(() => this.setState({ toast: null }), 4000);
  }

  async handleSave() {
    const { supplier, name, description, is_active } = this.state;
    this.setState({ saving: true, error: null });
    try {
      await api.updateSupplier(supplier.id, {
        name: name.trim(),
        description: description.trim() || null,
        is_active,
      });
      this.showToast("Fournisseur sauvegardé");
      this.setState({ saving: false });
    } catch (e) {
      this.setState({ error: e.message, saving: false });
    }
  }

  async handleDelete() {
    if (!confirm("Supprimer ce fournisseur ?")) return;
    try {
      await api.deleteSupplier(this.state.supplier.id);
      window.location.href = "/suppliers";
    } catch (e) {
      this.setState({ error: e.message });
    }
  }

  async handleUpload(files) {
    const { supplier } = this.state;
    this.setState({ uploading: true, error: null });
    try {
      for (const file of files) {
        await api.uploadDocument(file, supplier.id);
      }
      this.showToast(`${files.length} fichier${files.length > 1 ? "s" : ""} uploadé${files.length > 1 ? "s" : ""}`);
      const documents = await api.getSupplierDocuments(supplier.id);
      this.setState({ documents, uploading: false });
    } catch (e) {
      this.setState({ error: e.message, uploading: false });
    }
  }

  async handleAnalyze(docId) {
    const provider = localStorage.getItem("default_provider") || DEFAULT_PROVIDER;
    const model = localStorage.getItem("default_model") || DEFAULT_MODEL;
    this.setState({
      analyzingDocId: docId,
      analysis: null,
      analysisDocId: null,
      analysisStep: "selection",
      fieldMappingOverride: {},
      maxProductsInput: "",
      error: null,
    });
    try {
      const res = await api.analyzeDocument(docId, provider, model);
      if (this.state.supplier?.id) {
        const documents = await api.getSupplierDocuments(this.state.supplier.id);
        this.setState({ documents });
      }
      if (res.skip_analysis) {
        this.handleExtract(docId, null, { source_mode: "document" });
        return;
      }
      this.setState({ analysis: res.analysis, analysisDocId: docId, analyzingDocId: null });
    } catch (e) {
      this.setState({ error: e.message, analyzingDocId: null });
    }
  }

  updateSheetAnalysis(index, field, value) {
    const { analysis } = this.state;
    if (!analysis) return;
    const sheets = [...analysis.sheets];
    sheets[index] = { ...sheets[index], [field]: value };

    if (field === "role" && value === "master") {
      const newMaster = sheets[index].name;
      sheets.forEach((s, i) => {
        if (i !== index && s.role === "master") {
          sheets[i] = { ...s, role: "enrichment", relation: "1:1" };
        }
      });
      sheets[index].relation = "master";
      this.setState({ analysis: { ...analysis, master_sheet: newMaster, sheets } });
    } else {
      this.setState({ analysis: { ...analysis, sheets } });
    }
  }

  toggleSheetExcluded(index) {
    const { analysis } = this.state;
    if (!analysis) return;
    const sheets = [...(analysis.sheets || [])];
    const current = sheets[index];
    const excluded = !current.excluded;
    sheets[index] = {
      ...current,
      excluded,
      role: excluded ? "metadata" : (current.role || "enrichment"),
    };
    this.setState({ analysis: { ...analysis, sheets } });
  }

  getFormatFieldNames() {
    const { selectedFormat, formats } = this.state;
    const fallback = ["name", "description", "price", "category", "reference", "brand"];
    if (selectedFormat === "default") return fallback;

    const selected = (formats || []).find((f) => (f.key || f.name || f.id) === selectedFormat);
    if (!selected) return fallback;
    if (Array.isArray(selected.fields) && selected.fields.length > 0) {
      return selected.fields.filter(Boolean);
    }
    if (selected.yaml_content) {
      const fromYaml = this.extractFieldNamesFromYaml(selected.yaml_content);
      if (fromYaml.length > 0) return fromYaml;
    }
    return fallback;
  }

  extractFieldNamesFromYaml(yamlContent) {
    const fieldsRoot = yamlContent && yamlContent.fields;
    if (!fieldsRoot) return [];

    const result = [];
    const walk = (fieldDef, prefix = "") => {
      if (!fieldDef) return;
      if (Array.isArray(fieldDef)) {
        fieldDef.forEach((f) => walk(f, prefix));
        return;
      }
      if (typeof fieldDef !== "object") return;

      const name = fieldDef.name || "";
      const path = name ? (prefix ? `${prefix}.${name}` : name) : "";
      if (path && !fieldDef.exclude_from_extraction && !fieldDef.const) {
        result.push(path);
      }

      const sub = fieldDef.fields;
      if (Array.isArray(sub)) {
        sub.forEach((s) => walk(s, path));
      } else if (sub && typeof sub === "object") {
        Object.entries(sub).forEach(([k, v]) => {
          if (v && typeof v === "object") {
            walk({ name: k, ...v }, path);
          } else {
            walk({ name: k }, path);
          }
        });
      }
    };

    if (Array.isArray(fieldsRoot)) {
      fieldsRoot.forEach((f) => walk(f));
    } else if (fieldsRoot && typeof fieldsRoot === "object") {
      Object.entries(fieldsRoot).forEach(([k, v]) => {
        if (v && typeof v === "object") {
          walk({ name: k, ...v });
        } else {
          walk({ name: k });
        }
      });
    }

    return Array.from(new Set(result));
  }

  proceedToMappingStep() {
    const { analysis } = this.state;
    if (!analysis) return;
    const sheets = analysis.sheets || [];
    const master = sheets.find((s) => s.name === analysis.master_sheet);
    if (!master || master.excluded || master.role === "metadata") {
      this.setState({ error: "Veuillez définir une feuille principale non exclue avant de continuer." });
      return;
    }

    const fields = this.getFormatFieldNames();
    const currentMap = { ...(this.state.fieldMappingOverride || {}) };
    const cols = (master.columns || []).map((c) => (c == null ? "" : String(c)));
    fields.forEach((field) => {
      if (Object.prototype.hasOwnProperty.call(currentMap, field)) return;
      const hit = cols.findIndex((c) => c.toLowerCase() === field.toLowerCase() || c.toLowerCase().includes(field.toLowerCase()));
      currentMap[field] = hit >= 0 ? String(hit) : "";
    });

    this.setState({ analysisStep: "mapping", fieldMappingOverride: currentMap });
  }

  updateFieldMapping(field, value) {
    this.setState((prev) => ({
      fieldMappingOverride: {
        ...(prev.fieldMappingOverride || {}),
        [field]: value == null ? "" : String(value),
      },
    }));
  }

  async handleExtract(docId, analysisOverride, options = {}) {
    const { selectedFormat, analysis, analysisDocId, sourceMode, presentedMode } = this.state;
    const finalAnalysis = analysisOverride !== undefined ? analysisOverride : (analysisDocId === docId ? analysis : null);
    const provider = localStorage.getItem("default_provider") || DEFAULT_PROVIDER;
    const model = localStorage.getItem("default_model") || DEFAULT_MODEL;
    this.setState({ extractingDocId: docId, extractionProgress: null, error: null, analysis: null, analysisDocId: null });
    try {
      const mergedOptions = {
        source_mode: sourceMode,
        presented_mode: presentedMode,
        provider,
        model_name: model,
        ...options,
      };
      const { job_id } = await api.extractProducts(docId, selectedFormat, finalAnalysis, mergedOptions);
      api.streamExtractionProgress(
        job_id,
        (data) => this.setState({ extractionProgress: data }),
        (data) => {
          this.showToast(`${data.count} produit${data.count > 1 ? "s" : ""} extrait${data.count > 1 ? "s" : ""}`);
          this.setState({ extractingDocId: null, extractionProgress: null });
          if (this.state.supplier?.id) {
            api.getSupplierDocuments(this.state.supplier.id)
              .then((documents) => this.setState({ documents }))
              .catch(() => {});
          }
        },
        (err) => {
          this.setState({ error: err, extractingDocId: null, extractionProgress: null });
        },
      );
    } catch (e) {
      this.setState({ error: e.message, extractingDocId: null, extractionProgress: null });
    }
  }

  async handleWebsiteExtract() {
    const {
      supplier,
      selectedFormat,
      websiteStartUrl,
      websiteCrawlMode,
      websiteUrlsText,
      websiteMaxPages,
      websiteMaxDepth,
      websiteMaxProductsInput,
    } = this.state;

    if (!websiteStartUrl.trim()) {
      this.setState({ error: "URL de départ requise pour l'extraction website." });
      return;
    }

    const urls = websiteUrlsText
      .split("\n")
      .map((u) => u.trim())
      .filter(Boolean);
    const maxProducts = Number(websiteMaxProductsInput);

    const provider = localStorage.getItem("default_provider") || DEFAULT_PROVIDER;
    const model = localStorage.getItem("default_model") || DEFAULT_MODEL;

    const payload = {
      supplier_id: supplier?.id || null,
      format_name: selectedFormat,
      website: {
        start_url: websiteStartUrl.trim(),
        crawl_mode: websiteCrawlMode,
        urls: urls.length ? urls : null,
        max_pages: Number(websiteMaxPages) > 0 ? Number(websiteMaxPages) : 30,
        max_depth: Number(websiteMaxDepth) >= 0 ? Number(websiteMaxDepth) : 2,
      },
      max_products: Number.isInteger(maxProducts) && maxProducts > 0 ? maxProducts : null,
      provider,
      model_name: model,
    };

    this.setState({ websiteExtracting: true, extractionProgress: null, error: null });
    try {
      const { job_id } = await api.extractWebsiteProducts(payload);
      api.streamExtractionProgress(
        job_id,
        (data) => this.setState({ extractionProgress: data }),
        async (data) => {
          this.showToast(`${data.count} produit${data.count > 1 ? "s" : ""} extrait${data.count > 1 ? "s" : ""} (website)`);
          this.setState({ websiteExtracting: false, extractionProgress: null });
          if (supplier?.id) {
            const documents = await api.getSupplierDocuments(supplier.id);
            this.setState({ documents });
          }
        },
        (err) => {
          this.setState({ error: err, websiteExtracting: false, extractionProgress: null });
        },
      );
    } catch (e) {
      this.setState({ error: e.message, websiteExtracting: false, extractionProgress: null });
    }
  }

  renderAnalysis() {
    const {
      analysis,
      analysisDocId,
      extractingDocId,
      documents,
      analysisStep,
      fieldMappingOverride,
      maxProductsInput,
      previewRowsCount,
    } = this.state;
    if (!analysis || !analysisDocId) return null;

    const doc = documents.find((d) => d.id === analysisDocId);
    const sheets = analysis.sheets || [];
    const master = sheets.find((s) => s.name === analysis.master_sheet);
    const formatFields = this.getFormatFieldNames();

    const launchWithMapping = () => {
      const cleaned = {};
      Object.entries(fieldMappingOverride || {}).forEach(([k, v]) => {
        if (v === "" || v == null) return;
        const n = Number(v);
        if (Number.isInteger(n) && n >= 0) cleaned[k] = n;
      });
      const maxProducts = Number(maxProductsInput);
      const options = {
        field_mapping_override: cleaned,
        max_products: Number.isInteger(maxProducts) && maxProducts > 0 ? maxProducts : null,
      };
      this.handleExtract(analysisDocId, analysis, options);
    };

    return (
      <div class="mt-4 bg-white rounded-lg border border-gray-200 p-4">
        <div class="flex items-center justify-between mb-3">
          <div>
            <h4 class="text-sm font-semibold">Analyse des feuilles</h4>
            <p class="text-xs text-gray-500">{doc ? doc.filename : ""} — {sheets.length} feuille{sheets.length > 1 ? "s" : ""}</p>
          </div>
          <div class="flex gap-2">
            <button
              class="bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg px-3 py-1.5 text-xs transition-colors"
              onClick={() => this.setState({ analysis: null, analysisDocId: null, analysisStep: "selection" })}
            >
              Annuler
            </button>
            {analysisStep === "selection" ? (
              <button
                class="bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg px-4 py-1.5 text-xs transition-colors disabled:opacity-50"
                disabled={!!extractingDocId}
                onClick={() => this.proceedToMappingStep()}
              >
                Étape suivante
              </button>
            ) : (
              <button
                class="bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg px-4 py-1.5 text-xs transition-colors disabled:opacity-50"
                disabled={!!extractingDocId}
                onClick={launchWithMapping}
              >
                Lancer extraction
              </button>
            )}
          </div>
        </div>

        <div class="bg-indigo-50 border border-indigo-200 rounded-lg p-2 mb-3">
          <p class="text-xs text-indigo-800">
            <strong>Principale :</strong> {analysis.master_sheet}
            {analysis.join_columns && analysis.join_columns.length > 0 && (
              <span> — <strong>Liaison :</strong> {analysis.join_columns.join(", ")}</span>
            )}
          </p>
        </div>

        {analysisStep === "selection" ? (
        <div class="space-y-2">
          <div class="flex justify-end">
            <div>
              <label class="block text-[10px] text-gray-500 mb-0.5">Aperçu lignes</label>
              <select
                class="border border-gray-300 rounded px-1.5 py-0.5 text-[10px]"
                value={previewRowsCount}
                onChange={(e) => this.setState({ previewRowsCount: Number(e.target.value) || 10 })}
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
              </select>
            </div>
          </div>
          {sheets.map((sheet, idx) => (
            <div
              key={sheet.name}
              class={`border rounded-lg p-3 ${sheet.excluded ? "border-red-200 bg-red-50/40" : sheet.role === "master" ? "border-indigo-300 bg-indigo-50/50" : sheet.role === "metadata" ? "border-gray-200 bg-gray-50 opacity-60" : "border-gray-200"}`}
            >
              <div class="flex items-center gap-2 mb-1">
                <span class="font-medium text-xs">{sheet.name}</span>
                <span class={`inline-block px-1.5 py-0.5 rounded-full text-[10px] font-medium ${ROLE_COLORS[sheet.role] || "bg-gray-100 text-gray-600"}`}>
                  {ROLE_LABELS[sheet.role] || sheet.role}
                </span>
                <span class="text-[10px] text-gray-500">{sheet.total_rows || 0} lignes</span>
                {sheet.relation && sheet.relation !== "master" && (
                  <span class={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${sheet.relation === "1:N" ? "bg-amber-100 text-amber-800" : "bg-green-100 text-green-800"}`}>
                    {RELATION_LABELS[sheet.relation] || sheet.relation}
                  </span>
                )}
                {sheet.excluded && (
                  <span class="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-100 text-red-700">
                    Exclue
                  </span>
                )}
              </div>

              {sheet.description && (
                <p class="text-[10px] text-gray-500 mb-1">{sheet.description}</p>
              )}

              <div class="flex flex-wrap gap-2 mt-1">
                <div>
                  <label class="block text-[10px] text-gray-500 mb-0.5">Rôle</label>
                  <select
                    class="border border-gray-300 rounded px-1.5 py-0.5 text-[10px]"
                    value={sheet.role}
                    onChange={(e) => this.updateSheetAnalysis(idx, "role", e.target.value)}
                  >
                    <option value="master">Principal</option>
                    <option value="logistique">Logistique</option>
                    <option value="media">Médias</option>
                    <option value="technique">Technique</option>
                    <option value="reglementaire">Réglementaire</option>
                    <option value="config">Configuration</option>
                    <option value="metadata">Métadonnées (ignoré)</option>
                    <option value="enrichment">Enrichissement</option>
                  </select>
                </div>
                {sheet.role !== "master" && sheet.role !== "metadata" && (
                  <div>
                    <label class="block text-[10px] text-gray-500 mb-0.5">Relation</label>
                    <select
                      class="border border-gray-300 rounded px-1.5 py-0.5 text-[10px]"
                      value={sheet.relation}
                      onChange={(e) => this.updateSheetAnalysis(idx, "relation", e.target.value)}
                    >
                      <option value="1:1">1:1</option>
                      <option value="1:N">1:N</option>
                    </select>
                  </div>
                )}
                {sheet.role !== "metadata" && sheet.columns && sheet.columns.length > 0 && (
                  <div>
                    <label class="block text-[10px] text-gray-500 mb-0.5">Liaison</label>
                    <select
                      class="border border-gray-300 rounded px-1.5 py-0.5 text-[10px]"
                      value={sheet.join_on || ""}
                      onChange={(e) => this.updateSheetAnalysis(idx, "join_on", e.target.value || null)}
                    >
                      <option value="">-- Aucune --</option>
                      {sheet.columns.filter(Boolean).map((col) => (
                        <option value={col}>{col}</option>
                      ))}
                    </select>
                  </div>
                )}
                <div class="ml-auto self-end">
                  <button
                    class={`text-[10px] rounded px-2 py-1 ${sheet.excluded ? "bg-gray-200 text-gray-700" : "bg-red-100 text-red-700 hover:bg-red-200"}`}
                    onClick={() => this.toggleSheetExcluded(idx)}
                  >
                    {sheet.excluded ? "Réinclure" : "Exclure"}
                  </button>
                </div>
              </div>

              {sheet.columns && sheet.columns.length > 0 && (
                <div class="mt-1">
                  <div class="flex flex-wrap gap-0.5">
                    {sheet.columns.filter(Boolean).slice(0, 15).map((col) => (
                      <span class="bg-gray-100 text-gray-600 text-[10px] px-1 py-0.5 rounded">{col}</span>
                    ))}
                    {sheet.columns.filter(Boolean).length > 15 && (
                      <span class="text-[10px] text-gray-400">+{sheet.columns.filter(Boolean).length - 15}</span>
                    )}
                  </div>
                </div>
              )}

              {sheet.sample_rows && sheet.sample_rows.length > 0 && (
                <div class="mt-2 overflow-x-auto border border-gray-100 rounded">
                  <table class="min-w-full text-[10px]">
                    <thead class="bg-gray-50 text-gray-600">
                      <tr>
                        {(sheet.columns || []).map((col, ci) => (
                          <th key={`${sheet.name}-h-${ci}`} class="px-2 py-1 text-left whitespace-nowrap">{col || `col_${ci}`}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {sheet.sample_rows.slice(0, previewRowsCount).map((row, ri) => (
                        <tr key={`${sheet.name}-r-${ri}`} class="border-t border-gray-100">
                          {(sheet.columns || []).map((_, ci) => (
                            <td key={`${sheet.name}-c-${ri}-${ci}`} class="px-2 py-1 whitespace-nowrap text-gray-700">
                              {row && row[ci] != null ? String(row[ci]) : ""}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ))}
        </div>
        ) : (
          <div class="space-y-3">
            <div class="bg-gray-50 border border-gray-200 rounded-lg p-3">
              <p class="text-xs text-gray-700">
                Feuille principale: <strong>{master ? master.name : analysis.master_sheet}</strong>
              </p>
            </div>

            <div class="flex justify-end">
              <div>
                <label class="block text-[10px] text-gray-500 mb-0.5">Aperçu tableau (lignes)</label>
                <select
                  class="border border-gray-300 rounded px-1.5 py-0.5 text-[10px]"
                  value={previewRowsCount}
                  onChange={(e) => this.setState({ previewRowsCount: Number(e.target.value) || 10 })}
                >
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                </select>
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              {formatFields.map((field) => {
                const options = (master && master.columns ? master.columns : []).map((col, idx) => ({
                  index: idx,
                  label: col || `col_${idx}`,
                }));
                const selectedIdx = fieldMappingOverride[field] == null ? "" : String(fieldMappingOverride[field]);
                const selectedColIndex = selectedIdx === "" ? -1 : Number(selectedIdx);
                const sampleValues =
                  selectedColIndex >= 0 && master && Array.isArray(master.sample_rows)
                    ? master.sample_rows
                        .slice(0, 10)
                        .map((row) => (row && row[selectedColIndex] != null ? String(row[selectedColIndex]) : ""))
                        .filter((v) => v.trim())
                    : [];
                return (
                  <div key={`map-${field}`} class="border border-gray-200 rounded-lg p-2">
                    <label class="block text-[11px] font-medium text-gray-700 mb-1">{field}</label>
                    <select
                      class="w-full border border-gray-300 rounded px-2 py-1 text-xs"
                      value={selectedIdx}
                      onChange={(e) => this.updateFieldMapping(field, e.target.value)}
                    >
                      <option value="">-- Non assigné --</option>
                      {options.map((opt) => (
                        <option key={`opt-${field}-${opt.index}`} value={String(opt.index)}>{opt.label}</option>
                      ))}
                    </select>
                    {sampleValues.length > 0 && (
                      <div class="mt-2 bg-gray-50 border border-gray-100 rounded p-1.5">
                        <p class="text-[10px] text-gray-500 mb-1">Exemples de valeurs</p>
                        <div class="flex flex-wrap gap-1">
                          {sampleValues.slice(0, 6).map((v, i) => (
                            <span key={`sample-${field}-${i}`} class="text-[10px] px-1.5 py-0.5 bg-white border border-gray-200 rounded text-gray-700">
                              {v}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {master && Array.isArray(master.columns) && master.columns.length > 0 && Array.isArray(master.sample_rows) && master.sample_rows.length > 0 && (
              <div class="border border-gray-200 rounded-lg overflow-hidden">
                <div class="px-3 py-2 bg-gray-50 border-b border-gray-200">
                  <p class="text-xs font-medium text-gray-700">Aperçu complet de la feuille principale</p>
                </div>
                <div class="overflow-x-auto">
                  <table class="min-w-full text-[10px]">
                    <thead class="bg-gray-50 text-gray-600">
                      <tr>
                        {master.columns.map((col, ci) => (
                          <th key={`map-full-h-${ci}`} class="px-2 py-1 text-left whitespace-nowrap">{col || `col_${ci}`}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {master.sample_rows.slice(0, previewRowsCount).map((row, ri) => (
                        <tr key={`map-full-r-${ri}`} class="border-t border-gray-100">
                          {master.columns.map((_, ci) => (
                            <td key={`map-full-c-${ri}-${ci}`} class="px-2 py-1 whitespace-nowrap text-gray-700">
                              {row && row[ci] != null ? String(row[ci]) : ""}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div class="flex items-end justify-between gap-3">
              <div>
                <label class="block text-[11px] font-medium text-gray-600 mb-1">Limite produits (N)</label>
                <input
                  type="number"
                  min="1"
                  placeholder="Ex: 100"
                  class="border border-gray-300 rounded px-2 py-1 text-xs w-40"
                  value={maxProductsInput}
                  onInput={(e) => this.setState({ maxProductsInput: e.target.value })}
                />
              </div>
              <button
                class="bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg px-3 py-1.5 text-xs transition-colors"
                onClick={() => this.setState({ analysisStep: "selection" })}
              >
                Retour analyse
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  render() {
    const {
      supplier, documents, loading, saving, uploading, error, toast, toastType,
      name, description, is_active, extractingDocId, extractionProgress, formats, selectedFormat,
      analyzingDocId, analysisDocId, activeTab, sourceMode, presentedMode,
      websiteStartUrl, websiteCrawlMode, websiteUrlsText, websiteMaxPages, websiteMaxDepth,
      websiteMaxProductsInput, websiteExtracting,
    } = this.state;

    if (loading) {
      return (
        <div class="flex items-center justify-center py-32">
          <IconSpinner size={24} class="text-indigo-500" />
        </div>
      );
    }

    if (!supplier) {
      return (
        <div class="max-w-4xl mx-auto px-4 py-16 text-center text-gray-400">
          Fournisseur introuvable.
          <Link to="/suppliers" class="text-indigo-600 hover:underline ml-2">Retour</Link>
        </div>
      );
    }

    return (
      <div class="max-w-5xl mx-auto px-4 py-8">
        <Toast message={toast} type={toastType} onClose={() => this.setState({ toast: null })} />

        <PageHeader
          title={name}
          breadcrumb={[
            { label: "Fournisseurs", to: "/suppliers" },
            { label: name },
          ]}
        />

        <div class="mb-4 inline-flex rounded-lg border border-gray-200 p-1 bg-white">
          <button
            class={`px-3 py-1.5 text-sm rounded-md transition-colors ${activeTab === "overview" ? "bg-indigo-600 text-white" : "text-gray-700 hover:bg-gray-100"}`}
            onClick={() => this.setState({ activeTab: "overview" })}
          >
            Informations
          </button>
          <button
            class={`px-3 py-1.5 text-sm rounded-md transition-colors ${activeTab === "documents" ? "bg-indigo-600 text-white" : "text-gray-700 hover:bg-gray-100"}`}
            onClick={() => this.setState({ activeTab: "documents" })}
          >
            Documents & extraction
          </button>
        </div>

        {error && (
          <div class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-4 text-sm flex items-center justify-between">
            {error}
            <button class="text-red-400 hover:text-red-600" onClick={() => this.setState({ error: null })}>✕</button>
          </div>
        )}

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Informations + Config */}
          <div class={`space-y-4 ${activeTab === "documents" ? "hidden" : ""}`}>
            <Card>
              <h2 class="text-base font-semibold mb-4">Informations</h2>
              <div class="space-y-3">
                <Field label="Nom" value={name} onInput={(v) => this.setState({ name: v })} required />
                <Field label="Description" value={description} onInput={(v) => this.setState({ description: v })} textarea rows={3} />
                <div>
                  <label class="block text-sm font-medium text-gray-700 mb-1.5">Statut</label>
                  <select
                    class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all focus-glow"
                    value={is_active}
                    onChange={(e) => this.setState({ is_active: e.target.value })}
                  >
                    <option value="active">Actif</option>
                    <option value="inactive">Inactif</option>
                  </select>
                </div>
              </div>
              <div class="flex items-center gap-3 mt-5">
                <button
                  class="inline-flex items-center gap-2 gradient-primary text-white font-medium rounded-lg px-5 py-2 text-sm transition-all hover:shadow-lg hover:shadow-indigo-500/25 disabled:opacity-50"
                  disabled={saving || !name.trim()}
                  onClick={() => this.handleSave()}
                >
                  {saving ? <><IconSpinner size={14} /> Sauvegarde...</> : <><IconSave size={14} /> Sauvegarder</>}
                </button>
                <button
                  class="inline-flex items-center gap-2 bg-red-50 hover:bg-red-100 text-red-600 font-medium rounded-lg px-4 py-2 text-sm transition-colors"
                  onClick={() => this.handleDelete()}
                >
                  <IconTrash size={14} /> Supprimer
                </button>
              </div>
            </Card>

            {/* Extraction config */}
            <Card>
              <h3 class="text-sm font-semibold mb-3 text-gray-700">Config extraction</h3>
              <div>
                <label class="block text-xs font-medium text-gray-500 mb-1">Format YAML</label>
                <select
                  class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all focus-glow"
                  value={selectedFormat}
                  onChange={(e) => this.setState({ selectedFormat: e.target.value })}
                >
                  <option value="default">default</option>
                  {formats.map((f) => (
                    <option value={f.key || f.name || f.id}>{f.name}</option>
                  ))}
                </select>
              </div>
            </Card>

            {/* Quick links */}
            <Card>
              <h3 class="text-sm font-semibold mb-3 text-gray-700">Raccourcis</h3>
              <div class="space-y-2">
                <Link to="/products" class="flex items-center gap-2 text-sm text-indigo-600 hover:text-indigo-800 transition-colors">
                  <IconPackage size={14} /> Voir tous les produits
                </Link>
              </div>
            </Card>

            {/* Meta */}
            <div class="bg-gray-50 rounded-xl border border-gray-100 p-5 text-xs text-gray-500">
              <p><strong>ID :</strong> {supplier.id}</p>
              <p class="mt-1"><strong>Créé :</strong> {new Date(supplier.created_at).toLocaleString("fr-FR")}</p>
              <p class="mt-1"><strong>Modifié :</strong> {new Date(supplier.updated_at).toLocaleString("fr-FR")}</p>
            </div>
          </div>

          {/* Right: Documents (main section, takes 2/3) */}
          <div class={`${activeTab === "overview" ? "hidden" : ""} ${activeTab === "documents" ? "lg:col-span-3" : "lg:col-span-2"} space-y-6`}>
            {activeTab === "documents" && (
              <Card>
                <h3 class="text-sm font-semibold mb-3 text-gray-700">Config extraction</h3>
                <div class="space-y-3">
                  <label class="block text-xs font-medium text-gray-500 mb-1">Format YAML</label>
                  <select
                    class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all focus-glow"
                    value={selectedFormat}
                    onChange={(e) => this.setState({ selectedFormat: e.target.value })}
                  >
                    <option value="default">default</option>
                    {formats.map((f) => (
                      <option value={f.key || f.name || f.id}>{f.name}</option>
                    ))}
                  </select>

                  <div>
                    <label class="block text-xs font-medium text-gray-500 mb-1">Mode source document</label>
                    <select
                      class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all focus-glow"
                      value={sourceMode}
                      onChange={(e) => this.setState({ sourceMode: e.target.value })}
                    >
                      <option value="document">Document tabulaire classique</option>
                      <option value="presented_catalog">Catalogue présenté (IA)</option>
                    </select>
                  </div>

                  {sourceMode === "presented_catalog" && (
                    <div>
                      <label class="block text-xs font-medium text-gray-500 mb-1">Mode catalogue présenté</label>
                      <select
                        class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all focus-glow"
                        value={presentedMode}
                        onChange={(e) => this.setState({ presentedMode: e.target.value })}
                      >
                        <option value="docling_ocr">Docling OCR</option>
                        <option value="vision_model">Vision model</option>
                      </select>
                    </div>
                  )}

                  <div class="pt-2 border-t border-gray-100">
                    <p class="text-xs font-semibold text-gray-700 mb-2">Extraction website</p>

                    <label class="block text-xs font-medium text-gray-500 mb-1">URL de départ</label>
                    <input
                      type="url"
                      class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all focus-glow"
                      placeholder="https://example.com"
                      value={websiteStartUrl}
                      onInput={(e) => this.setState({ websiteStartUrl: e.target.value })}
                    />

                    <div class="grid grid-cols-1 md:grid-cols-3 gap-2 mt-2">
                      <div>
                        <label class="block text-xs font-medium text-gray-500 mb-1">Mode crawl</label>
                        <select
                          class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all focus-glow"
                          value={websiteCrawlMode}
                          onChange={(e) => this.setState({ websiteCrawlMode: e.target.value })}
                        >
                          <option value="manual">Manuel</option>
                          <option value="semi_auto">Semi-auto</option>
                          <option value="auto">Auto</option>
                        </select>
                      </div>
                      <div>
                        <label class="block text-xs font-medium text-gray-500 mb-1">Max pages</label>
                        <input
                          type="number"
                          min="1"
                          class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all focus-glow"
                          value={websiteMaxPages}
                          onInput={(e) => this.setState({ websiteMaxPages: e.target.value })}
                        />
                      </div>
                      <div>
                        <label class="block text-xs font-medium text-gray-500 mb-1">Profondeur max</label>
                        <input
                          type="number"
                          min="0"
                          class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all focus-glow"
                          value={websiteMaxDepth}
                          onInput={(e) => this.setState({ websiteMaxDepth: e.target.value })}
                        />
                      </div>
                    </div>

                    <label class="block text-xs font-medium text-gray-500 mt-2 mb-1">URLs manuelles (1 par ligne)</label>
                    <textarea
                      rows={4}
                      class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all focus-glow"
                      placeholder="https://example.com/product-1"
                      value={websiteUrlsText}
                      onInput={(e) => this.setState({ websiteUrlsText: e.target.value })}
                    />

                    <label class="block text-xs font-medium text-gray-500 mt-2 mb-1">Limite produits (optionnel)</label>
                    <input
                      type="number"
                      min="1"
                      class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all focus-glow"
                      placeholder="Ex: 100"
                      value={websiteMaxProductsInput}
                      onInput={(e) => this.setState({ websiteMaxProductsInput: e.target.value })}
                    />

                    <button
                      class="mt-3 inline-flex items-center gap-1.5 gradient-primary text-white rounded-lg px-4 py-2 text-xs font-medium transition-all hover:shadow-lg hover:shadow-indigo-500/25 disabled:opacity-50"
                      disabled={websiteExtracting || !!extractingDocId || !!analyzingDocId}
                      onClick={() => this.handleWebsiteExtract()}
                    >
                      {websiteExtracting ? <><IconSpinner size={13} /> Extraction website...</> : <><IconZap size={13} /> Lancer extraction website</>}
                    </button>
                  </div>
                </div>
              </Card>
            )}
            {/* Upload zone */}
            <Card>
              <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-3">
                  <h2 class="text-base font-semibold">Documents</h2>
                  <Badge variant="indigo">{documents.length} fichier{documents.length !== 1 ? "s" : ""}</Badge>
                </div>
              </div>

              <DropZone
                onFiles={(files) => this.handleUpload(files)}
                uploading={uploading}
                accept=".xlsx,.xls,.pdf,.doc,.docx,.csv,.txt,.md,.markdown"
                label="Glissez vos catalogues ici ou cliquez pour importer"
              />
            </Card>

            {/* Extraction progress panel */}
            {extractionProgress && (
              <div class="bg-indigo-50 border border-indigo-200 rounded-xl p-4 animate-slide-up">
                <div class="flex items-center justify-between mb-2">
                  <div class="flex items-center gap-2">
                    <IconSpinner size={16} class="text-indigo-500" />
                    <span class="text-sm font-medium text-indigo-800">
                      {extractionProgress.status === "preparing" ? "Préparation..." :
                       extractionProgress.status === "extracting" ? "Extraction en cours" :
                       extractionProgress.status === "done" ? "Terminé" : "En cours..."}
                    </span>
                  </div>
                  {extractionProgress.count > 0 && (
                    <span class="text-xs font-semibold text-indigo-600 bg-indigo-100 px-2 py-0.5 rounded-full">
                      {extractionProgress.count} produit{extractionProgress.count > 1 ? "s" : ""}
                    </span>
                  )}
                </div>
                <p class="text-xs text-indigo-700 mb-2">{extractionProgress.message}</p>
                {extractionProgress.total > 0 && (
                  <div class="w-full bg-indigo-200 rounded-full h-2">
                    <div
                      class="bg-indigo-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${Math.min(100, Math.round((extractionProgress.progress / extractionProgress.total) * 100))}%` }}
                    />
                  </div>
                )}
              </div>
            )}

            {/* Analysis panel */}
            {this.renderAnalysis()}

            {/* Document list */}
            {documents.length === 0 ? (
              <EmptyState
                icon={<IconFileText size={28} />}
                title="Aucun document"
                description="Importez un catalogue Excel, PDF ou CSV pour commencer l'extraction de produits."
                className="py-10"
              />
            ) : (
              <div class="space-y-3 stagger-children">
                {documents.map((d) => {
                  const fn = (d.filename || "").toLowerCase();
                  const isExcel = fn.endsWith(".xlsx") || fn.endsWith(".xls");
                  const isAnalyzing = analyzingDocId === d.id;
                  const hasAnalysis = analysisDocId === d.id;
                  const ext = (d.filename || "").split(".").pop().toUpperCase();
                  const StatusIcon = d.status === "processed"
                    ? IconCheckCircle
                    : d.status === "failed"
                      ? IconAlertCircle
                      : d.status === "processing"
                        ? IconSpinner
                        : IconClock;
                  const statusColor = d.status === "processed"
                    ? "text-green-500"
                    : d.status === "failed"
                      ? "text-red-500"
                      : d.status === "processing"
                        ? "text-indigo-500"
                        : "text-amber-500";
                  const statusLabel = d.status === "processed"
                    ? "Traité"
                    : d.status === "failed"
                      ? "Échoué"
                      : d.status === "processing"
                        ? "Traitement"
                        : d.status === "uploaded"
                          ? "Uploadé"
                          : "En attente";

                  return (
                    <Card hover={true} animate={false} className="!p-0 overflow-hidden">
                      <div class="flex items-stretch">
                        {/* File type indicator */}
                        <div class="w-16 bg-indigo-50/50 flex flex-col items-center justify-center shrink-0 border-r border-gray-100">
                          <IconFileText size={22} class="text-indigo-400 mb-1" />
                          <span class="text-[10px] font-bold text-indigo-500 uppercase">{ext}</span>
                        </div>

                        {/* File info */}
                        <div class="flex-1 p-4">
                          <div class="flex items-start justify-between gap-3 mb-2">
                            <div class="min-w-0">
                              <p class="font-semibold text-gray-900 truncate text-sm">{d.filename}</p>
                              <div class="flex items-center gap-3 mt-1">
                                <span class="flex items-center gap-1 text-xs text-gray-400">
                                  <IconClock size={11} />
                                  {d.created_at ? new Date(d.created_at).toLocaleDateString("fr-FR") : ""}
                                </span>
                                <span class={`flex items-center gap-1 text-xs font-medium ${statusColor}`}>
                                  <StatusIcon size={12} />
                                  {statusLabel}
                                </span>
                                {d.file_type && (
                                  <Badge variant="default" className="!text-[10px] !px-1.5 !py-0">{d.file_type}</Badge>
                                )}
                              </div>
                            </div>
                          </div>

                          {/* Actions row */}
                          <div class="flex items-center gap-2 mt-3 pt-3 border-t border-gray-100">
                            {isExcel && !hasAnalysis ? (
                              <>
                                <button
                                  class="inline-flex items-center gap-1.5 gradient-primary text-white rounded-lg px-4 py-2 text-xs font-medium transition-all hover:shadow-lg hover:shadow-indigo-500/25 disabled:opacity-50"
                                  disabled={!!extractingDocId || !!analyzingDocId}
                                  onClick={() => this.handleAnalyze(d.id)}
                                >
                                  {isAnalyzing ? (
                                    <><IconSpinner size={13} /> Analyse...</>
                                  ) : <><IconSearch size={13} /> Analyser les feuilles</>}
                                </button>
                                <button
                                  class="inline-flex items-center gap-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg px-4 py-2 text-xs font-medium transition-colors disabled:opacity-50"
                                  disabled={!!extractingDocId || !!analyzingDocId}
                                  onClick={() => this.handleExtract(d.id, null, { source_mode: "document" })}
                                  title="Extraction directe sans analyse"
                                >
                                  <IconZap size={13} /> Extraction directe
                                </button>
                              </>
                            ) : (
                              <button
                                class="inline-flex items-center gap-1.5 gradient-primary text-white rounded-lg px-4 py-2 text-xs font-medium transition-all hover:shadow-lg hover:shadow-indigo-500/25 disabled:opacity-50"
                                disabled={!!extractingDocId || !!analyzingDocId}
                                onClick={() => this.handleExtract(d.id, null)}
                              >
                                {extractingDocId === d.id ? <><IconSpinner size={13} /> Extraction...</> : <><IconZap size={13} /> Extraire les produits</>}
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
}
