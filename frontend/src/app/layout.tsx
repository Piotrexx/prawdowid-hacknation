import type { Metadata, Viewport } from "next";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { SiteHeader } from "@/components/layout/SiteHeader";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Prawdowid – sprawdź informację w źródłach",
    template: "%s – Prawdowid",
  },
  description:
    "Wklej wiadomość, link albo zrzut ekranu. Prawdowid pokaże, co mówią o tym opisane źródła. Prototyp hackathonowy, nie jest oficjalną usługą.",
  icons: {
    icon: [{ url: "/logo-avatar.svg", type: "image/svg+xml" }],
    apple: "/logo-avatar.png",
  },
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#171d25" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pl">
      <body className="flex min-h-dvh flex-col antialiased">
        <a href="#tresc" className="skip-link">
          Przejdź do treści
        </a>
        <SiteHeader />
        <main id="tresc" tabIndex={-1} className="flex-1">
          {children}
        </main>
        <SiteFooter />
      </body>
    </html>
  );
}
