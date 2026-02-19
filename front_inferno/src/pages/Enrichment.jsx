import { Component } from "inferno";
import { Link } from "inferno-router";
import { api } from "../api";
import { DEFAULT_PROVIDER, DEFAULT_MODEL } from "../constants";
import DropZone from "../components/DropZone";
import Toast from "../components/Toast";
import PageHeader from "../components/PageHeader";
import Badge from "../components/Badge";
import Card from "../components/Card";
import { IconUpload, IconSearch, IconCheckCircle, IconTrash, IconSpinner, IconArrowRight, IconFile } from "../components/Icons";

const ENRICHMENT_TYPES = [
    { value: "notice", label: "Notice", desc: "Mode d'emploi, guide d'utilisation", color: "bg-blue-100 text-blue-700 border-blue-200" },
    { value: "catalogue", label: "Catalogue", desc: "Brochure commerciale, plaquette", color: "bg-violet-100 text-violet-700 border-violet-200" },
    { value: "fiche_technique", label: "Fiche technique", desc: "Spécifications, dimensions, certifications", color: "bg-amber-100 text-amber-700 border-amber-200" },
    { value: "other", label: "Autre", desc: "Document complémentaire divers", color: "bg-gray-100 text-gray-700 border-gray-200" },
];

const STATUS_BADGES = {
    pending: { variant: "default", label: "En attente" },
    processing: { variant: "info", label: "En cours" },
    completed: { variant: "success", label: "Terminé" },
    failed: { variant: "danger", label: "Erreur" },
};

const METHOD_LABELS = {
    direct: "Direct",
    reference: "Par référence",
    name_match: "Par nom",
    broadcast: "Diffusion",
};

export default class Enrichment extends Component {
    constructor(props) {
        super(props);
        this.state = {
            // Step management
            step: "upload", // upload | select_products | processing | done

            // Upload
            uploadedDoc: null,
            uploading: false,
            enrichmentType: "notice",

            // Product selection
            products: [],
            selectedProducts: new Set(),
            productSearch: "",
            loadingProducts: false,

            // Processing
            jobId: null,
            progress: null,
            processing: false,

            // History
            enrichmentHistory: [],
            loadingHistory: false,

            // UI
            toast: null,
            error: null,
        };
    }

    componentDidMount() {
        this.loadProducts();
        this.loadHistory();
    }

    async loadProducts() {
        this.setState({ loadingProducts: true });
        try {
            const products = await api.listProducts({ limit: 200 });
            this.setState({ products, loadingProducts: false });
        } catch (e) {
            this.setState({ loadingProducts: false, error: e.message });
        }
    }

    async loadHistory() {
        this.setState({ loadingHistory: true });
        try {
            const enrichmentHistory = await api.listEnrichmentDocuments();
            this.setState({ enrichmentHistory, loadingHistory: false });
        } catch {
            this.setState({ loadingHistory: false });
        }
    }

    showToast(message, type = "success") {
        this.setState({ toast: { message, type } });
        setTimeout(() => this.setState({ toast: null }), 4000);
    }

    async handleUpload(files) {
        if (!files.length) return;
        const file = files[0];
        this.setState({ uploading: true, error: null });
        try {
            const doc = await api.uploadEnrichmentDocument(file, this.state.enrichmentType);
            this.setState({ uploadedDoc: doc, uploading: false, step: "select_products" });
            this.showToast(`Document "${doc.filename}" uploadé avec succès`);
        } catch (e) {
            this.setState({ uploading: false, error: e.message });
            this.showToast("Erreur lors de l'upload : " + e.message, "error");
        }
    }

    toggleProduct(id) {
        const selected = new Set(this.state.selectedProducts);
        if (selected.has(id)) selected.delete(id);
        else selected.add(id);
        this.setState({ selectedProducts: selected });
    }

    selectAll() {
        const filtered = this.getFilteredProducts();
        const selected = new Set(this.state.selectedProducts);
        const allSelected = filtered.every((p) => selected.has(p.id));
        if (allSelected) {
            filtered.forEach((p) => selected.delete(p.id));
        } else {
            filtered.forEach((p) => selected.add(p.id));
        }
        this.setState({ selectedProducts: selected });
    }

    getFilteredProducts() {
        const search = this.state.productSearch.toLowerCase();
        if (!search) return this.state.products;
        return this.state.products.filter(
            (p) =>
                (p.name || "").toLowerCase().includes(search) ||
                (p.reference || "").toLowerCase().includes(search) ||
                (p.brand || "").toLowerCase().includes(search)
        );
    }

    async handleEnrich() {
        const { uploadedDoc, selectedProducts, enrichmentType } = this.state;
        if (!uploadedDoc || selectedProducts.size === 0) return;

        this.setState({ processing: true, step: "processing", error: null });

        try {
            const provider = localStorage.getItem("default_provider") || DEFAULT_PROVIDER;
            const model = localStorage.getItem("default_model") || DEFAULT_MODEL;

            const res = await api.processEnrichment(
                uploadedDoc.id,
                Array.from(selectedProducts),
                enrichmentType,
                { provider, model_name: model }
            );

            this.setState({ jobId: res.job_id });

            // Start SSE progress stream
            api.streamEnrichmentProgress(
                res.job_id,
                (data) => this.setState({ progress: data }),
                (data) => {
                    this.setState({
                        processing: false,
                        step: "done",
                        progress: data,
                    });
                    this.showToast(`Enrichissement terminé : ${data.count || 0} produit(s) enrichi(s)`);
                    this.loadHistory();
                },
                (err) => {
                    this.setState({ processing: false, error: err, step: "select_products" });
                    this.showToast("Erreur : " + err, "error");
                }
            );
        } catch (e) {
            this.setState({ processing: false, error: e.message, step: "select_products" });
            this.showToast("Erreur : " + e.message, "error");
        }
    }

    resetFlow() {
        this.setState({
            step: "upload",
            uploadedDoc: null,
            selectedProducts: new Set(),
            progress: null,
            jobId: null,
            error: null,
        });
    }

    async deleteEnrichment(id) {
        if (!confirm("Supprimer ce document d'enrichissement ?")) return;
        try {
            await api.deleteEnrichmentDocument(id);
            this.showToast("Document d'enrichissement supprimé");
            this.loadHistory();
        } catch (e) {
            this.showToast("Erreur : " + e.message, "error");
        }
    }

    renderStepIndicator() {
        const { step } = this.state;
        const steps = [
            { key: "upload", label: "1. Upload", icon: "📄" },
            { key: "select_products", label: "2. Sélection", icon: "🎯" },
            { key: "processing", label: "3. Enrichissement", icon: "⚡" },
            { key: "done", label: "4. Terminé", icon: "✅" },
        ];
        const currentIdx = steps.findIndex((s) => s.key === step);

        return (
            <div class="flex items-center gap-2 mb-8">
                {steps.map((s, i) => (
                    <div class="flex items-center gap-2" key={s.key}>
                        <div
                            class={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${i === currentIdx
                                    ? "gradient-primary text-white shadow-md shadow-indigo-200/50"
                                    : i < currentIdx
                                        ? "bg-green-100 text-green-700"
                                        : "bg-gray-100 text-gray-400"
                                }`}
                        >
                            <span>{s.icon}</span>
                            <span>{s.label}</span>
                        </div>
                        {i < steps.length - 1 && (
                            <IconArrowRight size={16} class={i < currentIdx ? "text-green-400" : "text-gray-300"} />
                        )}
                    </div>
                ))}
            </div>
        );
    }

    renderUploadStep() {
        const { uploading, enrichmentType } = this.state;

        return (
            <div class="space-y-6">
                {/* Type selection */}
                <div>
                    <label class="block text-sm font-semibold text-gray-700 mb-3">Type de document</label>
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {ENRICHMENT_TYPES.map((t) => (
                            <button
                                key={t.value}
                                class={`p-4 rounded-xl border-2 text-left transition-all duration-200 hover:shadow-md ${enrichmentType === t.value
                                        ? `${t.color} border-current shadow-sm scale-[1.02]`
                                        : "bg-white border-gray-200 hover:border-gray-300"
                                    }`}
                                onClick={() => this.setState({ enrichmentType: t.value })}
                            >
                                <p class="font-semibold text-sm">{t.label}</p>
                                <p class="text-xs mt-1 opacity-70">{t.desc}</p>
                            </button>
                        ))}
                    </div>
                </div>

                {/* Drop zone */}
                <DropZone
                    accept=".pdf,.docx,.doc,.xlsx,.xls,.csv,.txt,.md"
                    label="Glissez votre document d'enrichissement ici"
                    uploading={uploading}
                    onFiles={(files) => this.handleUpload(files)}
                />
            </div>
        );
    }

    renderProductSelection() {
        const { products, selectedProducts, productSearch, loadingProducts, uploadedDoc, enrichmentType } = this.state;
        const filtered = this.getFilteredProducts();
        const allSelected = filtered.length > 0 && filtered.every((p) => selectedProducts.has(p.id));
        const typeInfo = ENRICHMENT_TYPES.find((t) => t.value === enrichmentType);

        return (
            <div class="space-y-6">
                {/* Summary of uploaded doc */}
                <div class="flex items-center gap-4 p-4 bg-indigo-50/50 rounded-xl border border-indigo-100">
                    <div class="w-10 h-10 rounded-lg bg-indigo-100 flex items-center justify-center">
                        <IconFile size={20} class="text-indigo-600" />
                    </div>
                    <div class="flex-1">
                        <p class="font-medium text-gray-900 text-sm">{uploadedDoc?.filename}</p>
                        <div class="flex items-center gap-2 mt-1">
                            <Badge variant="indigo">{typeInfo?.label || enrichmentType}</Badge>
                            <span class="text-xs text-gray-400">Prêt pour l'enrichissement</span>
                        </div>
                    </div>
                </div>

                {/* Search + select all */}
                <div class="flex items-center gap-3">
                    <div class="relative flex-1">
                        <IconSearch size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                        <input
                            type="text"
                            placeholder="Rechercher par nom, référence, marque..."
                            class="w-full pl-10 pr-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400 transition-all"
                            value={productSearch}
                            onInput={(e) => this.setState({ productSearch: e.target.value })}
                        />
                    </div>
                    <button
                        class="px-4 py-2.5 rounded-xl text-sm font-medium border transition-all hover:shadow-sm whitespace-nowrap bg-white border-gray-200 text-gray-700 hover:bg-gray-50"
                        onClick={() => this.selectAll()}
                    >
                        {allSelected ? "Tout désélectionner" : "Tout sélectionner"}
                    </button>
                </div>

                {/* Product list */}
                <div class="border border-gray-200/80 rounded-xl overflow-hidden max-h-[400px] overflow-y-auto">
                    {loadingProducts ? (
                        <div class="p-8 text-center">
                            <IconSpinner size={24} class="mx-auto text-indigo-500" />
                            <p class="text-sm text-gray-500 mt-2">Chargement des produits...</p>
                        </div>
                    ) : filtered.length === 0 ? (
                        <div class="p-8 text-center text-gray-400">
                            <p class="text-sm">Aucun produit trouvé</p>
                        </div>
                    ) : (
                        filtered.map((p) => {
                            const selected = selectedProducts.has(p.id);
                            return (
                                <div
                                    key={p.id}
                                    class={`flex items-center gap-3 px-4 py-3 border-b border-gray-100 last:border-b-0 cursor-pointer transition-all ${selected ? "bg-indigo-50/50" : "hover:bg-gray-50/50"
                                        }`}
                                    onClick={() => this.toggleProduct(p.id)}
                                >
                                    <div
                                        class={`w-5 h-5 rounded-md border-2 flex items-center justify-center shrink-0 transition-all ${selected
                                                ? "bg-indigo-600 border-indigo-600"
                                                : "border-gray-300 bg-white"
                                            }`}
                                    >
                                        {selected && (
                                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3">
                                                <polyline points="20 6 9 17 4 12" />
                                            </svg>
                                        )}
                                    </div>
                                    <div class="flex-1 min-w-0">
                                        <p class="text-sm font-medium text-gray-900 truncate">{p.name || "Sans nom"}</p>
                                        <div class="flex items-center gap-2 mt-0.5">
                                            {p.reference && <span class="text-xs text-gray-400">Réf: {p.reference}</span>}
                                            {p.brand && <span class="text-xs text-gray-400">• {p.brand}</span>}
                                            {p.supplier_name && <span class="text-xs text-gray-400">• {p.supplier_name}</span>}
                                        </div>
                                    </div>
                                    <Badge variant={p.status === "validated" ? "success" : "default"} size="sm">
                                        {p.status || "draft"}
                                    </Badge>
                                </div>
                            );
                        })
                    )}
                </div>

                {/* Action */}
                <div class="flex items-center justify-between">
                    <button
                        class="px-4 py-2 rounded-xl text-sm font-medium text-gray-600 hover:bg-gray-100 transition-all"
                        onClick={() => this.resetFlow()}
                    >
                        ← Retour
                    </button>
                    <button
                        class={`px-6 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 ${selectedProducts.size > 0
                                ? "gradient-primary text-white shadow-md shadow-indigo-200/50 hover:shadow-lg hover:shadow-indigo-200/70 hover:scale-[1.02]"
                                : "bg-gray-100 text-gray-400 cursor-not-allowed"
                            }`}
                        disabled={selectedProducts.size === 0}
                        onClick={() => this.handleEnrich()}
                    >
                        Enrichir {selectedProducts.size} produit{selectedProducts.size > 1 ? "s" : ""}
                    </button>
                </div>
            </div>
        );
    }

    renderProcessing() {
        const { progress } = this.state;
        const pct = progress ? Math.min(progress.progress || 0, 100) : 0;

        return (
            <div class="text-center py-12">
                <div class="w-20 h-20 rounded-2xl gradient-primary flex items-center justify-center mx-auto mb-6 shadow-lg shadow-indigo-200/50">
                    <IconSpinner size={32} class="text-white" />
                </div>
                <h3 class="text-lg font-bold text-gray-900">Enrichissement en cours...</h3>
                <p class="text-sm text-gray-500 mt-2 max-w-md mx-auto">
                    {progress?.message || "Traitement du document..."}
                </p>

                {/* Progress bar */}
                <div class="max-w-lg mx-auto mt-6">
                    <div class="flex justify-between text-xs text-gray-400 mb-2">
                        <span>Progression</span>
                        <span>{pct}%</span>
                    </div>
                    <div class="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                            class="h-full gradient-primary rounded-full transition-all duration-500"
                            style={{ width: `${pct}%` }}
                        />
                    </div>
                </div>

                {progress?.count > 0 && (
                    <p class="text-sm text-indigo-600 font-medium mt-4">
                        {progress.count} produit(s) enrichi(s)
                    </p>
                )}
            </div>
        );
    }

    renderDone() {
        const { progress } = this.state;

        return (
            <div class="text-center py-12">
                <div class="w-20 h-20 rounded-2xl bg-green-100 flex items-center justify-center mx-auto mb-6">
                    <IconCheckCircle size={36} class="text-green-600" />
                </div>
                <h3 class="text-lg font-bold text-gray-900">Enrichissement terminé !</h3>
                <p class="text-sm text-gray-500 mt-2">
                    {progress?.count || 0} produit(s) ont été enrichis avec succès.
                </p>
                <div class="flex items-center justify-center gap-3 mt-8">
                    <button
                        class="px-6 py-2.5 rounded-xl text-sm font-semibold gradient-primary text-white shadow-md shadow-indigo-200/50 hover:shadow-lg transition-all"
                        onClick={() => this.resetFlow()}
                    >
                        Nouvel enrichissement
                    </button>
                    <Link
                        to="/products"
                        class="px-6 py-2.5 rounded-xl text-sm font-medium bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 transition-all no-underline"
                    >
                        Voir les produits
                    </Link>
                </div>
            </div>
        );
    }

    renderHistory() {
        const { enrichmentHistory, loadingHistory } = this.state;

        if (loadingHistory) {
            return (
                <div class="p-8 text-center">
                    <IconSpinner size={20} class="mx-auto text-gray-400" />
                </div>
            );
        }

        if (!enrichmentHistory.length) {
            return (
                <div class="p-8 text-center text-gray-400">
                    <p class="text-sm">Aucun enrichissement effectué</p>
                </div>
            );
        }

        // Group by document
        const byDoc = {};
        enrichmentHistory.forEach((ed) => {
            const key = ed.document_id;
            if (!byDoc[key]) {
                byDoc[key] = {
                    document_filename: ed.document_filename,
                    enrichment_type: ed.enrichment_type,
                    created_at: ed.created_at,
                    items: [],
                };
            }
            byDoc[key].items.push(ed);
        });

        return (
            <div class="space-y-3">
                {Object.entries(byDoc).map(([docId, group]) => {
                    const statusInfo = STATUS_BADGES[group.items[0]?.status] || STATUS_BADGES.pending;
                    return (
                        <div key={docId} class="border border-gray-200/80 rounded-xl p-4 hover:shadow-sm transition-all">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center gap-3">
                                    <div class="w-9 h-9 rounded-lg bg-gray-100 flex items-center justify-center">
                                        <IconFile size={16} class="text-gray-500" />
                                    </div>
                                    <div>
                                        <p class="text-sm font-medium text-gray-900">{group.document_filename || "Document"}</p>
                                        <div class="flex items-center gap-2 mt-0.5">
                                            <Badge variant="indigo" size="sm">
                                                {ENRICHMENT_TYPES.find((t) => t.value === group.enrichment_type)?.label || group.enrichment_type}
                                            </Badge>
                                            <span class="text-xs text-gray-400">
                                                {group.items.length} produit{group.items.length > 1 ? "s" : ""} enrichi{group.items.length > 1 ? "s" : ""}
                                            </span>
                                            <Badge variant={statusInfo.variant} size="sm">{statusInfo.label}</Badge>
                                        </div>
                                    </div>
                                </div>
                                <div class="flex items-center gap-2">
                                    <span class="text-xs text-gray-400">
                                        {group.created_at ? new Date(group.created_at).toLocaleDateString("fr-FR") : ""}
                                    </span>
                                    <button
                                        class="p-1.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition-all"
                                        onClick={() => {
                                            group.items.forEach((ed) => this.deleteEnrichment(ed.id));
                                        }}
                                        title="Supprimer"
                                    >
                                        <IconTrash size={14} />
                                    </button>
                                </div>
                            </div>

                            {/* Product list */}
                            <div class="mt-3 space-y-1">
                                {group.items.slice(0, 5).map((ed) => (
                                    <div key={ed.id} class="flex items-center gap-2 text-xs text-gray-500 pl-12">
                                        <span class="w-1.5 h-1.5 rounded-full bg-green-400" />
                                        <span class="font-medium text-gray-700">{ed.product_name || "Produit"}</span>
                                        {ed.match_method && (
                                            <span class="text-gray-400">• {METHOD_LABELS[ed.match_method] || ed.match_method}</span>
                                        )}
                                        {ed.match_confidence != null && (
                                            <span class="text-gray-400">({Math.round(ed.match_confidence * 100)}%)</span>
                                        )}
                                    </div>
                                ))}
                                {group.items.length > 5 && (
                                    <p class="text-xs text-gray-400 pl-12">+{group.items.length - 5} autre(s)</p>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        );
    }

    render() {
        const { step, toast, error } = this.state;

        return (
            <div class="p-6 md:p-8 max-w-5xl mx-auto">
                <PageHeader
                    title="Enrichissement"
                    subtitle="Enrichissez vos produits existants avec des documents complémentaires"
                />

                {toast && <Toast message={toast.message} type={toast.type} onClose={() => this.setState({ toast: null })} />}

                {error && (
                    <div class="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
                        {error}
                    </div>
                )}

                {this.renderStepIndicator()}

                {/* Main content card */}
                <Card>
                    <div class="p-6">
                        {step === "upload" && this.renderUploadStep()}
                        {step === "select_products" && this.renderProductSelection()}
                        {step === "processing" && this.renderProcessing()}
                        {step === "done" && this.renderDone()}
                    </div>
                </Card>

                {/* History section */}
                <div class="mt-10">
                    <h2 class="text-lg font-bold text-gray-900 mb-4">Historique des enrichissements</h2>
                    {this.renderHistory()}
                </div>
            </div>
        );
    }
}
