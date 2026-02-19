import { Component } from "inferno";
import { Link } from "inferno-router";
import { api } from "../api";
import Card from "../components/Card";
import PageHeader from "../components/PageHeader";
import { SkeletonMetrics } from "../components/Skeleton";
import { IconFactory, IconFileText, IconPackage, IconCheckCircle, IconZap, IconSparkles, IconPlus, IconArrowRight, IconLayers } from "../components/Icons";

const METRIC_STYLES = [
  { bg: "bg-blue-50", iconBg: "bg-blue-100", iconColor: "text-blue-600", valueColor: "text-blue-700", Icon: IconFactory },
  { bg: "bg-amber-50", iconBg: "bg-amber-100", iconColor: "text-amber-600", valueColor: "text-amber-700", Icon: IconFileText },
  { bg: "bg-indigo-50", iconBg: "bg-indigo-100", iconColor: "text-indigo-600", valueColor: "text-indigo-700", Icon: IconPackage },
  { bg: "bg-green-50", iconBg: "bg-green-100", iconColor: "text-green-600", valueColor: "text-green-700", Icon: IconCheckCircle },
];

const STEP_ICONS = [IconFactory, IconFileText, IconZap, IconSparkles];

export default class Dashboard extends Component {
  constructor(props) {
    super(props);
    this.state = {
      suppliers: 0,
      documents: 0,
      products: 0,
      validated: 0,
      loading: true,
    };
  }

  componentDidMount() {
    this.load();
  }

  async load() {
    this.setState({ loading: true });
    try {
      const stats = await api.getProductStats().catch(() => null);

      if (stats) {
        this.setState({
          suppliers: stats.suppliers || 0,
          documents: stats.documents || 0,
          products: stats.products || 0,
          validated: stats.validated || 0,
          loading: false,
        });
        return;
      }

      const [suppRes, docs, products] = await Promise.all([
        api.listSuppliers().catch(() => ({ total: 0 })),
        api.listDocuments().catch(() => []),
        api.listProducts({ limit: 200 }).catch(() => []),
      ]);
      this.setState({
        suppliers: suppRes.total || 0,
        documents: Array.isArray(docs) ? docs.length : 0,
        products: Array.isArray(products) ? products.length : 0,
        validated: Array.isArray(products) ? products.filter((p) => p.status === "validated").length : 0,
        loading: false,
      });
    } catch {
      this.setState({ loading: false });
    }
  }

  render() {
    const { suppliers, documents, products, validated, loading } = this.state;

    const metrics = [
      { label: "Fournisseurs", value: suppliers, link: "/suppliers" },
      { label: "Documents", value: documents, link: "/suppliers" },
      { label: "Produits", value: products, link: "/products" },
      { label: "Validés", value: validated, link: "/products" },
    ];

    const steps = [
      { num: 1, title: "Fournisseurs", desc: "Créez vos fournisseurs. Chaque fournisseur centralise ses catalogues et produits associés.", link: "/suppliers" },
      { num: 2, title: "Import catalogues", desc: "Depuis la fiche fournisseur, importez vos fichiers Excel, PDF, CSV. La structure est détectée automatiquement.", link: "/suppliers" },
      { num: 3, title: "Extraction IA", desc: "L'IA extrait automatiquement les produits, noms, prix et descriptions depuis vos documents.", link: "/suppliers" },
      { num: 4, title: "Enrichissement", desc: "Classifiez et regénérez les fiches produits avec l'IA selon vos formats YAML personnalisés.", link: "/products" },
    ];

    return (
      <div class="max-w-6xl mx-auto px-4 py-8">
        <PageHeader
          title="Dashboard"
          subtitle="Vue d'ensemble de votre catalogue produit"
        />

        {loading ? (
          <div class="space-y-8">
            <SkeletonMetrics count={4} />
            <div class="skeleton" style="height: 200px" />
          </div>
        ) : (
          <div class="space-y-8">
            {/* Metrics */}
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 stagger-children">
              {metrics.map((m, i) => {
                const style = METRIC_STYLES[i];
                return (
                  <Link to={m.link} class="block no-underline">
                    <Card className={`${style.bg} border-transparent hover:shadow-lg hover:shadow-${style.iconColor.split("-")[1]}-100/50`}>
                      <div class="flex items-center justify-between mb-3">
                        <div class={`w-10 h-10 rounded-xl ${style.iconBg} flex items-center justify-center`}>
                          <style.Icon size={20} class={style.iconColor} />
                        </div>
                        <IconArrowRight size={16} class="text-gray-300" />
                      </div>
                      <div class={`text-2xl font-bold ${style.valueColor} animate-counter`}>{m.value}</div>
                      <div class="text-sm text-gray-500 mt-0.5">{m.label}</div>
                    </Card>
                  </Link>
                );
              })}
            </div>

            {/* Workflow timeline */}
            <div>
              <h2 class="text-lg font-semibold mb-4 flex items-center gap-2">
                <IconZap size={20} class="text-indigo-500" />
                Guide de démarrage
              </h2>
              <div class="relative">
                {/* Connecting line */}
                <div class="hidden md:block absolute top-10 left-[calc(12.5%+16px)] right-[calc(12.5%+16px)] h-0.5 bg-gradient-to-r from-indigo-200 via-violet-200 to-indigo-200" />
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 stagger-children">
                  {steps.map((s, i) => {
                    const StepIcon = STEP_ICONS[i];
                    return (
                      <Link to={s.link} class="block no-underline">
                        <Card className="relative text-center">
                          <div class="flex justify-center mb-3">
                            <div class="relative">
                              <div class="w-10 h-10 rounded-xl gradient-primary flex items-center justify-center">
                                <StepIcon size={20} class="text-white" />
                              </div>
                              <span class="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-white border-2 border-indigo-500 flex items-center justify-center text-[10px] font-bold text-indigo-600">
                                {s.num}
                              </span>
                            </div>
                          </div>
                          <h3 class="font-semibold text-gray-900 text-sm mb-1">{s.title}</h3>
                          <p class="text-xs text-gray-500 leading-relaxed">{s.desc}</p>
                        </Card>
                      </Link>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Quick actions */}
            <div>
              <h2 class="text-lg font-semibold mb-4">Actions rapides</h2>
              <div class="flex flex-wrap gap-3 stagger-children">
                <Link
                  to="/suppliers"
                  class="inline-flex items-center gap-2 gradient-primary text-white font-medium rounded-lg px-5 py-2.5 text-sm transition-all hover:shadow-lg hover:shadow-indigo-500/25 no-underline"
                >
                  <IconPlus size={16} />
                  Nouveau fournisseur
                </Link>
                <Link
                  to="/formats"
                  class="inline-flex items-center gap-2 bg-white hover:bg-gray-50 text-gray-700 font-medium rounded-lg px-5 py-2.5 text-sm border border-gray-200 transition-all hover:shadow-md hover:border-gray-300 no-underline"
                >
                  <IconLayers size={16} />
                  Gérer les formats
                </Link>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }
}
