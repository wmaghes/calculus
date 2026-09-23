import type { ComponentProps } from "react";
import { useId } from "react";
import { cn } from "@/lib/cn";

export const inputClasses =
  "h-11 w-full rounded-md border border-line-strong bg-ink-900 px-3.5 text-[15px] text-fg " +
  "placeholder:text-fg-subtle transition-[border-color,box-shadow] duration-150 " +
  "hover:border-fg-subtle/40 focus:border-accent focus:shadow-[0_0_0_3px_var(--color-accent-soft)] focus:outline-none " +
  "aria-invalid:border-danger";

type FieldProps = ComponentProps<"input"> & { label: string; hint?: string; error?: string };

export function Field({ label, hint, error, className, id, ...props }: FieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const noteId = `${inputId}-note`;
  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={inputId} className="block text-[13px] font-medium text-fg-muted">
        {label}
      </label>
      <input
        id={inputId}
        className={inputClasses}
        aria-invalid={error ? true : undefined}
        aria-describedby={error || hint ? noteId : undefined}
        {...props}
      />
      {(error || hint) && (
        <p id={noteId} className={cn("text-[13px]", error ? "text-danger" : "text-fg-subtle")}>
          {error ?? hint}
        </p>
      )}
    </div>
  );
}
