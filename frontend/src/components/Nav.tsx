"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Trophy, BarChart3, GitCompareArrows, MessageSquare, LayoutDashboard, Radio, Users } from "lucide-react";

const navItems = [
  { href: "/", label: "Home", icon: Trophy },
  { href: "/scores", label: "Scores", icon: Radio },
  { href: "/bracket", label: "Bracket", icon: LayoutDashboard },
  { href: "/dashboard", label: "Rankings", icon: BarChart3 },
  { href: "/teams", label: "Teams", icon: Users },
  { href: "/compare", label: "Compare", icon: GitCompareArrows },
  { href: "/chat", label: "Madness Agent", icon: MessageSquare },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 glass">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-16">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center font-bold text-sm text-white">
              UM
            </div>
            <span className="font-bold text-lg hidden sm:block">
              Ubunifu <span className="text-accent">Madness</span>
            </span>
          </Link>

          <div className="flex items-center gap-1">
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
                  <span className="hidden md:inline">{item.label}</span>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
}
