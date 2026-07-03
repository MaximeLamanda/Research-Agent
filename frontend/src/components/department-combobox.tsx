"use client";

import {
  Combobox,
  ComboboxChip,
  ComboboxChips,
  ComboboxChipsInput,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxValue,
  useComboboxAnchor,
} from "@/components/ui/combobox";
import { getRegionCodesForCountry, getRegionLabel } from "@/data/regions";

interface DepartmentComboboxProps {
  country: string;
  value: string[];
  onChange: (value: string[]) => void;
}

export function DepartmentCombobox({ country, value, onChange }: DepartmentComboboxProps) {
  const anchor = useComboboxAnchor();
  const regionCodes = getRegionCodesForCountry(country);
  const emptyLabel = country === "DE" ? "No Land found." : "No region found.";
  const placeholder =
    country === "DE" ? "Search for a Land…" : "Search for a region…";

  return (
    <Combobox
      multiple
      items={regionCodes}
      value={value}
      onValueChange={(next) => onChange(next as string[])}
    >
      <ComboboxChips ref={anchor} className="w-full">
        <ComboboxValue>
          {value.map((code) => (
            <ComboboxChip key={code}>{getRegionLabel(code, country)}</ComboboxChip>
          ))}
        </ComboboxValue>
        <ComboboxChipsInput placeholder={placeholder} />
      </ComboboxChips>
      <ComboboxContent
        anchor={anchor}
        side="bottom"
        align="start"
        sideOffset={10}
        className="z-[200] max-h-72"
      >
        <ComboboxEmpty>{emptyLabel}</ComboboxEmpty>
        <ComboboxList>
          {(code) => (
            <ComboboxItem key={code} value={code}>
              {getRegionLabel(code, country)}
            </ComboboxItem>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
