import Image from "next/image";
import { cn } from "@/lib/cn";

type ProductImageProps = {
  src: string;
  alt: string;
  className?: string;
  sizes?: string;
  priority?: boolean;
};

/** Local SVGs use native img (stable CLS); raster uses next/image. */
export function ProductImage({
  src,
  alt,
  className,
  sizes = "33vw",
  priority,
}: ProductImageProps) {
  const isSvg = src.endsWith(".svg");

  if (isSvg) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt={alt}
        className={cn("h-full w-full object-cover", className)}
        loading={priority ? "eager" : "lazy"}
      />
    );
  }

  return (
    <Image
      src={src}
      alt={alt}
      fill
      sizes={sizes}
      className={cn("object-cover", className)}
      priority={priority}
    />
  );
}
