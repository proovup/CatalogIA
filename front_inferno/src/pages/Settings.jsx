import { Component } from "inferno";
import { api } from "../api";
import PageHeader from "../components/PageHeader";
import Card from "../components/Card";
import Badge from "../components/Badge";
import { IconCheckCircle, IconAlertCircle, IconSave } from "../components/Icons";
import { PROVIDERS, MODELS, DEFAULT_PROVIDER, DEFAULT_MODEL } from "../constants";

export default class Settings extends Component {
  constructor(props) {
    super(props);
    this.state = {
      loading: true,
      config: null,
      error: null,
      saved: false,

      // User preferences
      defaultProvider: localStorage.getItem("default_provider") || DEFAULT_PROVIDER,
      defaultModel: localStorage.getItem("default_model") || DEFAULT_MODEL,
    };
  }

  componentDidMount() {
    this.loadConfig();
  }

  async loadConfig() {
    this.setState({ loading: true });
    try {
      const config = await api.getConfig();
      this.setState({ config, loading: false });
    } catch (e) {
      this.setState({ error: e.message, loading: false });
    }
  }

  savePreferences() {
    localStorage.setItem("default_provider", this.state.defaultProvider);
    localStorage.setItem("default_model", this.state.defaultModel);
    this.setState({ saved: true });
    setTimeout(() => this.setState({ saved: false }), 2000);
  }

  render() {
    const { loading, config, error, defaultProvider, defaultModel, saved } = this.state;

    return (
      <div class="p-6 md:p-8 max-w-4xl mx-auto">
        <PageHeader title="Configuration" subtitle="Paramètres globaux et état du système" />

        <div class="space-y-6">
            {/* Preference Section */}
            <Card>
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-base font-semibold text-gray-900">Modèle IA par défaut</h2>
                    {saved && <span class="text-xs font-medium text-green-600 bg-green-50 px-2 py-1 rounded-lg">Sauvegardé !</span>}
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Fournisseur</label>
                        <select
                            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-100 focus:border-indigo-400 outline-none transition-all"
                            value={defaultProvider}
                            onChange={(e) => this.setState({ defaultProvider: e.target.value, defaultModel: MODELS[e.target.value]?.[0] || "" })}
                        >
                            {PROVIDERS.map(p => (
                                <option value={p.value}>{p.label}</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Modèle</label>
                         <div class="relative">
                            <input
                                list="model-list"
                                type="text"
                                class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-100 focus:border-indigo-400 outline-none transition-all"
                                value={defaultModel}
                                onInput={(e) => this.setState({ defaultModel: e.target.value })}
                                placeholder="Nom du modèle..."
                            />
                            <datalist id="model-list">
                                {(MODELS[defaultProvider] || []).map(m => (
                                    <option value={m} />
                                ))}
                            </datalist>
                        </div>
                        <p class="text-xs text-gray-500 mt-1">Vous pouvez saisir un modèle personnalisé si nécessaire.</p>
                    </div>
                </div>

                <div class="mt-4 flex justify-end">
                    <button
                        class="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
                        onClick={() => this.savePreferences()}
                    >
                        <IconSave size={16} />
                        Enregistrer
                    </button>
                </div>
            </Card>

            {/* System Status Section */}
             <Card>
                <h2 class="text-base font-semibold text-gray-900 mb-4">État du système</h2>

                {loading ? (
                    <div class="py-8 text-center text-gray-500">Chargement de la configuration...</div>
                ) : error ? (
                    <div class="p-4 bg-red-50 text-red-700 rounded-lg border border-red-200">
                        Erreur: {error}
                    </div>
                ) : config ? (
                    <div class="space-y-6">
                        {/* Env Vars */}
                        <div>
                            <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Variables d'environnement</h3>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {Object.entries(config.env_vars).map(([key, present]) => (
                                    <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100">
                                        <span class="text-sm font-mono text-gray-700">{key}</span>
                                        <Badge variant={present ? "success" : "danger"} size="sm">
                                            {present ? "Configuré" : "Manquant"}
                                        </Badge>
                                    </div>
                                ))}
                            </div>
                        </div>

                         {/* Providers */}
                        <div>
                            <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Fournisseurs IA</h3>
                            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {Object.entries(config.providers).map(([key, enabled]) => (
                                    <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100">
                                        <span class="text-sm font-medium text-gray-700 capitalize">{key}</span>
                                        <div class="flex items-center gap-2">
                                            {enabled ? (
                                                <IconCheckCircle size={16} class="text-green-500" />
                                            ) : (
                                                <IconAlertCircle size={16} class="text-gray-300" />
                                            )}
                                            <span class={`text-xs font-medium ${enabled ? "text-green-700" : "text-gray-400"}`}>
                                                {enabled ? "Activé" : "Non configuré"}
                                            </span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                ) : null}
            </Card>
        </div>
      </div>
    );
  }
}
