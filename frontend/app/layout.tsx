import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Codebase QA Assistant",
  description: "A local-first assistant for understanding code repositories.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
