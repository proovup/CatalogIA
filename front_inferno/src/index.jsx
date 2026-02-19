import { Component } from "inferno";
import { render } from "inferno";
import { BrowserRouter, Route, Switch, Link } from "inferno-router";
import "./index.css";
import Dashboard from "./pages/Dashboard";
import ProductsPage from "./pages/Products";
import ProductDetail from "./pages/ProductDetail";
import Suppliers from "./pages/Suppliers";
import SupplierDetail from "./pages/SupplierDetail";
import Formats from "./pages/Formats";
import Enrichment from "./pages/Enrichment";
import Settings from "./pages/Settings";
import { IconDashboard, IconFactory, IconPackage, IconLayers, IconZap, IconChevronLeft, IconChevronRight, IconDatabase, IconSettings } from "./components/Icons";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: IconDashboard },
  { to: "/suppliers", label: "Fournisseurs", icon: IconFactory },
  { to: "/products", label: "Produits", icon: IconPackage },
  { to: "/enrichment", label: "Enrichissement", icon: IconDatabase },
  { to: "/formats", label: "Formats Custom", icon: IconLayers },
  { to: "/settings", label: "Configuration", icon: IconSettings },
];

function NavLink({ to, label, icon: Icon, collapsed }) {
  const active = typeof window !== "undefined" && (
    to === "/" ? window.location.pathname === "/" : window.location.pathname.startsWith(to)
  );
  return (
    <Link
      to={to}
      class={`group relative flex items-center gap-3 rounded-xl text-sm font-medium transition-all duration-200 no-underline ${collapsed ? "px-3 py-2.5 justify-center" : "px-3 py-2.5"
        } ${active
          ? "bg-white text-indigo-700 shadow-sm shadow-indigo-100/50"
          : "text-gray-500 hover:bg-white/60 hover:text-gray-900"
        }`}
    >
      {active && (
        <span class="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 rounded-r-full gradient-primary transition-all duration-300" />
      )}
      <Icon size={20} class={`shrink-0 transition-colors ${active ? "text-indigo-600" : "text-gray-400 group-hover:text-gray-600"}`} />
      {!collapsed && <span>{label}</span>}
      {collapsed && (
        <span class="absolute left-full ml-2 px-2 py-1 bg-gray-900 text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50">
          {label}
        </span>
      )}
    </Link>
  );
}

class Sidebar extends Component {
  constructor(props) {
    super(props);
    this.state = { collapsed: false };
  }

  render() {
    const { collapsed } = this.state;

    return (
      <aside
        class={`fixed top-0 left-0 h-screen bg-gray-50/80 backdrop-blur-sm border-r border-gray-200/60 flex flex-col z-40 transition-all duration-300 ${collapsed ? "w-[72px]" : "w-[256px]"
          }`}
      >
        {/* Logo */}
        <div class={`flex items-center h-16 px-4 border-b border-gray-200/60 shrink-0 ${collapsed ? "justify-center" : "gap-3"}`}>
          <Link to="/" class="flex items-center gap-2.5 no-underline shrink-0">
            <div class="relative w-9 h-9 rounded-xl gradient-primary flex items-center justify-center shadow-md shadow-indigo-200/70">
              <IconPackage size={16} class="text-white" />
              <span class="absolute -right-0.5 -bottom-0.5 w-4 h-4 rounded-full bg-white border border-indigo-100 flex items-center justify-center">
                <IconZap size={10} class="text-indigo-600" />
              </span>
            </div>
            {!collapsed && (
              <span class="flex flex-col leading-tight">
                <span class="font-bold text-base gradient-text">CatalogIA</span>
                <span class="text-[10px] text-gray-400 tracking-wide uppercase">product generator</span>
              </span>
            )}
          </Link>
        </div>

        {/* Nav items */}
        <nav class="flex-1 px-3 py-4 space-y-1 sidebar-scroll overflow-y-auto">
          {NAV_ITEMS.map((item) => (
            <NavLink to={item.to} label={item.label} icon={item.icon} collapsed={collapsed} />
          ))}
        </nav>

        {/* Footer */}
        <div class={`px-3 py-3 border-t border-gray-200/60 shrink-0 ${collapsed ? "flex justify-center" : ""}`}>
          <button
            class="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-xs text-gray-400 hover:text-gray-600 hover:bg-white/60 transition-all"
            onClick={() => this.setState({ collapsed: !collapsed })}
          >
            {collapsed ? <IconChevronRight size={16} /> : (
              <>
                <IconChevronLeft size={16} />
                <span>Réduire</span>
              </>
            )}
          </button>
          {!collapsed && (
            <p class="text-center text-[10px] text-gray-300 mt-2">CatalogIA v0.1.0</p>
          )}
        </div>
      </aside>
    );
  }
}

class App extends Component {
  render() {
    return (
      <BrowserRouter>
        <div class="min-h-screen bg-gray-50/50">
          <Sidebar />
          <main class="ml-[256px] transition-all duration-300">
            <div class="page-enter">
              <Switch>
                <Route exact path="/" component={Dashboard} />
                <Route exact path="/suppliers" component={Suppliers} />
                <Route path="/suppliers/:id" component={SupplierDetail} />
                <Route exact path="/products" component={ProductsPage} />
                <Route path="/products/:id" component={ProductDetail} />
                <Route exact path="/settings" component={Settings} />
                <Route exact path="/enrichment" component={Enrichment} />
                <Route exact path="/formats" component={Formats} />
              </Switch>
            </div>
          </main>
        </div>
      </BrowserRouter>
    );
  }
}

render(<App />, document.getElementById("app"));
