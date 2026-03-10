import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Ubunifu Madness — AI-Powered March Madness Predictions";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          background: "linear-gradient(135deg, #0a0a0f 0%, #111827 50%, #0a0a0f 100%)",
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "system-ui, sans-serif",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Accent glow */}
        <div
          style={{
            position: "absolute",
            top: -100,
            left: "50%",
            transform: "translateX(-50%)",
            width: 600,
            height: 600,
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(249,115,22,0.15) 0%, transparent 70%)",
          }}
        />

        {/* Title */}
        <div
          style={{
            display: "flex",
            fontSize: 72,
            fontWeight: 800,
            letterSpacing: "-0.02em",
            marginBottom: 16,
          }}
        >
          <span style={{ color: "#f5f5f5" }}>Ubunifu </span>
          <span style={{ color: "#f97316", marginLeft: 16 }}>Madness</span>
        </div>

        {/* Subtitle */}
        <div
          style={{
            fontSize: 28,
            color: "#9ca3af",
            marginBottom: 48,
            textAlign: "center",
            maxWidth: 800,
          }}
        >
          AI-Powered March Madness Predictions
        </div>

        {/* Stats row */}
        <div
          style={{
            display: "flex",
            gap: 64,
          }}
        >
          {[
            { value: "6", label: "Prediction Signals" },
            { value: "0.14", label: "Brier Score" },
            { value: "31", label: "ML Features" },
            { value: "700+", label: "Teams Tracked" },
          ].map((stat) => (
            <div
              key={stat.label}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
              }}
            >
              <div style={{ fontSize: 42, fontWeight: 700, color: "#f97316" }}>
                {stat.value}
              </div>
              <div style={{ fontSize: 16, color: "#6b7280", marginTop: 4 }}>
                {stat.label}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div
          style={{
            position: "absolute",
            bottom: 32,
            fontSize: 18,
            color: "#4b5563",
          }}
        >
          madness.ubunifutech.com
        </div>
      </div>
    ),
    { ...size }
  );
}
