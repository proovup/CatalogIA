import { Component } from "inferno";
import { Link } from "inferno-router";
import { api } from "../api";
import DropZone from "../components/DropZone";
import Toast from "../components/Toast";
import PageHeader from "../components/PageHeader";
import { IconSpinner, IconCheckCircle, IconArrowRight, IconZap, IconSearch } from "../components/Icons";

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

export default class UploadPage extends Component {
  constructor(props) {
    super(props);
    this.state = {
      documents: [],
      suppliers: [],
      formats: [],
      selectedDoc: null,
      selectedSupplier: "",
      selectedFormat: "default",
      uploading: false,
      // Analysis
      analyzing: false,
      analysis: null,
      analysisFilename: null,
      // Extraction
      extracting: false,
      extractResult: null,
      extractionProgress: null,
      error: null,
      toast: null,
    };
  }

  componentDidMount() {
    this.loadDocuments();
    this.loadFormats();
    this.loadSuppliers();
  }

  async loadDocuments() {
    try {
      const docs = await api.listDocuments();
      this.setState({ documents: docs });
    } catch (e) {
      this.setState({ error: e.message });
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
        this.setState({ formats: legacy || [] });
      } catch {}
    }
  }

  async loadSuppliers() {
    try {
      const res = await api.listSuppliers();
      this.setState({ suppliers: res.suppliers || [] });
    } catch {}
  }

  async handleUpload(files) {
    const { selectedSupplier } = this.state;
    this.setState({ uploading: true, error: null });
    try {
      for (const file of files) {
        await api.uploadDocument(file, selectedSupplier || undefined);
      }
      this.setState({ toast: `${files.length} fichier${files.length > 1 ? "s" : ""} uploadé${files.length > 1 ? "s" : ""}` });
      setTimeout(() => this.setState({ toast: null }), 4000);
      await this.loadDocuments();
    } catch (e) {
      this.setState({ error: e.message });
    } finally {
      this.setState({ uploading: false });
    }
  }

  async handleAnalyze() {
    const { selectedDoc } = this.state;
    if (!selectedDoc) return;
    this.setState({ analyzing: true, error: null, analysis: null, extractResult: null });
    try {
      const res = await api.analyzeDocument(selectedDoc);
      if (res.skip_analysis) {
        // Non-Excel file: skip analysis, go directly to extraction
        this.handleExtract(null);
        return;
      }
      const doc = this.state.documents.find((d) => d.id === selectedDoc);
      this.setState({ analysis: res.analysis, analysisFilename: res.filename || (doc && doc.filename) || "", analyzing: false });
    } catch (e) {
      this.setState({ error: e.message, analyzing: false });
    }
  }

  updateSheetAnalysis(index, field, value) {
    const { analysis } = this.state;
    if (!analysis) return;
    const sheets = [...analysis.sheets];
    sheets[index] = { ...sheets[index], [field]: value };

    // If changing a sheet to master, update master_sheet and reset previous master
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

  async handleExtract(analysisOverride) {
    const { selectedDoc, selectedFormat, analysis } = this.state;
    if (!selectedDoc) return;
    const finalAnalysis = analysisOverride !== undefined ? analysisOverride : analysis;
    this.setState({ extracting: true, error: null, extractResult: null, extractionProgress: null });
    try {
      const { job_id } = await api.extractProducts(selectedDoc, selectedFormat, finalAnalysis);
      api.streamExtractionProgress(
        job_id,
        (data) => this.setState({ extractionProgress: data }),
        (data) => {
          this.setState({ extractResult: { count: data.count }, extracting: false, extractionProgress: null });
        },
        (err) => {
          this.setState({ error: err, extracting: false, extractionProgress: null });
        },
      );
    } catch (e) {
      this.setState({ error: e.message, extracting: false, extractionProgress: null });
    }
  }

  renderAnalysis() {
    const { analysis, analysisFilename, extracting } = this.state;
    if (!analysis) return null;

    const masterSheet = analysis.master_sheet;
    const sheets = analysis.sheets || [];

    return (
      <div class="mt-6 bg-white rounded-xl border border-gray-200 p-6">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h3 class="text-lg font-semibold">Analyse des feuilles</h3>
            <p class="text-sm text-gray-500 mt-0.5">
              Fichier : <strong>{analysisFilename}</strong> — {sheets.length} feuille{sheets.length > 1 ? "s" : ""} détectée{sheets.length > 1 ? "s" : ""}
            </p>
          </div>
          <div class="flex gap-2">
            <button
              class="bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg px-4 py-2 text-sm transition-colors"
              onClick={() => this.setState({ analysis: null })}
            >
              Annuler
            </button>
            <button
              class="bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg px-5 py-2 text-sm transition-colors disabled:opacity-50"
              disabled={extracting}
              onClick={() => this.handleExtract()}
            >
              Confirmer et extraire
            </button>
          </div>
        </div>

        {/* Master sheet info */}
        <div class="bg-indigo-50 border border-indigo-200 rounded-lg p-3 mb-4">
          <p class="text-sm text-indigo-800">
            <strong>Feuille principale :</strong> {masterSheet}
            {analysis.join_columns && analysis.join_columns.length > 0 && (
              <span> — <strong>Colonnes de liaison :</strong> {analysis.join_columns.join(", ")}</span>
            )}
          </p>
        </div>

        {/* Sheet cards */}
        <div class="space-y-3">
          {sheets.map((sheet, idx) => (
            <div
              key={sheet.name}
              class={`border rounded-lg p-4 ${sheet.role === "master" ? "border-indigo-300 bg-indigo-50/50" : sheet.role === "metadata" ? "border-gray-200 bg-gray-50 opacity-60" : "border-gray-200"}`}
            >
              <div class="flex items-start justify-between mb-2">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-sm">{sheet.name}</span>
                  <span class={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${ROLE_COLORS[sheet.role] || "bg-gray-100 text-gray-600"}`}>
                    {ROLE_LABELS[sheet.role] || sheet.role}
                  </span>
                  <span class="text-xs text-gray-500">
                    {sheet.total_rows || 0} lignes
                  </span>
                  {sheet.relation && sheet.relation !== "master" && (
                    <span class={`inline-block px-2 py-0.5 rounded text-xs font-medium ${sheet.relation === "1:N" ? "bg-amber-100 text-amber-800" : "bg-green-100 text-green-800"}`}>
                      {RELATION_LABELS[sheet.relation] || sheet.relation}
                    </span>
                  )}
                </div>
              </div>

              {sheet.description && (
                <p class="text-xs text-gray-500 mb-2">{sheet.description}</p>
              )}

              {/* Edit controls */}
              <div class="flex flex-wrap gap-3 mt-2">
                <div>
                  <label class="block text-xs text-gray-500 mb-0.5">Rôle</label>
                  <select
                    class="border border-gray-300 rounded px-2 py-1 text-xs"
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
                    <label class="block text-xs text-gray-500 mb-0.5">Relation</label>
                    <select
                      class="border border-gray-300 rounded px-2 py-1 text-xs"
                      value={sheet.relation}
                      onChange={(e) => this.updateSheetAnalysis(idx, "relation", e.target.value)}
                    >
                      <option value="1:1">1:1 (une ligne par produit)</option>
                      <option value="1:N">1:N (plusieurs lignes par produit)</option>
                    </select>
                  </div>
                )}
                {sheet.role !== "metadata" && sheet.columns && sheet.columns.length > 0 && (
                  <div>
                    <label class="block text-xs text-gray-500 mb-0.5">Colonne de liaison</label>
                    <select
                      class="border border-gray-300 rounded px-2 py-1 text-xs"
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
              </div>

              {/* Column preview */}
              {sheet.columns && sheet.columns.length > 0 && (
                <div class="mt-2">
                  <p class="text-xs text-gray-400 mb-1">Colonnes :</p>
                  <div class="flex flex-wrap gap-1">
                    {sheet.columns.filter(Boolean).slice(0, 20).map((col) => (
                      <span class="bg-gray-100 text-gray-600 text-xs px-1.5 py-0.5 rounded">{col}</span>
                    ))}
                    {sheet.columns.filter(Boolean).length > 20 && (
                      <span class="text-xs text-gray-400">+{sheet.columns.filter(Boolean).length - 20} colonnes</span>
                    )}
                  </div>
                </div>
              )}

              {/* Sample rows */}
              {sheet.sample_rows && sheet.sample_rows.length > 0 && (
                <details class="mt-2">
                  <summary class="text-xs text-gray-400 cursor-pointer hover:text-gray-600">
                    Aperçu des données ({sheet.sample_rows.length} ligne{sheet.sample_rows.length > 1 ? "s" : ""})
                  </summary>
                  <div class="mt-1 overflow-x-auto">
                    <table class="text-xs border-collapse">
                      <thead>
                        <tr>
                          {(sheet.columns || []).filter(Boolean).slice(0, 10).map((col) => (
                            <th class="border border-gray-200 px-2 py-1 bg-gray-50 text-left font-medium text-gray-600 whitespace-nowrap">{col}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {sheet.sample_rows.slice(0, 3).map((row) => (
                          <tr>
                            {row.slice(0, 10).map((cell) => (
                              <td class="border border-gray-200 px-2 py-1 text-gray-500 whitespace-nowrap max-w-[150px] truncate">
                                {cell != null ? String(cell) : "—"}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }

  render() {
    const {
      documents, suppliers, formats, selectedDoc, selectedSupplier, selectedFormat,
      uploading, analyzing, analysis, extracting, extractResult, extractionProgress, error, toast,
    } = this.state;

    const isExcel = (() => {
      if (!selectedDoc) return false;
      const doc = documents.find((d) => d.id === selectedDoc);
      if (!doc) return false;
      const fn = (doc.filename || "").toLowerCase();
      return fn.endsWith(".xlsx") || fn.endsWith(".xls");
    })();

    return (
      <div class="max-w-4xl mx-auto px-4 py-8">
        <Toast message={toast} type="success" onClose={() => this.setState({ toast: null })} />

        <PageHeader
          title="Import & Extraction"
          subtitle={<span>Pour un upload contextualisé, passez par <Link to="/suppliers" class="text-indigo-600 hover:underline">un fournisseur</Link>.</span>}
        />

        {/* Upload zone */}
        <section class="mb-6">
          {suppliers.length > 0 && (
            <div class="mb-3">
              <label class="block text-sm font-medium text-gray-700 mb-1">Fournisseur (optionnel)</label>
              <select
                class="w-64 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                value={selectedSupplier}
                onChange={(e) => this.setState({ selectedSupplier: e.target.value })}
              >
                <option value="">-- Aucun --</option>
                {suppliers.map((s) => (
                  <option value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
          )}
          <DropZone
            onFiles={(files) => this.handleUpload(files)}
            uploading={uploading}
            accept=".xlsx,.xls,.pdf,.docx,.csv,.txt"
          />
        </section>

        {error && (
          <div class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-6 text-sm flex items-center justify-between">
            {error}
            <button class="text-red-400 hover:text-red-600" onClick={() => this.setState({ error: null })}>✕</button>
          </div>
        )}

        {/* Extraction */}
        <section class="bg-white rounded-xl border border-gray-200 p-6">
          <h2 class="text-lg font-semibold mb-4">Extraction automatique</h2>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Document</label>
              <select
                class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                value={selectedDoc || ""}
                onChange={(e) => this.setState({ selectedDoc: e.target.value || null, analysis: null, extractResult: null })}
              >
                <option value="">-- Sélectionner --</option>
                {documents.map((d) => (
                  <option value={d.id}>{d.filename}</option>
                ))}
              </select>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Format YAML</label>
              <select
                class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                value={selectedFormat}
                onChange={(e) => this.setState({ selectedFormat: e.target.value })}
              >
                <option value="default">default</option>
                {formats.map((f) => (
                  <option value={f.key || f.name || f.id}>{f.name}</option>
                ))}
              </select>
            </div>
          </div>

          <p class="text-sm text-gray-500 mb-4">
            {isExcel ? (
              <span>
                Ce fichier Excel sera d'abord <strong>analysé</strong> pour détecter les liens entre feuilles.
                Vous pourrez vérifier et ajuster avant l'extraction.
              </span>
            ) : (
              <span>
                L'extraction récupère automatiquement <strong>nom</strong>, <strong>description</strong> et <strong>prix</strong> depuis le fichier.
              </span>
            )}
          </p>

          <div class="flex gap-2">
            {isExcel && !analysis ? (
              <button
                class="bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg px-5 py-2.5 text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={!selectedDoc || analyzing || extracting}
                onClick={() => this.handleAnalyze()}
              >
                {analyzing ? (
                  <span class="flex items-center gap-2">
                    <IconSpinner size={16} />
                    Analyse en cours...
                  </span>
                ) : (
                  <span class="flex items-center gap-2"><IconSearch size={16} /> Analyser les feuilles</span>
                )}
              </button>
            ) : !analysis ? (
              <button
                class="bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg px-5 py-2.5 text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={!selectedDoc || extracting}
                onClick={() => this.handleExtract(null)}
              >
                {extracting ? (
                  <span class="flex items-center gap-2">
                    <IconSpinner size={16} />
                    Extraction en cours...
                  </span>
                ) : (
                  <span class="flex items-center gap-2"><IconZap size={16} /> Extraire les produits</span>
                )}
              </button>
            ) : null}

            {isExcel && !analysis && (
              <button
                class="bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg px-4 py-2.5 text-sm transition-colors disabled:opacity-50"
                disabled={!selectedDoc || extracting || analyzing}
                onClick={() => this.handleExtract(null)}
                title="Extraire sans analyser les relations entre feuilles"
              >
                Extraction directe
              </button>
            )}
          </div>

          {/* Analysis results */}
          {this.renderAnalysis()}

          {extractionProgress && (
            <div class="mt-4 bg-indigo-50 border border-indigo-200 rounded-lg p-4">
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

          {extractResult && (
            <div class="mt-6 bg-green-50 border border-green-200 rounded-xl p-4 animate-scale-in">
              <div class="flex items-center gap-2">
                <IconCheckCircle size={18} class="text-green-500" />
                <p class="text-green-800 font-medium">
                  {extractResult.count} produit{extractResult.count > 1 ? "s" : ""} extrait{extractResult.count > 1 ? "s" : ""}
                </p>
              </div>
              <Link to="/products" class="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 text-sm mt-2 font-medium transition-colors">
                Voir les produits <IconArrowRight size={14} />
              </Link>
            </div>
          )}
        </section>
      </div>
    );
  }
}
