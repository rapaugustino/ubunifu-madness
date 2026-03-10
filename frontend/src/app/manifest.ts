import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Ubunifu Madness",
    short_name: "Madness",
    description: "AI-Powered March Madness Predictions",
    start_url: "/",
    display: "standalone",
    background_color: "#0a0a0f",
    theme_color: "#f97316",
  };
}
