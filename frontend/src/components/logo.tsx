import Image from "next/image";

/** The Pippit logo mark, used everywhere a brand icon is shown. */
export function Logo({
  size = 36,
  className = "",
  priority = false,
}: {
  size?: number;
  className?: string;
  priority?: boolean;
}) {
  return (
    <Image
      src="/pippit-logo.png"
      alt="Pippit"
      width={size}
      height={size}
      priority={priority}
      className={`shrink-0 rounded-xl ${className}`}
      style={{ width: size, height: size }}
    />
  );
}
