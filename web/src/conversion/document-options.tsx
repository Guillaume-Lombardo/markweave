import type { DocumentOptions } from "../api/generated/types.gen";

const BOOLEAN_OPTIONS = [
  ["toc", "Table of contents"],
  ["number_sections", "Number sections"],
] as const;

export function appendDocumentOptions(
  form: FormData,
  options: DocumentOptions | undefined,
): void {
  for (const [key, value] of Object.entries(options ?? {})) {
    if (value != null) form.append(key, String(value));
  }
}

function optionalBoolean(
  value: FormDataEntryValue | null,
): boolean | undefined {
  if (value === "true") return true;
  if (value === "false") return false;
  return undefined;
}

export function readDocumentOptions(form: FormData): DocumentOptions {
  const depth = form.get("toc_depth");
  return {
    toc: optionalBoolean(form.get("toc")),
    toc_depth: depth ? Number(depth) : undefined,
    number_sections: optionalBoolean(form.get("number_sections")),
  };
}

export function DocumentOptionFields({
  options,
  disabled,
  inheritLabel,
  onChange,
}: {
  options?: DocumentOptions;
  disabled: boolean;
  inheritLabel: string;
  onChange?: (options: DocumentOptions) => void;
}) {
  const selection = (value: boolean | number | null | undefined) =>
    onChange
      ? { value: value == null ? "" : String(value) }
      : { defaultValue: value == null ? "" : String(value) };
  return (
    <fieldset className="grid gap-2" disabled={disabled}>
      <legend className="font-semibold">Document structure</legend>
      {BOOLEAN_OPTIONS.map(([name, label]) => (
        <label className="grid gap-1" key={name}>
          {label}
          <select
            name={name}
            {...selection(options?.[name])}
            onChange={(event) =>
              onChange?.({
                ...options,
                [name]: optionalBoolean(event.target.value),
              })
            }
          >
            <option value="">{inheritLabel}</option>
            <option value="true">On</option>
            <option value="false">Off</option>
          </select>
        </label>
      ))}
      <label className="grid gap-1">
        Table of contents depth
        <select
          name="toc_depth"
          {...selection(options?.toc_depth)}
          onChange={(event) =>
            onChange?.({
              ...options,
              toc_depth: event.target.value
                ? Number(event.target.value)
                : undefined,
            })
          }
        >
          <option value="">{inheritLabel}</option>
          {[1, 2, 3, 4, 5, 6].map((depth) => (
            <option key={depth} value={depth}>
              {depth}
            </option>
          ))}
        </select>
      </label>
    </fieldset>
  );
}
