"use client";

/**
 * Bulk quote form.
 *
 * The `quote_requests` table and statuses exist (NEW, CONTACTED, QUOTED,
 * CONVERTED, CLOSED) but the API is a later build phase, so this form renders
 * and validates locally and then states plainly that the request was not sent.
 * It does not pretend to have submitted, and it does not show a success state
 * for something that did not happen - that is the failure mode that erodes trust
 * fastest in a B2B form where the customer is waiting on a reply.
 */

import { Check, Send } from "lucide-react";
import { useMemo, useState } from "react";

import { Button, Input, Label, Select, Textarea } from "@/components/ui";
import { cn } from "@/lib/cn";

interface Line {
  key: number;
  product: string;
  size: string;
  material: string;
  quantity: string;
}

const SIZES = ["8x12", "12x18", "18x24", "24x36", "30x60", "36x48", "36x72", "48x72", "48x96"];
const MATERIALS = [
  "3MM ACP",
  "5MM FOAMSHEET",
  "ACP",
  "AUTOGLOW STICKER",
  "ECO VINYL STICKER",
];

let nextKey = 1;
const blankLine = (): Line => ({
  key: nextKey++,
  product: "",
  size: "",
  material: "",
  quantity: "1",
});

export function BulkOrderForm({ productSlug }: { productSlug?: string }) {
  const [lines, setLines] = useState<Line[]>(() => {
    // Arriving from a product page pre-fills the first line with that product,
    // so the buyer does not retype what the link already told us.
    const first = blankLine();
    if (productSlug) first.product = productSlug.replace(/-/g, " ");
    return [first];
  });
  const [contact, setContact] = useState({
    name: "",
    email: "",
    phone: "",
    company: "",
    gstin: "",
    notes: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);

  const totals = useMemo(() => {
    const units = lines.reduce((sum, line) => {
      const quantity = Number.parseInt(line.quantity, 10);
      return sum + (Number.isFinite(quantity) && quantity > 0 ? quantity : 0);
    }, 0);
    return { lines: lines.filter((line) => line.product.trim()).length, units };
  }, [lines]);

  function update(key: number, patch: Partial<Line>) {
    setLines((current) =>
      current.map((line) => (line.key === key ? { ...line, ...patch } : line)),
    );
  }

  function validate(): boolean {
    const next: Record<string, string> = {};
    if (!contact.name.trim()) next.name = "Please tell us who to reply to.";
    if (!contact.email.trim() && !contact.phone.trim()) {
      next.email = "An email address or a phone number is required.";
    } else if (contact.email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(contact.email.trim())) {
      next.email = "That email address does not look right.";
    }
    if (contact.phone.trim() && contact.phone.replace(/\D/g, "").length < 10) {
      next.phone = "Please include the area code.";
    }
    if (totals.lines === 0) {
      next.lines = "Add at least one board with a product name.";
    }
    for (const line of lines) {
      if (line.product.trim() && line.size && !SIZES.includes(line.size)) {
        next[`size-${line.key}`] = "Pick a listed size.";
      }
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (validate()) setSubmitted(true);
  }

  if (submitted) {
    return (
      <div
        role="status"
        className="border border-signal-400 bg-signal-50 p-6 sm:p-8"
      >
        <p className="flex items-center gap-2.5 text-[17px] font-bold text-ink-950">
          <Check aria-hidden="true" className="size-5 text-safe-600" strokeWidth={3} />
          Form validated &mdash; but not yet sent
        </p>
        <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-700">
          The quote request API is the next build phase, so this form has not submitted anything
          and no request has been stored. In the meantime, send your board list straight to us:
        </p>
        <ul className="mt-4 space-y-2 text-[14px] text-ink-800">
          <li>
            Email:{" "}
            <a href="mailto:safetyposterprint@gmail.com" className="font-semibold underline underline-offset-4">
              safetyposterprint@gmail.com
            </a>
          </li>
          <li>
            WhatsApp:{" "}
            <a href="https://wa.me/918320050573" className="font-semibold underline underline-offset-4">
              +91 83200 50573
            </a>
          </li>
        </ul>
        <details className="mt-6">
          <summary className="cursor-pointer text-[13px] font-semibold text-ink-700">
            Show the request you built
          </summary>
          <pre className="mt-3 overflow-x-auto border border-ink-200 bg-white p-3 font-mono text-[11px] leading-relaxed text-ink-800">
            {JSON.stringify(
              { contact, lines: lines.filter((line) => line.product.trim()) },
              null,
              2,
            )}
          </pre>
        </details>
        <Button variant="outline" className="mt-6" onClick={() => setSubmitted(false)}>
          Edit the request
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-8">
      {/* --- board list --- */}
      <fieldset>
        <legend className="text-[15px] font-bold text-ink-950">
          What do you need printed?
        </legend>
        <p className="mt-1 text-[13px] text-ink-600">
          One row per board type. Add as many as you need.
        </p>

        <div className="mt-4 space-y-3">
          {lines.map((line, index) => (
            <div
              key={line.key}
              className="grid gap-3 border border-ink-200 bg-ink-50 p-3 sm:grid-cols-12"
            >
              <div className="sm:col-span-12">
                <div className="flex items-center justify-between">
                  <Label htmlFor={`product-${line.key}`}>Board {index + 1}</Label>
                  {lines.length > 1 ? (
                    <button
                      type="button"
                      onClick={() => setLines((current) => current.filter((l) => l.key !== line.key))}
                      className="text-[12px] font-semibold text-ink-600 underline underline-offset-4 hover:text-danger-600"
                    >
                      Remove
                      <span className="sr-only"> board {index + 1}</span>
                    </button>
                  ) : null}
                </div>
              </div>

              <div className="sm:col-span-12">
                <Input
                  id={`product-${line.key}`}
                  value={line.product}
                  placeholder="e.g. Danger High Voltage"
                  onChange={(event) => update(line.key, { product: event.target.value })}
                />
              </div>

              <div className="sm:col-span-4">
                <Label htmlFor={`size-${line.key}`} className="mb-1">
                  Size
                </Label>
                <Select
                  id={`size-${line.key}`}
                  value={line.size}
                  aria-invalid={Boolean(errors[`size-${line.key}`])}
                  onChange={(event) => update(line.key, { size: event.target.value })}
                >
                  <option value="">Select</option>
                  {SIZES.map((size) => (
                    <option key={size} value={size}>
                      {size} in.
                    </option>
                  ))}
                </Select>
                {errors[`size-${line.key}`] ? (
                  <p className="mt-1 text-[12px] text-danger-600">{errors[`size-${line.key}`]}</p>
                ) : null}
              </div>

              <div className="sm:col-span-5">
                <Label htmlFor={`material-${line.key}`} className="mb-1">
                  Material
                </Label>
                <Select
                  id={`material-${line.key}`}
                  value={line.material}
                  onChange={(event) => update(line.key, { material: event.target.value })}
                >
                  <option value="">Not sure / advise</option>
                  {MATERIALS.map((material) => (
                    <option key={material} value={material}>
                      {material}
                    </option>
                  ))}
                </Select>
              </div>

              <div className="sm:col-span-3">
                <Label htmlFor={`qty-${line.key}`} className="mb-1">
                  Quantity
                </Label>
                <Input
                  id={`qty-${line.key}`}
                  type="number"
                  min={1}
                  inputMode="numeric"
                  value={line.quantity}
                  onChange={(event) => update(line.key, { quantity: event.target.value })}
                />
              </div>
            </div>
          ))}
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setLines((current) => [...current, blankLine()])}
          >
            Add another board
          </Button>
          <p className="tabular text-[13px] text-ink-600">
            {totals.lines} board type{totals.lines === 1 ? "" : "s"} &middot; {totals.units} unit
            {totals.units === 1 ? "" : "s"} in total
          </p>
        </div>
        {errors.lines ? <p className="mt-2 text-[13px] text-danger-600">{errors.lines}</p> : null}
      </fieldset>

      {/* --- contact --- */}
      <fieldset className="border-t border-ink-200 pt-8">
        <legend className="text-[15px] font-bold text-ink-950">How should we reply?</legend>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Field
            id="bulk-name"
            label="Your name"
            required
            value={contact.name}
            error={errors.name}
            onChange={(value) => setContact({ ...contact, name: value })}
          />
          <Field
            id="bulk-company"
            label="Company"
            value={contact.company}
            onChange={(value) => setContact({ ...contact, company: value })}
          />
          <Field
            id="bulk-email"
            label="Email"
            type="email"
            value={contact.email}
            error={errors.email}
            onChange={(value) => setContact({ ...contact, email: value })}
          />
          <Field
            id="bulk-phone"
            label="Phone"
            type="tel"
            value={contact.phone}
            error={errors.phone}
            onChange={(value) => setContact({ ...contact, phone: value })}
          />
          <div className="sm:col-span-2">
            <Label htmlFor="bulk-gstin" className="mb-1.5">
              GSTIN{" "}
              <span className="font-normal text-ink-500">
                (optional &mdash; needed for a business invoice)
              </span>
            </Label>
            <Input
              id="bulk-gstin"
              value={contact.gstin}
              maxLength={15}
              placeholder="22AAAAA0000A1Z5"
              onChange={(event) =>
                setContact({ ...contact, gstin: event.target.value.toUpperCase() })
              }
              className="font-mono uppercase"
            />
            <p className="mt-1.5 text-[12px] text-ink-500">
              Our own GSTIN is not published yet. Send yours and we will confirm ours on the
              quotation.
            </p>
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="bulk-notes" className="mb-1.5">
              Anything else we should know?
            </Label>
            <Textarea
              id="bulk-notes"
              value={contact.notes}
              rows={4}
              placeholder="Delivery city, target date, whether you need installation, language requirements..."
              onChange={(event) => setContact({ ...contact, notes: event.target.value })}
            />
          </div>
        </div>
      </fieldset>

      <div className="flex flex-col gap-3 border-t border-ink-200 pt-6 sm:flex-row sm:items-center">
        <Button type="submit" variant="primary" size="lg">
          <Send aria-hidden="true" />
          Request quotation
        </Button>
        <p className="text-[12px] leading-relaxed text-ink-500">
          We reply with a proper quotation, freight included, rather than a per-item price that
          does not add up at volume.
        </p>
      </div>
    </form>
  );
}

function Field({
  id,
  label,
  value,
  onChange,
  error,
  type = "text",
  required,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  type?: string;
  required?: boolean;
}) {
  return (
    <div>
      <Label htmlFor={id} className="mb-1.5">
        {label}
        {required ? <span className="ml-1 text-danger-600">*</span> : null}
      </Label>
      <Input
        id={id}
        type={type}
        value={value}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        onChange={(event) => onChange(event.target.value)}
        className={cn(error && "border-danger-500")}
      />
      {error ? (
        <p id={`${id}-error`} className="mt-1.5 text-[12px] font-medium text-danger-600">
          {error}
        </p>
      ) : null}
    </div>
  );
}
