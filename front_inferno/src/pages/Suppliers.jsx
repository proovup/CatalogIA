import { Component } from "inferno";
import { Link } from "inferno-router";
import { api } from "../api";
import Card from "../components/Card";
import Badge from "../components/Badge";
import Modal from "../components/Modal";
import Field from "../components/Field";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import { SkeletonCard } from "../components/Skeleton";
import { IconFactory, IconPlus, IconArrowRight, IconClock, IconSpinner } from "../components/Icons";

const AVATAR_COLORS = [
  "bg-indigo-500", "bg-violet-500", "bg-blue-500", "bg-emerald-500",
  "bg-amber-500", "bg-rose-500", "bg-cyan-500", "bg-fuchsia-500",
];

function getInitials(name) {
  return (name || "?").split(" ").map((w) => w[0]).join("").toUpperCase().slice(0, 2);
}

function getAvatarColor(name) {
  let hash = 0;
  for (let i = 0; i < (name || "").length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

export default class Suppliers extends Component {
  constructor(props) {
    super(props);
    this.state = {
      suppliers: [],
      total: 0,
      loading: true,
      error: null,
      showCreate: false,
      newName: "",
      newDesc: "",
      creating: false,
    };
  }

  componentDidMount() {
    this.load();
  }

  async load() {
    this.setState({ loading: true, error: null });
    try {
      const res = await api.listSuppliers();
      this.setState({ suppliers: res.suppliers || [], total: res.total || 0, loading: false });
    } catch (e) {
      this.setState({ error: e.message, loading: false });
    }
  }

  async handleCreate() {
    const { newName, newDesc } = this.state;
    if (!newName.trim()) return;
    this.setState({ creating: true, error: null });
    try {
      await api.createSupplier({ name: newName.trim(), description: newDesc.trim() || null });
      this.setState({ showCreate: false, newName: "", newDesc: "", creating: false });
      await this.load();
    } catch (e) {
      this.setState({ error: e.message, creating: false });
    }
  }

  render() {
    const { suppliers, total, loading, error, showCreate, newName, newDesc, creating } = this.state;

    return (
      <div class="max-w-6xl mx-auto px-4 py-8">
        <PageHeader
          title="Fournisseurs"
          subtitle={`${total} fournisseur${total !== 1 ? "s" : ""}`}
          actions={
            <button
              class="inline-flex items-center gap-2 gradient-primary text-white font-medium rounded-lg px-4 py-2.5 text-sm transition-all hover:shadow-lg hover:shadow-indigo-500/25"
              onClick={() => this.setState({ showCreate: true })}
            >
              <IconPlus size={16} />
              Nouveau fournisseur
            </button>
          }
        />

        {error && (
          <div class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 mb-6 text-sm animate-fade-in">{error}</div>
        )}

        {loading ? (
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map(() => <SkeletonCard lines={3} />)}
          </div>
        ) : suppliers.length === 0 ? (
          <EmptyState
            icon={<IconFactory size={28} />}
            title="Aucun fournisseur"
            description="Commencez par créer votre premier fournisseur pour centraliser ses catalogues et produits."
            actionLabel="Créer le premier fournisseur"
            onAction={() => this.setState({ showCreate: true })}
          />
        ) : (
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
            {suppliers.map((s) => (
              <Link to={`/suppliers/${s.id}`} class="block no-underline">
                <Card className="h-full group">
                  <div class="flex items-start gap-3 mb-3">
                    <div class={`w-10 h-10 rounded-xl ${getAvatarColor(s.name)} flex items-center justify-center text-white text-sm font-bold shrink-0`}>
                      {getInitials(s.name)}
                    </div>
                    <div class="min-w-0 flex-1">
                      <div class="flex items-start justify-between gap-2">
                        <h3 class="font-semibold text-gray-900 truncate">{s.name}</h3>
                        <Badge variant={s.is_active === "active" ? "success" : "default"}>
                          {s.is_active === "active" ? "Actif" : "Inactif"}
                        </Badge>
                      </div>
                      {s.description && (
                        <p class="text-sm text-gray-500 line-clamp-2 mt-1">{s.description}</p>
                      )}
                    </div>
                  </div>
                  <div class="flex items-center justify-between pt-3 border-t border-gray-100">
                    <p class="text-xs text-gray-400 flex items-center gap-1">
                      <IconClock size={12} />
                      {new Date(s.created_at).toLocaleDateString("fr-FR")}
                    </p>
                    <IconArrowRight size={14} class="text-gray-300 group-hover:text-indigo-500 transition-colors" />
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        )}

        <Modal open={showCreate} onClose={() => this.setState({ showCreate: false })} title="Nouveau fournisseur">
          <div class="space-y-4">
            <Field
              label="Nom"
              value={newName}
              onInput={(v) => this.setState({ newName: v })}
              required
              placeholder="Nom du fournisseur"
            />
            <Field
              label="Description"
              value={newDesc}
              onInput={(v) => this.setState({ newDesc: v })}
              textarea
              placeholder="Description (optionnel)"
              rows={3}
            />
            <div class="flex justify-end gap-3 pt-2">
              <button
                class="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
                onClick={() => this.setState({ showCreate: false })}
              >
                Annuler
              </button>
              <button
                class="inline-flex items-center gap-2 gradient-primary text-white font-medium rounded-lg px-5 py-2.5 text-sm transition-all hover:shadow-lg hover:shadow-indigo-500/25 disabled:opacity-50"
                disabled={!newName.trim() || creating}
                onClick={() => this.handleCreate()}
              >
                {creating ? <><IconSpinner size={16} /> Création...</> : "Créer"}
              </button>
            </div>
          </div>
        </Modal>
      </div>
    );
  }
}
