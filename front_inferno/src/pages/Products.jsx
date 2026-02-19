import { Component } from "inferno";
import { Link } from "inferno-router";
import { api } from "../api";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import Badge from "../components/Badge";
import { SkeletonTable } from "../components/Skeleton";
import { IconPackage, IconSearch, IconRefresh, IconArrowRight } from "../components/Icons";

const STATUS_BADGE = {
  draft: "warning",
  validated: "success",
  rejected: "danger",
};
const STATUS_LABEL = {
  draft: "Brouillon",
  validated: "Validé",
  rejected: "Rejeté",
};

export default class ProductsPage extends Component {
  constructor(props) {
    super(props);
    this.state = {
      products: [],
      suppliers: [],
      search: "",
      statusFilter: "",
      supplierFilter: "",
      categoryFilter: "",
      brandFilter: "",
      createdFrom: "",
      createdTo: "",
      sortBy: "created_at",
      sortDir: "desc",
      page: 1,
      pageSize: 10,
      loading: true,
      error: null,
    };
  }

  componentDidMount() {
    this.loadSuppliers();
    this.load();
  }

  async loadSuppliers() {
    try {
      const res = await api.listSuppliers();
      this.setState({ suppliers: res.suppliers || [] });
    } catch {}
  }

  async load() {
    this.setState({ loading: true, error: null });
    try {
      const products = await api.listProducts({
        search: this.state.search || undefined,
        status: this.state.statusFilter || undefined,
        supplier_id: this.state.supplierFilter || undefined,
        limit: 200,
      });
      this.setState({ products, loading: false });
    } catch (e) {
      this.setState({ error: e.message, loading: false });
    }
  }

  render() {
    const {
      products,
      suppliers,
      search,
      statusFilter,
      supplierFilter,
      categoryFilter,
      brandFilter,
      createdFrom,
      createdTo,
      sortBy,
      sortDir,
      page,
      pageSize,
      loading,
      error,
    } = this.state;

    const categories = [...new Set(products.map((p) => (p.category || "").trim()).filter(Boolean))]
      .sort((a, b) => a.localeCompare(b, "fr", { sensitivity: "base" }));
    const brands = [...new Set(products.map((p) => (p.brand || "").trim()).filter(Boolean))]
      .sort((a, b) => a.localeCompare(b, "fr", { sensitivity: "base" }));

    const fromDate = createdFrom ? new Date(`${createdFrom}T00:00:00`) : null;
    const toDate = createdTo ? new Date(`${createdTo}T23:59:59`) : null;

    const filteredProducts = products
      .filter((p) => !categoryFilter || (p.category || "") === categoryFilter)
      .filter((p) => !brandFilter || (p.brand || "") === brandFilter)
      .filter((p) => {
        if (!fromDate && !toDate) return true;
        if (!p.created_at) return false;
        const d = new Date(p.created_at);
        if (Number.isNaN(d.getTime())) return false;
        if (fromDate && d < fromDate) return false;
        if (toDate && d > toDate) return false;
        return true;
      })
      .sort((a, b) => {
        const direction = sortDir === "asc" ? 1 : -1;
        if (sortBy === "name") {
          return ((a.name || "").localeCompare((b.name || ""), "fr", { sensitivity: "base" })) * direction;
        }
        const ad = a.created_at ? new Date(a.created_at).getTime() : 0;
        const bd = b.created_at ? new Date(b.created_at).getTime() : 0;
        return (ad - bd) * direction;
      });

    const totalProducts = filteredProducts.length;
    const totalPages = Math.max(1, Math.ceil(totalProducts / pageSize));
    const currentPage = Math.min(page, totalPages);
    const start = (currentPage - 1) * pageSize;
    const paginatedProducts = filteredProducts.slice(start, start + pageSize);

    return (
      <div class="max-w-6xl mx-auto px-4 py-8">
        <PageHeader
          title="Produits"
          subtitle={`${totalProducts} résultat${totalProducts !== 1 ? "s" : ""}`}
        />

        {/* Filters */}
        <div class="bg-white rounded-xl border border-gray-200/80 p-3 mb-6 animate-fade-in">
          <div class="flex flex-wrap items-center gap-3">
            <div class="relative flex-1 min-w-[200px] max-w-xs">
              <IconSearch size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Rechercher un produit..."
                class="w-full border border-gray-200 rounded-lg pl-9 pr-3 py-2 text-sm bg-gray-50/50 transition-all focus-glow"
                value={search}
                onInput={(e) => this.setState({ search: e.target.value })}
                onKeyDown={(e) => e.key === "Enter" && this.load()}
              />
            </div>
            <select
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50/50 transition-all focus-glow"
              value={supplierFilter}
              onChange={(e) => {
                this.setState({ supplierFilter: e.target.value }, () => this.load());
              }}
            >
              <option value="">Tous les fournisseurs</option>
              {suppliers.map((s) => (
                <option value={s.id}>{s.name}</option>
              ))}
            </select>
            <select
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50/50 transition-all focus-glow"
              value={statusFilter}
              onChange={(e) => {
                this.setState({ statusFilter: e.target.value, page: 1 }, () => this.load());
              }}
            >
              <option value="">Tous les statuts</option>
              <option value="draft">Brouillon</option>
              <option value="validated">Validé</option>
              <option value="rejected">Rejeté</option>
            </select>
            <select
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50/50 transition-all focus-glow"
              value={categoryFilter}
              onChange={(e) => this.setState({ categoryFilter: e.target.value, page: 1 })}
            >
              <option value="">Toutes les catégories</option>
              {categories.map((c) => (
                <option value={c}>{c}</option>
              ))}
            </select>
            <select
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50/50 transition-all focus-glow"
              value={brandFilter}
              onChange={(e) => this.setState({ brandFilter: e.target.value, page: 1 })}
            >
              <option value="">Toutes les marques</option>
              {brands.map((b) => (
                <option value={b}>{b}</option>
              ))}
            </select>
            <input
              type="date"
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50/50 transition-all focus-glow"
              value={createdFrom}
              onInput={(e) => this.setState({ createdFrom: e.target.value, page: 1 })}
              title="Créé après le"
            />
            <input
              type="date"
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50/50 transition-all focus-glow"
              value={createdTo}
              onInput={(e) => this.setState({ createdTo: e.target.value, page: 1 })}
              title="Créé avant le"
            />
            <select
              class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-gray-50/50 transition-all focus-glow"
              value={`${sortBy}:${sortDir}`}
              onChange={(e) => {
                const [nextSortBy, nextSortDir] = e.target.value.split(":");
                this.setState({ sortBy: nextSortBy, sortDir: nextSortDir, page: 1 });
              }}
            >
              <option value="created_at:desc">Plus récents</option>
              <option value="created_at:asc">Plus anciens</option>
              <option value="name:asc">Nom (A-Z)</option>
              <option value="name:desc">Nom (Z-A)</option>
            </select>
            <button
              class="inline-flex items-center gap-1.5 gradient-primary text-white rounded-lg px-4 py-2 text-sm font-medium transition-all hover:shadow-lg hover:shadow-indigo-500/25"
              onClick={() => this.load()}
            >
              <IconRefresh size={14} />
              Rechercher
            </button>
          </div>
        </div>

        {error && (
          <div class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-6 text-sm animate-fade-in">{error}</div>
        )}

        {loading ? (
          <SkeletonTable rows={6} cols={5} />
        ) : totalProducts === 0 ? (
          <EmptyState
            icon={<IconPackage size={28} />}
            title="Aucun produit"
            description="Commencez par créer un fournisseur et importer un catalogue pour extraire vos produits."
            actionLabel="Voir les fournisseurs"
            actionTo="/suppliers"
          />
        ) : (
          <div class="bg-white rounded-xl border border-gray-200/80 overflow-hidden animate-scale-in shadow-sm">
            <table class="w-full text-sm">
              <thead class="bg-gray-50/80 border-b border-gray-200">
                <tr>
                  <th class="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wider">Nom</th>
                  <th class="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wider">Catégorie</th>
                  <th class="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wider">Marque</th>
                  <th class="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wider">Créé le</th>
                  <th class="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wider">Fournisseur</th>
                  <th class="text-left px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wider">Statut</th>
                  <th class="text-right px-4 py-3 font-medium text-gray-500 text-xs uppercase tracking-wider">Action</th>
                </tr>
              </thead>
              <tbody>
                {paginatedProducts.map((p, i) => (
                  <tr
                    key={p.id}
                    class={`hover:bg-indigo-50/40 transition-colors border-b border-gray-50 cursor-pointer ${i % 2 === 1 ? "bg-gray-50/30" : ""}`}
                    onClick={() => { window.location.href = `/products/${p.id}`; }}
                  >
                    <td class="px-4 py-3.5 font-medium max-w-xs truncate">
                      {p.name || <span class="text-gray-400 italic">Sans nom</span>}
                    </td>
                    <td class="px-4 py-3.5 text-gray-600 max-w-[160px] truncate">
                      {p.category || "—"}
                    </td>
                    <td class="px-4 py-3.5 text-gray-600 max-w-[140px] truncate">
                      {p.brand || "—"}
                    </td>
                    <td class="px-4 py-3.5 text-gray-600 whitespace-nowrap">
                      {p.created_at ? new Date(p.created_at).toLocaleDateString("fr-FR") : "—"}
                    </td>
                    <td class="px-4 py-3.5 text-xs max-w-[140px] truncate">
                      {p.supplier_name ? (
                        <span
                          class="text-indigo-600 hover:text-indigo-800 font-medium transition-colors"
                          onClick={(e) => { e.stopPropagation(); window.location.href = `/suppliers/${p.supplier_id}`; }}
                        >
                          {p.supplier_name}
                        </span>
                      ) : (
                        <span class="text-gray-300">—</span>
                      )}
                    </td>
                    <td class="px-4 py-3.5">
                      <Badge variant={STATUS_BADGE[p.status] || "default"}>
                        {STATUS_LABEL[p.status] || p.status}
                      </Badge>
                    </td>
                    <td class="px-4 py-3.5 text-right">
                      <span class="inline-flex items-center gap-1.5 text-indigo-600 bg-indigo-50 hover:bg-indigo-100 font-medium text-xs px-3 py-1.5 rounded-lg transition-colors">
                        Voir
                        <IconArrowRight size={12} />
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div class="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-t border-gray-100 bg-gray-50/50">
              <div class="text-xs text-gray-500">
                Affichage {totalProducts === 0 ? 0 : start + 1}-{Math.min(start + pageSize, totalProducts)} sur {totalProducts}
              </div>
              <div class="flex items-center gap-2">
                <label class="text-xs text-gray-500">Par page</label>
                <select
                  class="border border-gray-200 rounded-lg px-2.5 py-1.5 text-xs bg-white"
                  value={String(pageSize)}
                  onChange={(e) => this.setState({ pageSize: Number(e.target.value), page: 1 })}
                >
                  <option value="10">10</option>
                  <option value="20">20</option>
                  <option value="50">50</option>
                </select>
                <button
                  class="px-3 py-1.5 text-xs rounded-lg border border-gray-200 bg-white disabled:opacity-40"
                  disabled={currentPage <= 1}
                  onClick={() => this.setState({ page: currentPage - 1 })}
                >
                  Précédent
                </button>
                <span class="text-xs text-gray-600 min-w-[68px] text-center">
                  {currentPage} / {totalPages}
                </span>
                <button
                  class="px-3 py-1.5 text-xs rounded-lg border border-gray-200 bg-white disabled:opacity-40"
                  disabled={currentPage >= totalPages}
                  onClick={() => this.setState({ page: currentPage + 1 })}
                >
                  Suivant
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }
}
