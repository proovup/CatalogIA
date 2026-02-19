import { Component } from "inferno";
import { Link } from "inferno-router";
import { api } from "../api";
import Badge from "../components/Badge";
import DynamicField from "../components/DynamicField";
import Toast from "../components/Toast";
import PageHeader from "../components/PageHeader";
import { IconSpinner, IconSave, IconTrash, IconSparkles, IconBrain, IconWand, IconChevronDown, IconSettings, IconEdit, IconLayers, IconZap, IconFileText, IconGlobe, IconGrid, IconImage, IconSearch, IconDownload, IconX, IconMaximize, IconExternalLink, IconDatabase } from "../components/Icons";

const STATUS_BADGE = {
  draft: "warning",
  validated: "success",
  rejected: "danger",
};
const STATUS_LABEL = {
  draft: "Brouillon",
  validated: "Valid\u00e9",
  rejected: "Rejet\u00e9",
};

const TABS = [
  { id: "info", label: "Informations", icon: IconEdit },
  { id: "yaml", label: "Fiche Custom", icon: IconLayers },
  { id: "scraping", label: "Scraping", icon: IconGlobe },
  { id: "gallery", label: "Galerie", icon: IconImage },
  { id: "enrichment", label: "Enrichissement", icon: IconDatabase },
  { id: "data", label: "Données brutes", icon: IconFileText },
];

export default class ProductDetail extends Component {
  constructor(props) {
    super(props);
    this.state = {
      product: null,
      formats: [],
      selectedFormatId: null,
      formatDetail: null,
      formatFields: [],
      provider: localStorage.getItem("default_provider") || DEFAULT_PROVIDER,
      model: localStorage.getItem("default_model") || DEFAULT_MODEL,
      loading: true,
      saving: false,
      classifying: false,
      regenerating: false,
      error: null,
      toast: null,
      toastType: "success",
      activeTab: "info",
      showRaw: false,
      showProcessed: false,
      // Core editable fields
      name: "",
      description: "",
      price: "",
      category: "",
      reference: "",
      brand: "",
      status: "draft",
      // Dynamic fields values
      dynamicValues: {},
      // Per-field mode & AI hints
      fieldModes: {},
      fieldAiHints: {},
      generatingField: null,
      // Scraping
      scrapeQuery: "",
      scrapeUrls: "",
      scrapeSites: "",
      scraping: false,
      scrapeResults: [],
      scrapeLoading: false,
      // Gallery
      galleryImages: [],
      galleryLoading: false,
      gallerySelected: new Set(),
      galleryFilter: "",
      galleryPreview: null,
      downloading: false,
      // Enrichment
      enrichments: [],
      enrichmentsLoading: false,
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
      const product = await api.getProduct(id);
      this.setState({
        product,
        loading: false,
        name: product.name || "",
        description: product.description || "",
        price: product.price != null ? String(product.price) : "",
        category: product.category || "",
        reference: product.reference || "",
        brand: product.brand || "",
        status: product.status || "draft",
      });
    } catch (e) {
      this.setState({ error: e.message, loading: false });
    }
  }

  async loadFormats() {
    try {
      const res = await api.listFormats();
      const fmts = res.formats || [];
      this.setState({ formats: fmts });
    } catch {
      try {
        const legacy = await api.listFormatsLegacy();
        this.setState({ formats: (legacy || []).map((f) => ({ id: f.key, name: f.name, field_count: f.fields?.length || 0 })) });
      } catch { }
    }
  }

  showToast(message, type = "success") {
    this.setState({ toast: message, toastType: type });
    setTimeout(() => this.setState({ toast: null }), 4000);
  }

  async handleFormatChange(formatId) {
    this.setState({ selectedFormatId: formatId, formatDetail: null, formatFields: [] });
    if (!formatId) return;
    try {
      const detail = await api.getFormat(formatId);
      const fields = this._parseFields(detail.yaml_content);
      const dynamicValues = this._prefillValues(fields);
      this.setState({ formatDetail: detail, formatFields: fields, dynamicValues });
    } catch (e) {
      this.setState({ error: e.message });
    }
  }

  _parseFields(yamlContent) {
    const raw = yamlContent?.fields;
    if (!raw) return [];

    let topFields = [];
    if (Array.isArray(raw)) {
      topFields = raw.filter((f) => f && !f.exclude_from_extraction);
    } else if (typeof raw === "object") {
      topFields = Object.entries(raw).map(([key, val]) => ({ name: key, ...(typeof val === "object" ? val : { type: "string" }) }));
    }

    const result = [];

    const flatten = (fields, prefix = "", groupOverride = null, groupKeyOverride = null) => {
      for (const f of fields) {
        if (f.exclude_from_extraction) continue;

        const fname = f.name || "";
        const fullPath = prefix ? `${prefix}.${fname}` : fname;
        const ftype = f.type || "string";
        const label = f.label || f.description || fname || "";

        // Determine grouping
        let currentGroup = groupOverride;
        let currentGroupKey = groupKeyOverride;

        if (!currentGroup && prefix === "") {
          // Top level grouping logic
          if (ftype === "object" && Array.isArray(f.fields) && f.fields.length > 0) {
            currentGroup = label;
            currentGroupKey = fname;
          }
        }

        if (ftype === "object" && Array.isArray(f.fields) && f.fields.length > 0) {
          // Recurse
          flatten(f.fields, fullPath, currentGroup, currentGroupKey);
        } else {
          // Leaf field
          result.push({
            name: fullPath,
            type: ftype,
            label: label,
            required: !!f.required,
            options: f.options || null,
            ai_instruction: f.ai_instruction || null,
            fields: f.fields || null, // Keep subfields structure just in case, though handled above
            default: f.default != null ? f.default : null,
            unit: f.unit || null,
            group: currentGroup,
            groupKey: currentGroupKey,
          });
        }
      }
    };

    flatten(topFields);
    return result;
  }

  _prefillValues(fields) {
    const { product } = this.state;
    const processed = product?.processed_data || {};
    const rawData = product?.raw_data || {};
    const values = {};

    const _get = (obj, path) => {
      const parts = path.split(".");
      let cur = obj;
      for (const p of parts) {
        if (cur == null || typeof cur !== "object") return undefined;
        cur = cur[p];
      }
      return cur;
    };

    for (const f of fields) {
      const fromProcessed = _get(processed, f.name);
      const fromRaw = _get(rawData, f.name);
      const fromProduct = f.name.indexOf(".") === -1 ? product?.[f.name] : undefined;
      // Also check flattened key (parent_child) in processed_data
      const flatKey = f.name.replace(/\./g, "_");
      const fromProcessedFlat = processed[flatKey];

      if (fromProcessed != null) {
        values[f.name] = fromProcessed;
      } else if (fromProcessedFlat != null) {
        values[f.name] = fromProcessedFlat;
      } else if (fromRaw != null) {
        values[f.name] = fromRaw;
      } else if (fromProduct != null) {
        values[f.name] = fromProduct;
      } else if (f.default != null) {
        values[f.name] = f.default;
      } else {
        values[f.name] = null;
      }
    }
    return values;
  }

  handleDynamicChange(fieldName, value) {
    this.setState((prev) => ({
      dynamicValues: { ...prev.dynamicValues, [fieldName]: value },
    }));
  }

  handleFieldModeChange(fieldName, mode) {
    this.setState((prev) => ({
      fieldModes: { ...prev.fieldModes, [fieldName]: mode },
    }));
  }

  handleFieldAiHintChange(fieldName, hint) {
    this.setState((prev) => ({
      fieldAiHints: { ...prev.fieldAiHints, [fieldName]: hint },
    }));
  }

  async handleRegenerateField(field) {
    const { product, fieldAiHints, provider, model } = this.state;
    this.setState({ generatingField: field.name, error: null });
    try {
      const result = await api.regenerateField(product.id, {
        field_name: field.name,
        field_type: field.type || "string",
        field_label: field.label || field.name,
        ai_hint: fieldAiHints[field.name] || "",
        ai_instruction: field.ai_instruction || "",
        provider,
        model_name: model,
      });
      this.setState((prev) => ({
        dynamicValues: { ...prev.dynamicValues, [result.field_name]: result.value },
        generatingField: null,
      }));
      this.showToast(`Champ "${field.label || field.name}" généré`);
    } catch (e) {
      this.setState({ error: e.message, generatingField: null });
    }
  }

  _flattenRawData(obj, prefix = "") {
    const result = [];
    for (const [key, val] of Object.entries(obj || {})) {
      const fullKey = prefix ? `${prefix}.${key}` : key;
      if (val && typeof val === "object" && !Array.isArray(val)) {
        result.push(...this._flattenRawData(val, fullKey));
      } else {
        result.push({ key: fullKey, value: val });
      }
    }
    return result;
  }

  async handleSave() {
    const { product, name, description, price, category, reference, brand, status } = this.state;
    this.setState({ saving: true, error: null });
    try {
      const data = {
        name: name || null,
        description: description || null,
        price: price ? parseFloat(price) : null,
        category: category || null,
        reference: reference || null,
        brand: brand || null,
        status,
      };
      await api.updateProduct(product.id, data);
      this.showToast("Produit sauvegardé");
      this.setState({ saving: false });
    } catch (e) {
      this.setState({ error: e.message, saving: false });
    }
  }

  async handleClassify() {
    const { product, provider, model } = this.state;
    this.setState({ classifying: true, error: null });
    try {
      const result = await api.classifyProduct(product.id, provider, model);
      const updated = result.product;
      this.setState({
        classifying: false,
        category: updated.category || this.state.category,
        product: updated,
      });
      this.showToast(`Classifié : ${result.classification.category_path?.join(" > ") || "—"} (${(result.classification.confidence * 100).toFixed(0)}%)`);
    } catch (e) {
      this.setState({ error: e.message, classifying: false });
    }
  }

  async handleRegenerate() {
    const { product, selectedFormatId, formatDetail, provider, model } = this.state;
    const formatName = formatDetail?.yaml_content?.name || formatDetail?.name || "default";
    this.setState({ regenerating: true, error: null });
    try {
      const result = await api.regenerateProduct(product.id, formatName, provider, model);
      const updated = result.product;
      this.setState({
        regenerating: false,
        product: updated,
        name: updated.name || "",
        description: updated.description || "",
        price: updated.price != null ? String(updated.price) : "",
        category: updated.category || "",
        reference: updated.reference || "",
        brand: updated.brand || "",
      });
      // Re-prefill dynamic values from regenerated processed_data
      if (this.state.formatFields.length) {
        const dynamicValues = this._prefillValues(this.state.formatFields);
        this.setState({ dynamicValues });
      }
      this.showToast("Fiche regénérée avec l'IA");
    } catch (e) {
      this.setState({ error: e.message, regenerating: false });
    }
  }

  // ── Scraping ──

  async loadScrapeResults() {
    const { product } = this.state;
    this.setState({ scrapeLoading: true });
    try {
      const results = await api.getScrapeResults(product.id);
      this.setState({ scrapeResults: results, scrapeLoading: false });
    } catch (e) {
      this.setState({ scrapeLoading: false });
      this.showToast(e.message, "error");
    }
  }

  async handleScrape() {
    const { product, scrapeQuery, scrapeUrls, scrapeSites } = this.state;
    this.setState({ scraping: true, error: null });
    const data = {};
    const query = scrapeQuery.trim() || `${product.name || ""} ${product.reference || ""}`.trim();
    if (query) data.search_query = query;
    if (scrapeUrls.trim()) data.urls = scrapeUrls.split("\n").map((u) => u.trim()).filter(Boolean);
    if (scrapeSites.trim()) data.sites = scrapeSites.split(",").map((s) => s.trim()).filter(Boolean);
    try {
      const results = await api.scrapeProduct(product.id, data);
      this.showToast(`${results.length} résultat(s) trouvé(s)`);
      this.setState({ scraping: false });
      this.loadScrapeResults();
    } catch (e) {
      this.setState({ error: e.message, scraping: false });
    }
  }

  async handleDeleteScrapeResult(resultId) {
    const { product } = this.state;
    try {
      await api.deleteScrapeResult(product.id, resultId);
      this.loadScrapeResults();
      this.showToast("Résultat supprimé");
    } catch (e) {
      this.showToast(e.message, "error");
    }
  }

  // ── Gallery ──

  async loadGallery() {
    const { product } = this.state;
    this.setState({ galleryLoading: true });
    try {
      const images = await api.getProductGallery(product.id);
      this.setState({ galleryImages: images, galleryLoading: false, gallerySelected: new Set() });
    } catch (e) {
      this.setState({ galleryLoading: false });
      this.showToast(e.message, "error");
    }
  }

  toggleGallerySelect(url) {
    this.setState((prev) => {
      const next = new Set(prev.gallerySelected);
      if (next.has(url)) next.delete(url);
      else next.add(url);
      return { gallerySelected: next };
    });
  }

  selectAllGallery() {
    const { galleryImages, galleryFilter } = this.state;
    const filtered = galleryFilter
      ? galleryImages.filter((img) => img.source_site === galleryFilter)
      : galleryImages;
    this.setState({ gallerySelected: new Set(filtered.map((img) => img.url)) });
  }

  async handleDownloadGallery() {
    const { product, gallerySelected } = this.state;
    if (!gallerySelected.size) return;
    this.setState({ downloading: true });
    try {
      const blob = await api.downloadGalleryImages(product.id, [...gallerySelected]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `product_${product.id}_images.zip`;
      a.click();
      URL.revokeObjectURL(url);
      this.showToast("Téléchargement lancé");
    } catch (e) {
      this.showToast(e.message, "error");
    }
    this.setState({ downloading: false });
  }

  async handleDelete() {
    if (!confirm("Supprimer ce produit ?")) return;
    try {
      await api.deleteProduct(this.state.product.id);
      window.location.href = "/products";
    } catch (e) {
      this.setState({ error: e.message });
    }
  }

  // ── Enrichment ──

  async loadEnrichments() {
    const { product } = this.state;
    this.setState({ enrichmentsLoading: true });
    try {
      const enrichments = await api.getProductEnrichments(product.id);
      this.setState({ enrichments, enrichmentsLoading: false });
    } catch (e) {
      this.setState({ enrichmentsLoading: false });
      this.showToast(e.message, "error");
    }
  }

  async deleteEnrichment(id) {
    try {
      await api.deleteEnrichmentDocument(id);
      this.loadEnrichments();
      this.showToast("Document d'enrichissement supprimé");
    } catch (e) {
      this.showToast(e.message, "error");
    }
  }

  render() {
    const {
      product, formats, selectedFormatId, formatFields, dynamicValues,
      provider, loading, saving, classifying, regenerating,
      error, toast, toastType, showRaw, showProcessed,
      name, description, price, category, reference, brand, status,
      fieldModes, fieldAiHints, generatingField, model,
    } = this.state;

    const rawDataEntries = product ? this._flattenRawData(product.raw_data) : [];

    if (loading) {
      return (
        <div class="flex items-center justify-center py-32">
          <IconSpinner size={24} class="text-indigo-500" />
        </div>
      );
    }

    if (!product) {
      return (
        <div class="max-w-4xl mx-auto px-4 py-16 text-center text-gray-400">
          Produit introuvable.
          <Link to="/products" class="text-indigo-600 hover:underline ml-2">Retour</Link>
        </div>
      );
    }

    const { activeTab } = this.state;

    return (
      <div class="max-w-5xl mx-auto px-4 py-8">
        <Toast message={toast} type={toastType} onClose={() => this.setState({ toast: null })} />

        <PageHeader
          title={name || "Sans nom"}
          breadcrumb={[
            { label: "Produits", to: "/products" },
            { label: name || "Sans nom" },
          ]}
          actions={
            <div class="flex items-center gap-2">
              <Badge variant={STATUS_BADGE[status] || "default"}>
                {STATUS_LABEL[status] || status}
              </Badge>
              {product.supplier_name && (
                <Badge variant="indigo">{product.supplier_name}</Badge>
              )}
            </div>
          }
        />

        {/* Source info bar */}
        <div class="flex flex-wrap items-center gap-4 mb-5 text-xs text-gray-400 animate-fade-in">
          {product.document_filename && (
            <span class="flex items-center gap-1"><IconFileText size={12} /> {product.document_filename}</span>
          )}
          {product.created_at && (
            <span>Créé le {new Date(product.created_at).toLocaleDateString("fr-FR")}</span>
          )}
          {product.raw_data?.source_sheets && (
            <span>Feuilles : {product.raw_data.source_sheets.map((s) => s.sheet_name).join(", ")}</span>
          )}
        </div>

        {/* Error */}
        {error && (
          <div class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-4 text-sm flex items-center justify-between animate-fade-in">
            {error}
            <button class="text-red-400 hover:text-red-600" onClick={() => this.setState({ error: null })}>✕</button>
          </div>
        )}

        {/* Tabs */}
        <div class="border-b border-gray-200 mb-6">
          <nav class="flex gap-0 -mb-px">
            {TABS.map((tab) => {
              const active = activeTab === tab.id;
              const TabIcon = tab.icon;
              return (
                <button
                  class={`inline-flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-all ${active
                      ? "border-indigo-500 text-indigo-600"
                      : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                    }`}
                  onClick={() => {
                    this.setState({ activeTab: tab.id });
                    if (tab.id === "scraping") this.loadScrapeResults();
                    if (tab.id === "gallery") this.loadGallery();
                    if (tab.id === "enrichment") this.loadEnrichments();
                  }}
                >
                  <TabIcon size={16} class={active ? "text-indigo-500" : "text-gray-400"} />
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Tab panels */}
        <div class="animate-fade-in" key={activeTab}>

          {/* ── Tab: Informations ── */}
          {activeTab === "info" && (
            <div class="max-w-3xl space-y-6">
              <section class="bg-white rounded-xl border border-gray-200 p-6">
                <h2 class="text-base font-semibold mb-4">Informations produit</h2>
                <div class="space-y-4">
                  <FieldSimple label="Nom" value={name} onInput={(v) => this.setState({ name: v })} />
                  <FieldSimple label="Description" value={description} onInput={(v) => this.setState({ description: v })} textarea />
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <FieldSimple label="Prix" value={price} onInput={(v) => this.setState({ price: v })} type="number" />
                    <FieldSimple label="Catégorie" value={category} onInput={(v) => this.setState({ category: v })} />
                  </div>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <FieldSimple label="Référence / SKU" value={reference} onInput={(v) => this.setState({ reference: v })} />
                    <FieldSimple label="Marque" value={brand} onInput={(v) => this.setState({ brand: v })} />
                  </div>
                  <div class="max-w-xs">
                    <label class="block text-sm font-medium text-gray-700 mb-1.5">Statut</label>
                    <select
                      class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all focus-glow"
                      value={status}
                      onChange={(e) => this.setState({ status: e.target.value })}
                    >
                      <option value="draft">Brouillon</option>
                      <option value="validated">Validé</option>
                      <option value="rejected">Rejeté</option>
                    </select>
                  </div>
                </div>
              </section>

              {/* Action bar */}
              <div class="flex items-center gap-3">
                <button
                  class="inline-flex items-center gap-2 gradient-primary text-white font-medium rounded-lg px-6 py-2.5 text-sm transition-all hover:shadow-lg hover:shadow-indigo-500/25 disabled:opacity-50"
                  disabled={saving}
                  onClick={() => this.handleSave()}
                >
                  {saving ? <><IconSpinner size={14} /> Sauvegarde...</> : <><IconSave size={14} /> Sauvegarder</>}
                </button>
                <button
                  class="inline-flex items-center gap-2 bg-red-50 hover:bg-red-100 text-red-600 font-medium rounded-lg px-4 py-2.5 text-sm transition-colors"
                  onClick={() => this.handleDelete()}
                >
                  <IconTrash size={14} /> Supprimer
                </button>
              </div>
            </div>
          )}

          {/* ── Tab: Fiche Custom ── */}
          {activeTab === "yaml" && (
            <div class="max-w-3xl space-y-6">
              {/* Format selector */}
              <div class="bg-white rounded-xl border border-gray-200 p-5">
                <div class="flex items-center justify-between">
                  <div>
                    <h2 class="text-base font-semibold">Format Custom</h2>
                    <p class="text-xs text-gray-500 mt-0.5">Sélectionnez un format pour afficher les champs dynamiques</p>
                  </div>
                  <select
                    class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all focus-glow min-w-[200px]"
                    value={selectedFormatId || ""}
                    onChange={(e) => this.handleFormatChange(e.target.value || null)}
                  >
                    <option value="">-- Sélectionner --</option>
                    {formats.map((f) => (
                      <option value={f.id}>{f.name} ({f.field_count} champs)</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Dynamic fields */}
              {!selectedFormatId ? (
                <div class="flex flex-col items-center justify-center py-12 text-gray-400">
                  <IconLayers size={32} class="text-gray-300 mb-3" />
                  <p class="text-sm">Sélectionnez un format ci-dessus</p>
                </div>
              ) : formatFields.length === 0 ? (
                <div class="flex items-center justify-center py-12">
                  <IconSpinner size={24} class="text-indigo-500" />
                </div>
              ) : (
                <section class="bg-white rounded-xl border border-gray-200 p-6">
                  <h3 class="text-sm font-semibold text-gray-700 mb-4">
                    {formatFields.length} champ{formatFields.length > 1 ? "s" : ""}
                  </h3>
                  <div class="space-y-3">
                    {(() => {
                      let lastGroup = null;
                      const elements = [];
                      for (const field of formatFields) {
                        // Group header for object fields
                        if (field.group && field.groupKey !== lastGroup) {
                          lastGroup = field.groupKey;
                          elements.push(
                            <div class="flex items-center gap-2 pt-3 pb-1">
                              <div class="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                              <span class="text-xs font-semibold text-indigo-600 uppercase tracking-wide">{field.group}</span>
                              <div class="flex-1 h-px bg-indigo-100" />
                            </div>
                          );
                        } else if (!field.group && lastGroup) {
                          lastGroup = null;
                        }
                        elements.push(
                          <DynamicField
                            field={field}
                            value={dynamicValues[field.name]}
                            onChange={(n, v) => this.handleDynamicChange(n, v)}
                            mode={fieldModes[field.name]}
                            aiHint={fieldAiHints[field.name]}
                            onModeChange={(n, m) => this.handleFieldModeChange(n, m)}
                            onAiHintChange={(n, h) => this.handleFieldAiHintChange(n, h)}
                            rawDataEntries={rawDataEntries}
                            onGenerate={(f) => this.handleRegenerateField(f)}
                            generating={generatingField === field.name}
                          />
                        );
                      }
                      return elements;
                    })()}
                  </div>

                  <div class="flex items-center gap-3 mt-6 pt-4 border-t border-gray-100">
                    <button
                      class="inline-flex items-center gap-2 bg-violet-600 hover:bg-violet-700 text-white font-medium rounded-lg px-5 py-2.5 text-sm transition-all hover:shadow-lg hover:shadow-violet-500/25 disabled:opacity-50"
                      disabled={regenerating}
                      onClick={() => this.handleRegenerate()}
                    >
                      {regenerating ? (
                        <><IconSpinner size={14} /> Regénération...</>
                      ) : (
                        <><IconWand size={14} /> Regénérer avec l'IA</>
                      )}
                    </button>
                    <button
                      class="inline-flex items-center gap-2 gradient-primary text-white font-medium rounded-lg px-5 py-2.5 text-sm transition-all hover:shadow-lg hover:shadow-indigo-500/25 disabled:opacity-50"
                      disabled={saving}
                      onClick={() => this.handleSave()}
                    >
                      {saving ? <><IconSpinner size={14} /> Sauvegarde...</> : <><IconSave size={14} /> Sauvegarder</>}
                    </button>
                  </div>
                </section>
              )}
            </div>
          )}

          {/* ── Tab: Scraping ── */}
          {activeTab === "scraping" && (
            <div class="max-w-4xl space-y-6">
              {/* Scrape form */}
              <section class="bg-white rounded-xl border border-gray-200 p-6">
                <h2 class="text-base font-semibold mb-4">Rechercher des fiches produit</h2>
                <div class="space-y-4">
                  <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1.5">Recherche web</label>
                    <input
                      class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all focus-glow placeholder:text-gray-400"
                      placeholder={`${this.state.name || ""} ${this.state.reference || ""}`.trim() || "Nom du produit..."}
                      value={this.state.scrapeQuery}
                      onInput={(e) => this.setState({ scrapeQuery: e.target.value })}
                    />
                    <p class="text-xs text-gray-400 mt-1">Laissez vide pour utiliser le nom + référence du produit</p>
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1.5">URLs manuelles (une par ligne)</label>
                    <textarea
                      class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all focus-glow resize-y placeholder:text-gray-400"
                      rows={3}
                      placeholder="https://exemple.com/produit-123"
                      value={this.state.scrapeUrls}
                      onInput={(e) => this.setState({ scrapeUrls: e.target.value })}
                    />
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1.5">Filtrer par sites (séparés par virgule)</label>
                    <input
                      class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all focus-glow placeholder:text-gray-400"
                      placeholder="amazon.fr, leroymerlin.fr"
                      value={this.state.scrapeSites}
                      onInput={(e) => this.setState({ scrapeSites: e.target.value })}
                    />
                  </div>
                  <button
                    class="inline-flex items-center gap-2 gradient-primary text-white font-medium rounded-lg px-6 py-2.5 text-sm transition-all hover:shadow-lg hover:shadow-indigo-500/25 disabled:opacity-50"
                    disabled={this.state.scraping}
                    onClick={() => this.handleScrape()}
                  >
                    {this.state.scraping ? (
                      <><IconSpinner size={14} /> Scraping en cours...</>
                    ) : (
                      <><IconSearch size={14} /> Lancer le scraping</>
                    )}
                  </button>
                </div>
              </section>

              {/* Scrape results */}
              {this.state.scrapeLoading ? (
                <div class="flex items-center justify-center py-12">
                  <IconSpinner size={24} class="text-indigo-500" />
                </div>
              ) : this.state.scrapeResults.length === 0 ? (
                <div class="flex flex-col items-center justify-center py-12 text-gray-400">
                  <IconGlobe size={32} class="text-gray-300 mb-3" />
                  <p class="text-sm">Aucun résultat de scraping. Lancez une recherche ci-dessus.</p>
                </div>
              ) : (
                <div class="space-y-4">
                  <h3 class="text-sm font-semibold text-gray-700">
                    {this.state.scrapeResults.length} résultat{this.state.scrapeResults.length > 1 ? "s" : ""}
                  </h3>
                  {this.state.scrapeResults.map((r) => (
                    <section class="bg-white rounded-xl border border-gray-200 p-5" key={r.id}>
                      <div class="flex items-start justify-between gap-4">
                        <div class="flex-1 min-w-0">
                          <div class="flex items-center gap-2 mb-1">
                            <h4 class="text-sm font-semibold text-gray-800 truncate">{r.title || "Sans titre"}</h4>
                            {r.source_site && (
                              <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-indigo-50 text-indigo-600 font-medium">
                                {r.source_site}
                              </span>
                            )}
                          </div>
                          <a
                            href={r.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            class="text-xs text-indigo-500 hover:underline truncate block"
                          >
                            <IconExternalLink size={10} class="inline mr-1" />
                            {r.source_url}
                          </a>
                          {r.description && (
                            <p class="text-xs text-gray-500 mt-2 line-clamp-3">{r.description}</p>
                          )}
                        </div>
                        <button
                          class="text-gray-400 hover:text-red-500 transition-colors shrink-0"
                          onClick={() => this.handleDeleteScrapeResult(r.id)}
                          title="Supprimer"
                        >
                          <IconTrash size={14} />
                        </button>
                      </div>

                      {/* Images preview */}
                      {r.images && r.images.length > 0 && (
                        <div class="flex gap-2 mt-3 overflow-x-auto pb-1">
                          {r.images.slice(0, 6).map((imgUrl) => (
                            <img
                              src={api.proxyImageUrl(imgUrl)}
                              alt=""
                              class="w-16 h-16 rounded-lg object-cover border border-gray-100 shrink-0"
                              loading="lazy"
                              onError={(e) => { e.target.onerror = null; e.target.src = imgUrl; }}
                            />
                          ))}
                          {r.images.length > 6 && (
                            <div class="w-16 h-16 rounded-lg bg-gray-100 border border-gray-200 flex items-center justify-center text-xs text-gray-500 shrink-0">
                              +{r.images.length - 6}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Characteristics */}
                      {r.characteristics && Object.keys(r.characteristics).length > 0 && (
                        <div class="mt-3 border-t border-gray-100 pt-3">
                          <p class="text-xs font-medium text-gray-500 mb-1">Caractéristiques</p>
                          <div class="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                            {Object.entries(r.characteristics).slice(0, 8).map(([k, v]) => (
                              <div class="flex gap-1">
                                <span class="text-gray-400 truncate">{k}:</span>
                                <span class="text-gray-700 truncate font-medium">{v}</span>
                              </div>
                            ))}
                          </div>
                          {Object.keys(r.characteristics).length > 8 && (
                            <p class="text-xs text-gray-400 mt-1">
                              +{Object.keys(r.characteristics).length - 8} autres
                            </p>
                          )}
                        </div>
                      )}
                    </section>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Tab: Gallery ── */}
          {activeTab === "gallery" && (
            <div class="max-w-5xl space-y-4">
              {this.state.galleryLoading ? (
                <div class="flex items-center justify-center py-12">
                  <IconSpinner size={24} class="text-indigo-500" />
                </div>
              ) : this.state.galleryImages.length === 0 ? (
                <div class="flex flex-col items-center justify-center py-12 text-gray-400">
                  <IconImage size={32} class="text-gray-300 mb-3" />
                  <p class="text-sm">Aucune image. Lancez un scraping d'abord depuis l'onglet Scraping.</p>
                </div>
              ) : (
                <>
                  {/* Toolbar */}
                  <div class="flex flex-wrap items-center justify-between gap-3 bg-white rounded-xl border border-gray-200 p-4">
                    <div class="flex items-center gap-3">
                      <select
                        class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all focus-glow"
                        value={this.state.galleryFilter}
                        onChange={(e) => this.setState({ galleryFilter: e.target.value })}
                      >
                        <option value="">Toutes les sources</option>
                        {[...new Set(this.state.galleryImages.map((img) => img.source_site))].map((site) => (
                          <option value={site}>{site}</option>
                        ))}
                      </select>
                      <button
                        class="text-xs text-indigo-600 hover:underline"
                        onClick={() => this.selectAllGallery()}
                      >
                        Tout sélectionner
                      </button>
                      {this.state.gallerySelected.size > 0 && (
                        <button
                          class="text-xs text-gray-500 hover:underline"
                          onClick={() => this.setState({ gallerySelected: new Set() })}
                        >
                          Désélectionner ({this.state.gallerySelected.size})
                        </button>
                      )}
                    </div>
                    <button
                      class="inline-flex items-center gap-2 gradient-primary text-white font-medium rounded-lg px-5 py-2 text-sm transition-all hover:shadow-lg hover:shadow-indigo-500/25 disabled:opacity-50"
                      disabled={!this.state.gallerySelected.size || this.state.downloading}
                      onClick={() => this.handleDownloadGallery()}
                    >
                      {this.state.downloading ? (
                        <><IconSpinner size={14} /> Téléchargement...</>
                      ) : (
                        <><IconDownload size={14} /> Télécharger la sélection ({this.state.gallerySelected.size})</>
                      )}
                    </button>
                  </div>

                  {/* Image grid */}
                  <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
                    {(this.state.galleryFilter
                      ? this.state.galleryImages.filter((img) => img.source_site === this.state.galleryFilter)
                      : this.state.galleryImages
                    ).map((img) => {
                      const selected = this.state.gallerySelected.has(img.url);
                      return (
                        <div
                          class={`relative group rounded-xl border-2 overflow-hidden cursor-pointer transition-all ${selected ? "border-indigo-500 ring-2 ring-indigo-200" : "border-gray-200 hover:border-gray-300"
                            }`}
                          key={img.url}
                        >
                          <img
                            src={api.proxyImageUrl(img.url)}
                            alt=""
                            class="w-full h-36 object-cover"
                            loading="lazy"
                            onClick={() => this.toggleGallerySelect(img.url)}
                            onError={(e) => { e.target.onerror = null; e.target.src = img.url; }}
                          />
                          {/* Checkbox */}
                          <div
                            class={`absolute top-2 left-2 w-5 h-5 rounded border-2 flex items-center justify-center transition-all ${selected ? "bg-indigo-500 border-indigo-500" : "bg-white/80 border-gray-300"
                              }`}
                            onClick={() => this.toggleGallerySelect(img.url)}
                          >
                            {selected && (
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="20 6 9 17 4 12" />
                              </svg>
                            )}
                          </div>
                          {/* Expand button */}
                          <button
                            class="absolute top-2 right-2 w-6 h-6 rounded bg-black/40 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                            onClick={() => this.setState({ galleryPreview: img })}
                          >
                            <IconMaximize size={12} />
                          </button>
                          {/* Source badge */}
                          <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent px-2 py-1.5">
                            <span class="text-[10px] text-white font-medium truncate block">{img.source_site}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Preview modal */}
                  {this.state.galleryPreview && (
                    <div
                      class="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
                      onClick={() => this.setState({ galleryPreview: null })}
                    >
                      <div class="relative max-w-4xl max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
                        <img
                          src={api.proxyImageUrl(this.state.galleryPreview.url)}
                          alt=""
                          class="max-w-full max-h-[85vh] rounded-xl object-contain"
                          onError={(e) => { e.target.onerror = null; e.target.src = this.state.galleryPreview.url; }}
                        />
                        <button
                          class="absolute top-3 right-3 w-8 h-8 rounded-full bg-black/50 text-white flex items-center justify-center hover:bg-black/70 transition-colors"
                          onClick={() => this.setState({ galleryPreview: null })}
                        >
                          <IconX size={16} />
                        </button>
                        <div class="absolute bottom-3 left-3 bg-black/50 text-white text-xs rounded-lg px-3 py-1.5">
                          {this.state.galleryPreview.source_site}
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* ── Tab: Enrichissement ── */}
          {activeTab === "enrichment" && (
            <div class="max-w-4xl space-y-6">
              <div class="flex items-center justify-between">
                <div>
                  <h2 class="text-base font-semibold">Documents d'enrichissement</h2>
                  <p class="text-xs text-gray-500 mt-0.5">Documents complémentaires liés à ce produit</p>
                </div>
                <Link
                  to="/enrichment"
                  class="inline-flex items-center gap-2 gradient-primary text-white font-medium rounded-lg px-4 py-2 text-sm transition-all hover:shadow-lg hover:shadow-indigo-500/25 no-underline"
                >
                  + Enrichir
                </Link>
              </div>

              {this.state.enrichmentsLoading ? (
                <div class="flex items-center justify-center py-12">
                  <IconSpinner size={24} class="text-indigo-500" />
                </div>
              ) : this.state.enrichments.length === 0 ? (
                <div class="bg-gray-50 rounded-xl border border-gray-100 p-12 text-center">
                  <IconDatabase size={32} class="mx-auto text-gray-300 mb-3" />
                  <p class="text-sm text-gray-500">Aucun document d'enrichissement lié à ce produit</p>
                  <Link
                    to="/enrichment"
                    class="inline-flex items-center gap-1 text-sm text-indigo-600 mt-3 hover:underline no-underline"
                  >
                    Enrichir ce produit →
                  </Link>
                </div>
              ) : (
                <div class="space-y-4">
                  {this.state.enrichments.map((ed) => {
                    const methodLabels = {
                      direct: "Direct",
                      reference: "Par référence",
                      name_match: "Par nom",
                      broadcast: "Diffusion",
                    };
                    const typeLabels = {
                      notice: "Notice",
                      catalogue: "Catalogue",
                      fiche_technique: "Fiche technique",
                      other: "Autre",
                    };
                    return (
                      <section key={ed.id} class="bg-white rounded-xl border border-gray-200 p-5">
                        <div class="flex items-center justify-between mb-3">
                          <div class="flex items-center gap-3">
                            <div class="w-9 h-9 rounded-lg bg-indigo-50 flex items-center justify-center">
                              <IconFileText size={16} class="text-indigo-500" />
                            </div>
                            <div>
                              <p class="text-sm font-medium text-gray-900">{ed.document_filename || "Document"}</p>
                              <div class="flex items-center gap-2 mt-0.5">
                                <Badge variant="indigo" size="sm">
                                  {typeLabels[ed.enrichment_type] || ed.enrichment_type}
                                </Badge>
                                {ed.match_method && (
                                  <Badge variant="default" size="sm">
                                    {methodLabels[ed.match_method] || ed.match_method}
                                  </Badge>
                                )}
                                {ed.match_confidence != null && (
                                  <span class="text-xs text-gray-400">
                                    Confiance : {Math.round(ed.match_confidence * 100)}%
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                          <button
                            class="p-2 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition-all"
                            onClick={() => this.deleteEnrichment(ed.id)}
                            title="Supprimer"
                          >
                            <IconTrash size={14} />
                          </button>
                        </div>
                        {ed.extracted_data && Object.keys(ed.extracted_data).length > 0 && (
                          <div class="bg-gray-50 rounded-lg p-4 border border-gray-100">
                            <h4 class="text-xs font-semibold text-gray-600 mb-2 uppercase tracking-wide">Données extraites</h4>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
                              {Object.entries(ed.extracted_data)
                                .filter(([k]) => !['raw_content', 'source'].includes(k))
                                .slice(0, 20)
                                .map(([key, val]) => (
                                  <div key={key} class="flex gap-2 text-xs">
                                    <span class="font-medium text-gray-500 min-w-[100px]">{key}:</span>
                                    <span class="text-gray-700 truncate">
                                      {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                                    </span>
                                  </div>
                                ))}
                            </div>
                            {Object.keys(ed.extracted_data).length > 20 && (
                              <p class="text-xs text-gray-400 mt-2">
                                +{Object.keys(ed.extracted_data).length - 20} autres champs
                              </p>
                            )}
                          </div>
                        )}
                        {ed.created_at && (
                          <p class="text-xs text-gray-400 mt-3">
                            Enrichi le {new Date(ed.created_at).toLocaleDateString("fr-FR")}
                          </p>
                        )}
                      </section>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* ── Tab: Données brutes ── */}
          {activeTab === "data" && (
            <div class="max-w-4xl space-y-6">
              <section class="bg-white rounded-xl border border-gray-200 p-6">
                <h2 class="text-base font-semibold mb-4">Données brutes (raw_data)</h2>
                <pre class="bg-gray-50 rounded-lg p-4 text-xs overflow-auto max-h-[500px] text-gray-600 border border-gray-100">
                  {JSON.stringify(product.raw_data, null, 2)}
                </pre>
              </section>

              {product.processed_data && (
                <section class="bg-white rounded-xl border border-gray-200 p-6">
                  <h2 class="text-base font-semibold mb-4">Données traitées (processed_data)</h2>
                  <pre class="bg-gray-50 rounded-lg p-4 text-xs overflow-auto max-h-[500px] text-gray-600 border border-gray-100">
                    {JSON.stringify(product.processed_data, null, 2)}
                  </pre>
                </section>
              )}
            </div>
          )}

        </div>
      </div>
    );
  }
}

function FieldSimple({ label, value, onInput, textarea, type }) {
  const cls = "w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white transition-all duration-200 focus-glow placeholder:text-gray-400";
  return (
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
      {textarea ? (
        <textarea class={`${cls} resize-y`} rows={4} value={value} onInput={(e) => onInput(e.target.value)} />
      ) : (
        <input class={cls} type={type || "text"} value={value} onInput={(e) => onInput(e.target.value)} />
      )}
    </div>
  );
}
