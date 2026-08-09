import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Refactor Workflow Studio",
  description: "Local-first visual workflow composition for coding and agent reactions.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
