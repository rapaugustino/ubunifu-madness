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
  Award,
  BookOpen,
  Target,
  Menu,
  X,
  ChevronDown,
} from "lucide-react";
import { useGender } from "@/hooks/useGender";

// Primary items always visible in desktop nav
const primaryNav = [
  { href: "/scores", label: "Scores", icon: Radio },
  { href: "/dashboard", label: "Rankings", icon: BarChart3 },
  { href: "/bracket", label: "Bracket", icon: LayoutDashboard },
  { href: "/chat", label: "Agent", icon: MessageSquare },
];

// Secondary items in "More" dropdown on desktop
const moreNav = [
  { href: "/teams", label: "Teams", icon: Users },
  { href: "/players", label: "Players", icon: Award },
  { href: "/compare", label: "Compare", icon: GitCompareArrows },
  { href: "/performance", label: "Performance", icon: Target },
  { href: "/about", label: "How It Works", icon: BookOpen },
];

// Mobile groups (keep full structure)
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
      { href: "/players", label: "Players", icon: Award },
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

export default function Nav() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [gender, setGender] = useGender();
  const menuRef = useRef<HTMLDivElement>(null);
  const moreRef = useRef<HTMLDivElement>(null);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileOpen(false);
    setMoreOpen(false);
  }, [pathname]);

  // Close when clicking outside
  useEffect(() => {
    if (!mobileOpen && !moreOpen) return;

    function handleClick(e: MouseEvent) {
      if (mobileOpen && menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMobileOpen(false);
      }
      if (moreOpen && moreRef.current && !moreRef.current.contains(e.target as Node)) {
        setMoreOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [mobileOpen, moreOpen]);

  // Prevent body scroll while mobile menu is open
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  const isMoreActive = moreNav.some((item) => pathname === item.href);

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 glass" ref={menuRef}>
      <div className="max-w-[90rem] mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-14">
          {/* ---- Logo ---- */}
          <Link href="/" className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center font-bold text-xs text-white">
              UM
            </div>
            <span className="font-bold text-sm hidden sm:block">
              Ubunifu <span className="text-accent">Madness</span>
            </span>
          </Link>

          {/* ---- Desktop nav (lg+) ---- */}
          <div className="hidden lg:flex items-center gap-0.5">
            {primaryNav.map((item) => {
              const isActive = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-accent/15 text-accent"
                      : "text-muted hover:text-foreground hover:bg-white/5"
                  }`}
                >
                  <Icon size={14} />
                  <span>{item.label}</span>
                </Link>
              );
            })}

            {/* More dropdown */}
            <div className="relative" ref={moreRef}>
              <button
                onClick={() => setMoreOpen(!moreOpen)}
                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  isMoreActive
                    ? "bg-accent/15 text-accent"
                    : "text-muted hover:text-foreground hover:bg-white/5"
                }`}
              >
                More
                <ChevronDown size={12} className={`transition-transform ${moreOpen ? "rotate-180" : ""}`} />
              </button>
              {moreOpen && (
                <div className="absolute top-full mt-1 right-0 bg-card border border-card-border rounded-lg shadow-xl z-50 min-w-[180px] py-1">
                  {moreNav.map((item) => {
                    const isActive = pathname === item.href;
                    const Icon = item.icon;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={() => setMoreOpen(false)}
                        className={`flex items-center gap-2.5 px-3 py-2 text-sm transition-colors ${
                          isActive
                            ? "text-accent bg-accent/10"
                            : "text-muted hover:text-foreground hover:bg-white/5"
                        }`}
                      >
                        <Icon size={14} />
                        <span>{item.label}</span>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* ---- Right side: Gender toggle + hamburger ---- */}
          <div className="flex items-center gap-2">
            <div className="flex gap-0.5 bg-card border border-card-border rounded-lg p-0.5">
              {(["M", "W"] as const).map((g) => (
                <button
                  key={g}
                  onClick={() => setGender(g)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                    gender === g ? "bg-accent text-white" : "text-muted hover:text-foreground"
                  }`}
                >
                  {g === "M" ? "Men" : "Women"}
                </button>
              ))}
            </div>

            {/* ---- Hamburger button (mobile only) ---- */}
            <button
              type="button"
              aria-label={mobileOpen ? "Close menu" : "Open menu"}
              onClick={() => setMobileOpen((prev) => !prev)}
              className="lg:hidden flex items-center justify-center w-9 h-9 rounded-lg text-muted hover:text-foreground hover:bg-white/5 transition-colors"
            >
              {mobileOpen ? <X size={22} /> : <Menu size={22} />}
            </button>
          </div>
        </div>
      </div>

      {/* ---- Mobile dropdown panel ---- */}
      <div
        className={`lg:hidden overflow-hidden transition-all duration-300 ease-in-out ${
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
