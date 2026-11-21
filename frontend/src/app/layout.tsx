import type { Metadata, Viewport } from "next";
import { Open_Sans } from "next/font/google";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { DISPLAY_BOOT_SCRIPT } from "@/lib/theme";
import "./globals.css";

// gov.pl sets its whole interface in Open Sans; latin-ext carries the Polish diacritics.
const openSans = Open_Sans({
  subsets: ["latin", "latin-ext"],
  weight: ["400", "600", "700"],
  display: "swap",
  variable: "--font-open-sans",
});

export const metadata: Metadata = {
  title: {
    default: "Prawdowid – sprawdź informację w źródłach",
    template: "%s – Prawdowid",
  },
  description:
    "Wklej wiadomość, link albo zrzut ekranu. Prawdowid pokaże, co mówią o tym opisane źródła. Prototyp hackathonowy, nie jest oficjalną usługą.",
  icons: {
    icon: [
      { url: "/logo-avatar.svg", type: "image/svg+xml" },
      { url: "/favicon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: "/logo-avatar-192.png",
  },
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#0052a5" },
    { media: "(prefers-color-scheme: dark)", color: "#15191d" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pl" className={openSans.variable} suppressHydrationWarning>
      <head>
        {/* Applies the stored theme before first paint, so the page never flashes
            the wrong one. Inline by necessity: an external file would load too late. */}
        <script dangerouslySetInnerHTML={{ __html: DISPLAY_BOOT_SCRIPT }} />
      </head>
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
