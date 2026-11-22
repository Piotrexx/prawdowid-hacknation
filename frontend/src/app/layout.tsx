import type { Metadata, Viewport } from "next";
import { Suspense, type ReactNode } from "react";

interface LayoutProps {
  children: ReactNode;
}
import { Open_Sans } from "next/font/google";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { PrivacyConsentDialog } from "@/components/privacy/PrivacyConsentDialog";
import { Toaster } from "@/components/ui/Toaster";
import { APPLY_SETTINGS_SCRIPT } from "@/lib/a11ySettings";
import { I18nProvider } from "@/i18n/provider";
import { SIDEBAR_SCRIPT } from "@/lib/sidebarScript";
import "./globals.css";

const openSans = Open_Sans({
  subsets: ["latin", "latin-ext"],
  variable: "--font-open-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Prawdowid – sprawdź informację w źródłach",
    template: "%s – Prawdowid",
  },
  description:
    "Wklej wiadomość, link albo zdjęcie. Prawdowid pokaże, co mówią o tym opisane źródła. Prototyp hackathonowy, nie jest oficjalną usługą.",
  icons: {
    icon: [{ url: "/logo-avatar.svg", type: "image/svg+xml" }],
    apple: "/logo-avatar.png",
  },
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  colorScheme: "light",
  themeColor: "#ffffff",
};

export default function RootLayout({ children }: LayoutProps) {
  return (
    // The pre-paint script sets data attributes for the accessibility settings.
    <html lang="pl" className={openSans.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: APPLY_SETTINGS_SCRIPT + SIDEBAR_SCRIPT }} />
      </head>
      <body className="min-h-dvh bg-surface antialiased">
        <a href="#tresc" className="skip-link">
          Przejdź do treści
        </a>
        <I18nProvider>
          <div className="flex min-h-dvh flex-col bg-surface lg:flex-row">
            <AppSidebar />
            <main id="tresc" tabIndex={-1} className="flex min-w-0 flex-1 flex-col">
              {children}
            </main>
          </div>
          <Suspense fallback={null}>
            <PrivacyConsentDialog />
          </Suspense>
          <Toaster />
        </I18nProvider>
      </body>
    </html>
  );
}
