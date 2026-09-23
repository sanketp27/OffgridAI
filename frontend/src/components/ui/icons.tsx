import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function base({ size = 20, ...props }: IconProps) {
  return { width: size, height: size, viewBox: "0 0 24 24", fill: "none", ...props };
}

export function IconSearch(props: IconProps) {
  return (
    <svg {...base(props)} aria-hidden>
      <circle cx="11" cy="11" r="6.25" stroke="currentColor" strokeWidth="1.6" />
      <path d="M16.5 16.5 20 20" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function IconCamera(props: IconProps) {
  return (
    <svg {...base(props)} aria-hidden>
      <path
        d="M4 8.5A2.5 2.5 0 0 1 6.5 6h1.1c.4 0 .8-.2 1-.5l.6-.9A1.5 1.5 0 0 1 10.5 4h3c.5 0 1 .2 1.3.6l.6.9c.2.3.6.5 1 .5h1.1A2.5 2.5 0 0 1 20 8.5v8A2.5 2.5 0 0 1 17.5 19h-11A2.5 2.5 0 0 1 4 16.5v-8Z"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <circle cx="12" cy="12.5" r="3.1" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

export function IconBag(props: IconProps) {
  return (
    <svg {...base(props)} aria-hidden>
      <path
        d="M6.5 8h11l-.8 10.2a1.5 1.5 0 0 1-1.5 1.3H8.8a1.5 1.5 0 0 1-1.5-1.3L6.5 8Z"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path
        d="M9 8V6.8A3 3 0 0 1 12 3.8 3 3 0 0 1 15 6.8V8"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function IconRisk(props: IconProps) {
  return (
    <svg {...base(props)} aria-hidden>
      <path
        d="M12 4.5 20 19H4L12 4.5Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M12 10v4.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="12" cy="16.8" r="0.9" fill="currentColor" />
    </svg>
  );
}
