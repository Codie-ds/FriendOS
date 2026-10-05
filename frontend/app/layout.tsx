import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FriendOS — Adaptive Learning Companion",
  description:
    "FriendOS is an AI-powered learning companion that adapts to how you learn, not just what you say.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
