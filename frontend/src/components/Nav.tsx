"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Trophy,
  BarChart3,
  GitCompareArrows,
  MessageSquare,
  LayoutDashboard,
  Radio,
  Users,
  BookOpen,
  Target,
  Menu,
  X,
} from "lucide-react";

const navGroups = [
  {
    label: "Primary",
    items: [
      { href: "/", label: "Home", icon: Trophy },
      { href: "/scores", label: "Scores", icon: Radio },
      { href: "/dashboard", label: "Rankings", icon: BarChart3 },
      { href: "/bracket", label: "Bracket", icon: LayoutDashboard },
    ],
  },
  {
    label: "Tools",
    items: [
      { href: "/teams", label: "Teams", icon: Users },
      { href: "/compare", label: "Compare", icon: GitCompareArrows },
      { href: "/chat", label: "Madness Agent", icon: MessageSquare },
    ],
  },
  {
    label: "Info",
    items: [
      { href: "/performance", label: "Performance", icon: Target },
      { href: "/about", label: "How It Works", icon: BookOpen },
    ],
  },
];

// Flat list for the desktop nav (preserves original order)
const navItems = navGroups.flatMap((g) => g.items);

export default function Nav() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // Close when clicking outside the menu
  useEffect(() => {
    if (!mobileOpen) return;

    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMobileOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [mobileOpen]);

  // Prevent body scroll while mobile menu is open
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 glass" ref={menuRef}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-16">
          {/* ---- Logo ---- */}
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center font-bold text-sm text-white">
              UM
            </div>
            <span className="font-bold text-lg hidden sm:block">
              Ubunifu <span className="text-accent">Madness</span>
            </span>
          </Link>

          {/* ---- Desktop nav (md+) ---- */}
          <div className="hidden md:flex items-center gap-1">
            {navItems.map((item) => {
              const isActive = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-accent/15 text-accent"
                      : "text-muted hover:text-foreground hover:bg-white/5"
                  }`}
                >
                  <Icon size={16} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </div>

          {/* ---- Hamburger button (mobile only) ---- */}
          <button
            type="button"
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            onClick={() => setMobileOpen((prev) => !prev)}
            className="md:hidden flex items-center justify-center w-10 h-10 rounded-lg text-muted hover:text-foreground hover:bg-white/5 transition-colors"
          >
            {mobileOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      {/* ---- Mobile dropdown panel ---- */}
      <div
        className={`md:hidden overflow-hidden transition-all duration-300 ease-in-out ${
          mobileOpen ? "max-h-[80vh] opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <div className="px-4 pb-6 pt-2 border-t border-card-border space-y-5">
          {navGroups.map((group) => (
            <div key={group.label}>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted mb-2 px-3">
                {group.label}
              </p>

              <div className="space-y-1">
                {group.items.map((item) => {
                  const isActive = pathname === item.href;
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileOpen(false)}
                      className={`flex items-center gap-3 px-3 py-3 rounded-lg text-base font-medium transition-colors ${
                        isActive
                          ? "bg-accent/15 text-accent"
                          : "text-muted hover:text-foreground hover:bg-white/5"
                      }`}
                    >
                      <Icon size={22} />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </nav>
  );
}
