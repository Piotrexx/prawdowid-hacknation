export type SourceTier = 1 | 2 | 3;

export type SourceCategory =
  | "bezpieczenstwo"
  | "pogoda"
  | "zdrowie"
  | "prawo"
  | "dyplomacja"
  | "transport"
  | "cyber"
  | "analizy"
  | "factcheck"
  | "media";

export interface CatalogSource {
  /** Stable key used by the preview-image endpoint. */
  slug: string;
  /** Short name shown in large type on the card. */
  name: string;
  /** Official publisher, shown above the name. */
  fullName: string;
  url: string;
  tier: SourceTier;
  categories: SourceCategory[];
  description: string;
  /** Two- or three-letter mark used when no preview image is available. */
  mark: string;
}

export const SOURCE_TIER_LABELS: Record<SourceTier, string> = {
  1: "Źródło urzędowe",
  2: "Fact-check",
  3: "Media",
};

export const SOURCE_TIER_DESCRIPTIONS: Record<SourceTier, string> = {
  1: "Materiały pierwotne i komunikaty instytucji publicznych. Największa waga w ocenie dowodów.",
  2: "Niezależne redakcje sprawdzające fakty. Wspierają werdykt, ale nie zastępują źródła pierwotnego.",
  3: "Media opiniotwórcze. Dają kontekst i nigdy same nie rozstrzygają werdyktu.",
};

export const SOURCE_CATEGORY_LABELS: Record<SourceCategory, string> = {
  bezpieczenstwo: "Bezpieczeństwo",
  pogoda: "Pogoda i woda",
  zdrowie: "Zdrowie",
  prawo: "Prawo",
  dyplomacja: "Dyplomacja",
  transport: "Transport",
  cyber: "Cyberbezpieczeństwo",
  analizy: "Analizy",
  factcheck: "Fact-checking",
  media: "Media",
};

/** Display order of the category pills. */
export const SOURCE_CATEGORY_ORDER: SourceCategory[] = [
  "bezpieczenstwo",
  "pogoda",
  "zdrowie",
  "prawo",
  "dyplomacja",
  "transport",
  "cyber",
  "analizy",
  "factcheck",
  "media",
];

export const SOURCE_CATALOG: CatalogSource[] = [
  {
    slug: "rcb",
    name: "RCB",
    fullName: "Rządowe Centrum Bezpieczeństwa",
    url: "https://rcb.gov.pl",
    tier: 1,
    categories: ["bezpieczenstwo"],
    description: "Alerty i komunikaty o zagrożeniach dla ludności.",
    mark: "RCB",
  },
  {
    slug: "imgw",
    name: "IMGW",
    fullName: "Instytut Meteorologii i Gospodarki Wodnej",
    url: "https://imgw.pl",
    tier: 1,
    categories: ["pogoda"],
    description: "Prognozy oraz ostrzeżenia meteorologiczne i hydrologiczne.",
    mark: "IMGW",
  },
  {
    slug: "cert-polska",
    name: "CERT Polska",
    fullName: "Naukowa i Akademicka Sieć Komputerowa – NASK",
    url: "https://cert.pl",
    tier: 1,
    categories: ["cyber", "bezpieczenstwo"],
    description: "Zgłoszenia incydentów i ostrzeżenia o zagrożeniach w sieci.",
    mark: "CERT",
  },
  {
    slug: "msz",
    name: "MSZ",
    fullName: "Ministerstwo Spraw Zagranicznych",
    url: "https://www.gov.pl/web/dyplomacja",
    tier: 1,
    categories: ["dyplomacja"],
    description: "Komunikaty i stanowiska polskiej dyplomacji.",
    mark: "MSZ",
  },
  {
    slug: "policja",
    name: "Policja",
    fullName: "Komenda Główna Policji",
    url: "https://policja.pl",
    tier: 1,
    categories: ["bezpieczenstwo", "prawo"],
    description: "Komunikaty policyjne i informacje o bezpieczeństwie publicznym.",
    mark: "PL",
  },
  {
    slug: "gis",
    name: "GIS",
    fullName: "Główny Inspektorat Sanitarny",
    url: "https://www.gov.pl/web/gis",
    tier: 1,
    categories: ["zdrowie", "bezpieczenstwo"],
    description: "Komunikaty sanitarne i informacje o zagrożeniach zdrowotnych.",
    mark: "GIS",
  },
  {
    slug: "paa",
    name: "PAA",
    fullName: "Państwowa Agencja Atomistyki",
    url: "https://www.gov.pl/web/paa",
    tier: 1,
    categories: ["bezpieczenstwo", "zdrowie"],
    description: "Informacje o bezpieczeństwie jądrowym i radiacyjnym.",
    mark: "PAA",
  },
  {
    slug: "gddkia",
    name: "GDDKiA",
    fullName: "Generalna Dyrekcja Dróg Krajowych i Autostrad",
    url: "https://www.gov.pl/web/gddkia",
    tier: 1,
    categories: ["transport"],
    description: "Stan dróg, utrudnienia i komunikaty drogowe.",
    mark: "GDD",
  },
  {
    slug: "kgpsp",
    name: "KG PSP",
    fullName: "Komenda Główna Państwowej Straży Pożarnej",
    url: "https://www.gov.pl/web/kgpsp",
    tier: 1,
    categories: ["bezpieczenstwo"],
    description: "Komunikaty strażackie i ostrzeżenia o zagrożeniach.",
    mark: "PSP",
  },
  {
    slug: "sejm-eli",
    name: "Sejm ELI",
    fullName: "Sejm Rzeczypospolitej Polskiej",
    url: "https://isap.sejm.gov.pl",
    tier: 1,
    categories: ["prawo"],
    description: "Teksty aktów prawnych z Systemu Informacji Prawnej.",
    mark: "ELI",
  },
  {
    slug: "osw",
    name: "OSW",
    fullName: "Ośrodek Studiów Wschodnich",
    url: "https://www.osw.waw.pl",
    tier: 1,
    categories: ["analizy", "dyplomacja"],
    description: "Analizy sytuacji międzynarodowej i bezpieczeństwa.",
    mark: "OSW",
  },
  {
    slug: "konkret24",
    name: "Konkret24",
    fullName: "Konkret24 – TVN24",
    url: "https://konkret24.tvn24.pl",
    tier: 2,
    categories: ["factcheck", "media"],
    description: "Sprawdzenia faktów i wyjaśnienia dezinformacji.",
    mark: "K24",
  },
  {
    slug: "pravda",
    name: "Pravda",
    fullName: "Pravda.org.pl",
    url: "https://pravda.org.pl",
    tier: 2,
    categories: ["factcheck"],
    description: "Fact-checking twierdzeń z przestrzeni publicznej.",
    mark: "PRA",
  },
  {
    slug: "fakenews",
    name: "FakeNews.pl",
    fullName: "FakeNews.pl",
    url: "https://fakenews.pl",
    tier: 2,
    categories: ["factcheck"],
    description: "Baza sprawdzeń i ostrzeżeń o fake newsach.",
    mark: "FN",
  },
  {
    slug: "rzeczpospolita",
    name: "Rzeczpospolita",
    fullName: "Rzeczpospolita – Gremi Media",
    url: "https://www.rp.pl",
    tier: 3,
    categories: ["media"],
    description: "Kontekst i materiały z medium opiniotwórczego.",
    mark: "RP",
  },
];

export function findCatalogSource(slug: string): CatalogSource | undefined {
  return SOURCE_CATALOG.find((source) => source.slug === slug);
}

export function sourceImagePath(slug: string): string {
  return `/api/source-image?source=${encodeURIComponent(slug)}`;
}
