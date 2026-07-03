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
import { getRegionLabel } from "@/data/regions";
import { getSearchAnchors } from "@/lib/api";
import {
  cityChipLabel,
  cityOptionId,
  optionIdsToRegionCities,
  parseCityOptionId,
  regionCitiesToOptionIds,
} from "@/lib/region-cities";
import { useEffect, useMemo, useState } from "react";

interface CityOption {
  id: string;
  label: string;
}

interface RegionCitiesComboboxProps {
  country: string;
  selectedRegionCodes: string[];
  value: Record<string, string[]>;
  onChange: (value: Record<string, string[]>) => void;
}

export function RegionCitiesCombobox({
  country,
  selectedRegionCodes,
  value,
  onChange,
}: RegionCitiesComboboxProps) {
  const anchor = useComboboxAnchor();
  const [suggestedOptions, setSuggestedOptions] = useState<CityOption[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (selectedRegionCodes.length === 0) {
      setSuggestedOptions([]);
      return;
    }

    let cancelled = false;
    setLoading(true);
    getSearchAnchors(country, selectedRegionCodes)
      .then((anchors) => {
        if (cancelled) {
          return;
        }
        const options: CityOption[] = [];
        for (const code of selectedRegionCodes) {
          const anchor = anchors[code];
          for (const city of anchor?.cities ?? []) {
            options.push({
              id: cityOptionId(code, city),
              label: cityChipLabel(code, city, country, getRegionLabel),
            });
          }
        }
        setSuggestedOptions(options);
      })
      .catch(() => {
        if (!cancelled) {
          setSuggestedOptions([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [country, selectedRegionCodes]);

  const selectedIds = useMemo(() => regionCitiesToOptionIds(value), [value]);

  const allOptions = useMemo(() => {
    const byId = new Map(suggestedOptions.map((o) => [o.id, o]));
    for (const id of selectedIds) {
      if (byId.has(id)) {
        continue;
      }
      const parsed = parseCityOptionId(id);
      if (!parsed) {
        continue;
      }
      byId.set(id, {
        id,
        label: cityChipLabel(parsed.regionCode, parsed.city, country, getRegionLabel),
      });
    }
    return [...byId.values()].sort((a, b) => a.label.localeCompare(b.label));
  }, [suggestedOptions, selectedIds, country]);

  if (selectedRegionCodes.length === 0) {
    return null;
  }

  const emptyLabel = country === "DE" ? "Keine Stadt gefunden." : "Aucune ville trouvée.";
  const placeholder =
    country === "DE" ? "Stadt suchen (optional)…" : "Rechercher une ville (optionnel)…";

  return (
    <Combobox
      multiple
      items={allOptions.map((o) => o.id)}
      value={selectedIds}
      onValueChange={(next) => {
        onChange(optionIdsToRegionCities(next as string[]));
      }}
    >
      <ComboboxChips ref={anchor} className="w-full">
        <ComboboxValue>
          {selectedIds.map((id) => {
            const parsed = parseCityOptionId(id);
            if (!parsed) {
              return null;
            }
            return (
              <ComboboxChip key={id}>
                {cityChipLabel(parsed.regionCode, parsed.city, country, getRegionLabel)}
              </ComboboxChip>
            );
          })}
        </ComboboxValue>
        <ComboboxChipsInput placeholder={loading ? "…" : placeholder} />
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
          {(id) => {
            const option = allOptions.find((o) => o.id === id);
            return (
              <ComboboxItem key={id} value={id}>
                {option?.label ?? id}
              </ComboboxItem>
            );
          }}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
