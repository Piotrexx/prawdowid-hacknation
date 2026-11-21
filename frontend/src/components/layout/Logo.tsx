import Image from "next/image";

interface LogoProps {
  /** Set on the blue gov bar, where the mark has to read against the accent colour. */
  onAccent?: boolean;
}

/** Decorative: the wordmark next to it carries the name. */
export function Logo({ onAccent = false }: LogoProps) {
  if (onAccent) {
    return <Image src="/logo-dark.svg" alt="" width={36} height={36} className="size-9" />;
  }
  return (
    <>
      <Image src="/logo.svg" alt="" width={36} height={36} className="size-9 dark:hidden" />
      <Image
        src="/logo-dark.svg"
        alt=""
        width={36}
        height={36}
        className="hidden size-9 dark:block"
      />
    </>
  );
}
