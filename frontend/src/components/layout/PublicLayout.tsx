import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Menu, Moon, Sun, X } from "lucide-react";
import clsx from "clsx";
import { Logo } from "../Logo";
import { Button } from "../ui/primitives";
import { homeFor, useAuth, applyPreferences } from "@/lib/auth";

const NAV = [
  { to: "/", label: "Home", hash: "" },
  { to: "/#features", label: "Features", hash: "#features" },
  { to: "/#how-it-works", label: "How It Works", hash: "#how-it-works" },
  { to: "/#patients", label: "For Patients", hash: "#patients" },
  { to: "/#doctors", label: "For Doctors", hash: "#doctors" },
  { to: "/blueprint", label: "Blueprint", hash: "" },
  { to: "/about", label: "About", hash: "" },
];

export function ThemeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.dataset.theme === "dark");
  return (
    <button aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      className="grid h-10 w-10 place-items-center rounded-xl text-ink-2 hover:bg-surface-2"
      onClick={() => {
        const next = dark ? "light" : "dark";
        try { localStorage.setItem("impulse-theme", next); } catch { /* storage unavailable */ }
        applyPreferences({ theme: next });
        setDark(!dark);
      }}>
      {dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
    </button>
  );
}

export function PublicLayout() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const loc = useLocation();

  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 8);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  useEffect(() => {
    setOpen(false);
    if (loc.hash) document.querySelector(loc.hash)?.scrollIntoView({ behavior: "smooth" });
    else window.scrollTo({ top: 0 });
  }, [loc.pathname, loc.hash]);

  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[70] focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>
      <header className={clsx("sticky top-0 z-40 transition-all", scrolled ? "border-b border-line bg-bg/85 backdrop-blur-md" : "bg-transparent")}>
        <nav className="container-page flex h-16 items-center justify-between gap-4" aria-label="Main">
          <Link to="/" aria-label="DoseWISE home"><Logo /></Link>
          <div className="hidden items-center gap-1 xl:flex">
            {NAV.map((n) => (
              <NavLink key={n.label} to={n.to}
                className={() => clsx("whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  (n.hash ? loc.hash === n.hash : loc.pathname === n.to && !loc.hash) ? "text-ink" : "text-ink-3 hover:text-ink")}>
                {n.label}
              </NavLink>
            ))}
          </div>
          <div className="hidden items-center gap-2 xl:flex">
            <ThemeToggle />
            {user ? (
              <Link to={homeFor(user.role)}><Button>Open DoseWISE</Button></Link>
            ) : (
              <>
                <Link to="/login" className="whitespace-nowrap rounded-lg px-3 py-2 text-sm font-semibold text-ink-2 hover:text-ink">Log In</Link>
                <Link to="/register"><Button className="whitespace-nowrap">Get Started</Button></Link>
              </>
            )}
          </div>
          <button className="grid h-10 w-10 place-items-center rounded-xl hover:bg-surface-2 xl:hidden" aria-label="Open menu"
            aria-expanded={open} onClick={() => setOpen(!open)}>
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </nav>
        <AnimatePresence>
          {open && (
            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden border-b border-line bg-bg xl:hidden">
              <div className="container-page flex flex-col gap-1 py-3">
                {NAV.map((n) => (
                  <Link key={n.label} to={n.to} className="rounded-lg px-3 py-2.5 font-medium text-ink-2 hover:bg-surface-2">{n.label}</Link>
                ))}
                <div className="mt-2 flex gap-2">
                  {user ? <Link className="flex-1" to={homeFor(user.role)}><Button className="w-full">Open DoseWISE</Button></Link> : <>
                    <Link className="flex-1" to="/login"><Button variant="outline" className="w-full">Log In</Button></Link>
                    <Link className="flex-1" to="/register"><Button className="w-full">Get Started</Button></Link>
                  </>}
                  <ThemeToggle />
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </header>
      <main id="main"><Outlet /></main>
      <Footer />
    </div>
  );
}

function Footer() {
  const cols = [
    { title: "Product", links: [["Features", "/#features"], ["How it works", "/#how-it-works"], ["For patients", "/#patients"], ["For doctors", "/#doctors"], ["Find care", "/directory"]] },
    { title: "Company", links: [["About", "/about"], ["Project blueprint", "/blueprint"], ["Contact", "/contact"], ["Help", "/help"]] },
    { title: "Trust", links: [["Privacy Policy", "/privacy"], ["Terms", "/terms"], ["Security", "/security"], ["Accessibility", "/accessibility"]] },
  ];
  return (
    <footer className="mt-24 border-t border-line bg-surface">
      <div className="container-page grid gap-10 py-14 md:grid-cols-[1.4fr_repeat(3,1fr)]">
        <div>
          <Logo />
          <p className="mt-4 max-w-xs text-sm text-ink-3">Better medication management. More connected care.</p>
          <p className="mt-4 max-w-xs text-xs text-ink-3">
            DoseWISE is in development. It does not provide emergency services — in an emergency in India, call 112.
          </p>
        </div>
        {cols.map((c) => (
          <div key={c.title}>
            <h3 className="text-sm font-bold text-ink">{c.title}</h3>
            <ul className="mt-3 space-y-2">
              {c.links.map(([l, to]) => (
                <li key={l}><Link to={to} className="text-sm text-ink-3 hover:text-ink">{l}</Link></li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-line">
        <div className="container-page flex flex-col gap-2 py-5 text-xs text-ink-3 sm:flex-row sm:justify-between">
          <span>© {new Date().getFullYear()} DoseWISE. All demo data is fictional.</span>
          <span>No certifications, partnerships or regulatory approvals are claimed.</span>
        </div>
      </div>
    </footer>
  );
}
