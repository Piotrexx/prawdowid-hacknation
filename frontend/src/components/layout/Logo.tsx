import Image from "next/image";

/** Decorative: the wordmark next to it carries the name. */
export function Logo() {
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
