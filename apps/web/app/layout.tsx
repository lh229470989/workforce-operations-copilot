import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AcmeWorks Operations Copilot",
  description: "A fictional, role-aware workforce copilot demonstration.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
