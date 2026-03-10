import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://madness.ubunifutech.com";

  return [
    { url: base, lastModified: new Date(), changeFrequency: "daily", priority: 1 },
    { url: `${base}/scores`, lastModified: new Date(), changeFrequency: "hourly", priority: 0.9 },
    { url: `${base}/bracket`, lastModified: new Date(), changeFrequency: "daily", priority: 0.9 },
    { url: `${base}/dashboard`, lastModified: new Date(), changeFrequency: "daily", priority: 0.8 },
    { url: `${base}/compare`, lastModified: new Date(), changeFrequency: "daily", priority: 0.7 },
    { url: `${base}/chat`, lastModified: new Date(), changeFrequency: "weekly", priority: 0.7 },
    { url: `${base}/performance`, lastModified: new Date(), changeFrequency: "daily", priority: 0.6 },
    { url: `${base}/about`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.5 },
  ];
}
