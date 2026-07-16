"use client";

import { DatePickerWithRange } from "@/components/date-range-picker";
import { DepartmentCombobox } from "@/components/department-combobox";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { COUNTRIES } from "@/data/countries";
import { useAgentSettings } from "@/hooks/use-agent-settings";
import {
  PUBLISHED_DATE_PRESET_CUSTOM,
  PUBLISHED_DATE_PRESETS,
  type PublishedDatePreset,
} from "@/lib/published-date-presets";

const EXA_SEARCH_TYPES = [
  { value: "auto", label: "Auto" },
  { value: "neural", label: "Neural" },
  { value: "keyword", label: "Keyword" },
  { value: "fast", label: "Fast" },
] as const;

const EXA_CATEGORIES = [
  { value: "news", label: "News" },
  { value: "company", label: "Company" },
  { value: "research paper", label: "Research paper" },
  { value: "pdf", label: "PDF" },
  { value: "github", label: "GitHub" },
  { value: "tweet", label: "Tweet" },
  { value: "personal site", label: "Personal site" },
  { value: "linkedin profile", label: "LinkedIn profile" },
  { value: "financial report", label: "Financial report" },
] as const;

interface SettingsAccordionProps {
  settings: ReturnType<typeof useAgentSettings>;
}

export function SettingsAccordion({ settings }: SettingsAccordionProps) {
  const {
    country,
    setCountry,
    selected,
    setSelected,
    exaSearchType,
    setExaSearchType,
    exaCategory,
    setExaCategory,
    exaPublishedDatePreset,
    setExaPublishedDatePreset,
    exaStartPublishedDate,
    setExaStartPublishedDate,
    exaEndPublishedDate,
    setExaEndPublishedDate,
    loading,
    loadConfig,
    markDirty,
    handleSave,
  } = settings;

  return (
    <div className="w-full">
      <Accordion
        type="single"
        collapsible
        onValueChange={(v) => v && loadConfig()}
        className="rounded-xl bg-muted px-4 py-1"
      >
        <AccordionItem value="settings" className="border-b-0">
          <AccordionTrigger className="relative min-h-12 w-full justify-center px-6 py-4 text-sm font-medium hover:no-underline [&>svg]:absolute [&>svg]:right-4">
            Settings
          </AccordionTrigger>
          <AccordionContent className="overflow-visible">
            <div className="space-y-4 overflow-visible pb-2">
              <div className="space-y-2">
                <Label>Exa Search</Label>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="exa-search-type">Search Type</Label>
                    <Select
                      value={exaSearchType}
                      onValueChange={(value) => {
                        if (value) {
                          setExaSearchType(value);
                          markDirty();
                        }
                      }}
                    >
                      <SelectTrigger id="exa-search-type" className="w-full">
                        <SelectValue placeholder="Choose a type" />
                      </SelectTrigger>
                      <SelectContent side="bottom" align="start" alignItemWithTrigger={false}>
                        {EXA_SEARCH_TYPES.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="exa-category">Category</Label>
                    <Select
                      value={exaCategory}
                      onValueChange={(value) => {
                        if (value) {
                          setExaCategory(value);
                          markDirty();
                        }
                      }}
                    >
                      <SelectTrigger id="exa-category" className="w-full">
                        <SelectValue placeholder="Choose a category" />
                      </SelectTrigger>
                      <SelectContent side="bottom" align="start" alignItemWithTrigger={false}>
                        {EXA_CATEGORIES.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="exa-published-date-preset">Published date range</Label>
                  <Select
                    value={exaPublishedDatePreset}
                    onValueChange={(value) => {
                      if (value) {
                        setExaPublishedDatePreset(value as PublishedDatePreset);
                      }
                    }}
                  >
                    <SelectTrigger id="exa-published-date-preset" className="w-full">
                      <SelectValue placeholder="Choose a period" />
                    </SelectTrigger>
                    <SelectContent side="bottom" align="start" alignItemWithTrigger={false}>
                      {PUBLISHED_DATE_PRESETS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {exaPublishedDatePreset === PUBLISHED_DATE_PRESET_CUSTOM ? (
                    <DatePickerWithRange
                      id="exa-published-date-range"
                      label="Custom dates"
                      startDate={exaStartPublishedDate}
                      endDate={exaEndPublishedDate}
                      placeholder="Pick a date range"
                      onChange={({ startDate, endDate }) => {
                        setExaStartPublishedDate(startDate ?? "");
                        setExaEndPublishedDate(endDate ?? "");
                        markDirty();
                      }}
                    />
                  ) : null}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="country">Country</Label>
                  <Select
                    value={country}
                    onValueChange={(value) => {
                      if (value) {
                        setCountry(value);
                      }
                    }}
                  >
                    <SelectTrigger id="country" className="w-full">
                      <SelectValue placeholder="Choose a country" />
                    </SelectTrigger>
                    <SelectContent side="bottom" align="start" alignItemWithTrigger={false}>
                      {COUNTRIES.map((option) => (
                        <SelectItem key={option.code} value={option.code}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label>
                  {country === "DE"
                    ? "Länder"
                    : country === "GB"
                      ? "Regions"
                      : country === "IE"
                        ? "Provinces"
                        : "Régions"}
                </Label>
                <DepartmentCombobox
                  country={country}
                  value={selected}
                  onChange={setSelected}
                />
              </div>

              <div className="flex justify-center">
                <Button variant="outline" size="sm" onClick={handleSave} disabled={loading}>
                  Save
                </Button>
              </div>
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
