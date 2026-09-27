/**
 * UI primitives.
 *
 * Deliberately small and unopinionated: the storefront needs a button, a badge,
 * a skeleton, a sheet and a few form controls, and it needs them to look like
 * one system. These are local components rather than a component library so
 * the radii, borders and focus rings stay consistent with globals.css and are
 * not fighting a third party's defaults.
 */

import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Button
// ---------------------------------------------------------------------------
const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2 whitespace-nowrap",
    "font-semibold transition-colors duration-150",
    "disabled:pointer-events-none disabled:opacity-50",
    "[&_svg]:pointer-events-none [&_svg]:shrink-0",
  ],
  {
    variants: {
      variant: {
        // The primary action is safety amber on ink: the colour a safety
        // officer already associates with "act on this".
        primary:
          "bg-signal-400 text-ink-950 hover:bg-signal-300 active:bg-signal-500 border border-ink-950",
        ink: "bg-ink-950 text-white hover:bg-ink-800 border border-ink-950",
        outline:
          "bg-white text-ink-900 border border-ink-300 hover:border-ink-900 hover:bg-ink-50",
        quiet: "bg-transparent text-ink-700 hover:bg-ink-100 hover:text-ink-900",
        danger: "bg-danger-500 text-white hover:bg-danger-600 border border-danger-500",
        onDark: "bg-white/10 text-white border border-white/25 hover:bg-white/20",
      },
      size: {
        sm: "h-9 px-3 text-[13px] [&_svg]:size-4",
        md: "h-11 px-5 text-sm [&_svg]:size-[18px]",
        lg: "h-12 px-6 text-[15px] [&_svg]:size-5",
        icon: "size-10 [&_svg]:size-[18px]",
      },
      block: { true: "w-full", false: "" },
    },
    defaultVariants: { variant: "primary", size: "md", block: false },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /**
   * Render the styling on its single child element instead of a `<button>`.
   *
   * Needed whenever the control is really a link - a retry action pointing at
   * the same route, for example. The alternative is a wrapper `<div>` with the
   * button's class names, which puts a `<div>` in the interactive position and
   * loses the button semantics entirely. Radix `Slot` merges the props onto the
   * child, so `href`, keyboard behaviour and the reset link in global CSS all
   * keep working.
   */
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, size, block, type = "button", asChild = false, ...props },
  ref,
) {
  const Component = asChild ? Slot : "button";
  return (
    <Component
      ref={ref}
      {...(asChild ? {} : { type })}
      className={cn(buttonVariants({ variant, size, block }), className)}
      {...props}
    />
  );
});

export { buttonVariants };

// ---------------------------------------------------------------------------
// Badge
// ---------------------------------------------------------------------------
const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-xs font-semibold uppercase tracking-[0.08em]",
  {
    variants: {
      tone: {
        neutral: "bg-ink-100 text-ink-700",
        ink: "bg-ink-900 text-white",
        ok: "bg-safe-100 text-safe-700",
        warn: "bg-signal-100 text-signal-800",
        danger: "bg-danger-100 text-danger-700",
        info: "bg-info-100 text-info-600",
        sale: "bg-danger-500 text-white",
        outline: "border border-ink-300 text-ink-700",
      },
      size: {
        sm: "px-1.5 py-0.5 text-[10px]",
        md: "px-2 py-1 text-[11px]",
      },
    },
    defaultVariants: { tone: "neutral", size: "sm" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, size, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone, size }), className)} {...props} />;
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------
/**
 * A pulsing block. Used everywhere data is loading, because a skeleton that
 * matches the final layout is what stops the page jumping when it lands.
 */
export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn("animate-pulse rounded-xs bg-ink-200/70", className)}
      {...props}
    />
  );
}

// ---------------------------------------------------------------------------
// Container / Section
// ---------------------------------------------------------------------------
export function Container({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("container-page", className)} {...props} />;
}

export function Section({
  className,
  ...props
}: React.HTMLAttributes<HTMLElement>) {
  return <section className={cn("py-14 sm:py-20", className)} {...props} />;
}

/** Small uppercase label above a heading. */
export function Eyebrow({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("eyebrow", className)} {...props} />;
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  action,
  className,
}: {
  eyebrow?: string;
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "mb-8 flex flex-col gap-3 sm:mb-10 sm:flex-row sm:items-end sm:justify-between",
        className,
      )}
    >
      <div className="max-w-2xl">
        {eyebrow ? <Eyebrow className="mb-2">{eyebrow}</Eyebrow> : null}
        <h2 className="text-2xl sm:text-3xl">{title}</h2>
        {description ? (
          <p className="mt-2 text-[15px] leading-relaxed text-ink-600">{description}</p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Field
// ---------------------------------------------------------------------------
export function Label({
  className,
  ...props
}: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={cn(
        "block text-[13px] font-semibold text-ink-800",
        className,
      )}
      {...props}
    />
  );
}

export const inputClassName = cn(
  "h-11 w-full rounded-xs border border-ink-300 bg-white px-3 text-sm text-ink-900",
  "placeholder:text-ink-400",
  "focus:border-ink-900 focus:outline-none focus-visible:outline-2 focus-visible:outline-ink-900",
  "disabled:cursor-not-allowed disabled:bg-ink-50 disabled:text-ink-500",
  "aria-[invalid=true]:border-danger-500",
);

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(function Input({ className, type = "text", ...props }, ref) {
  return (
    <input ref={ref} type={type} className={cn(inputClassName, className)} {...props} />
  );
});

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, rows = 4, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      className={cn(inputClassName, "h-auto py-2.5 leading-relaxed", className)}
      {...props}
    />
  );
});

export const Select = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(function Select({ className, children, ...props }, ref) {
  return (
    <div className="relative">
      <select
        ref={ref}
        className={cn(inputClassName, "appearance-none pr-9", className)}
        {...props}
      >
        {children}
      </select>
      <svg
        aria-hidden="true"
        viewBox="0 0 20 20"
        className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-ink-500"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
      >
        <path d="M5 7.5 10 12.5 15 7.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
});

export function Checkbox({
  label,
  description,
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & {
  label: React.ReactNode;
  description?: React.ReactNode;
}) {
  return (
    <label
      className={cn(
        "group flex cursor-pointer items-start gap-2.5 text-sm",
        props.disabled && "cursor-not-allowed opacity-60",
        className,
      )}
    >
      <input
        type="checkbox"
        className="mt-0.5 size-4 shrink-0 cursor-pointer appearance-none rounded-xs border border-ink-400 bg-white checked:border-ink-950 checked:bg-ink-950 focus-visible:outline-2 focus-visible:outline-ink-900 focus-visible:outline-offset-2 checked:bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 20 20%22 fill=%22none%22 stroke=%22white%22 stroke-width=%223%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22><path d=%22M4 10.5l4 4 8-9%22/></svg>')] checked:bg-[length:14px_14px] checked:bg-center checked:bg-no-repeat"
        {...props}
      />
      <span className="min-w-0">
        <span className="block leading-5 text-ink-800">{label}</span>
        {description ? (
          <span className="mt-0.5 block text-xs leading-4 text-ink-500">{description}</span>
        ) : null}
      </span>
    </label>
  );
}

// ---------------------------------------------------------------------------
// Empty / error states
// ---------------------------------------------------------------------------
/**
 * The one place a route's "nothing to show" state is rendered, so every route
 * phrases it the same way. A blank screen is never an acceptable empty state.
 */
export function EmptyState({
  title,
  description,
  action,
  icon,
  className,
}: {
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-md border border-dashed border-ink-300 bg-ink-50/60 px-6 py-16 text-center",
        className,
      )}
    >
      {icon ? <div className="mb-4 text-ink-400">{icon}</div> : null}
      <p className="text-lg font-semibold text-ink-900">{title}</p>
      {description ? (
        <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-600">{description}</p>
      ) : null}
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  title = "We couldn't load this",
  description = "Something went wrong on our side. Please try again.",
  onRetry,
  className,
}: {
  title?: string;
  description?: React.ReactNode;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center rounded-md border border-danger-100 bg-danger-50 px-6 py-14 text-center",
        className,
      )}
    >
      <p className="text-lg font-semibold text-danger-700">{title}</p>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-danger-700/80">
        {description}
      </p>
      {onRetry ? (
        <Button variant="outline" className="mt-6" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}
