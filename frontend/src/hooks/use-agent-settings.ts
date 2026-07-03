"use client";

import { useEffect, useState } from "react";
import { filterRegionCodesForCountry } from "@/data/regions";
import {
  fetchDefaultRegionCities,
  GEOGRAPHICAL_GRANULARITY_CITY_FOCUS,
  GEOGRAPHICAL_GRANULARITY_LARGE,
  mergeWithDefaultRegionCities,
  type GeographicalGranularity,
} from "@/lib/geographical-granularity";
import { pruneRegionCities } from "@/lib/region-cities";
import {
  inferPublishedDatePreset,
  PUBLISHED_DATE_PRESET_ALL,
  PUBLISHED_DATE_PRESET_CUSTOM,
  type PublishedDatePreset,
} from "@/lib/published-date-presets";
import { getConfig, triggerRun, triggerTestRun, updateConfig } from "@/lib/api";

export function useAgentSettings(onRunStarted: (runId: string) => void) {
  const [country, setCountry] = useState("FR");
  const [selected, setSelectedState] = useState<string[]>([]);
  const [regionCities, setRegionCitiesState] = useState<Record<string, string[]>>({});
  const [exaSearchType, setExaSearchType] = useState("auto");
  const [exaCategory, setExaCategory] = useState("news");
  const [exaPublishedDatePreset, setExaPublishedDatePreset] =
    useState<PublishedDatePreset>(PUBLISHED_DATE_PRESET_ALL);
  const [exaStartPublishedDate, setExaStartPublishedDate] = useState("");
  const [exaEndPublishedDate, setExaEndPublishedDate] = useState("");
  const [geographicalGranularity, setGeographicalGranularityState] =
    useState<GeographicalGranularity>(GEOGRAPHICAL_GRANULARITY_LARGE);
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  async function loadConfig() {
    try {
      const config = await getConfig();
      const loadedCountry = config.country || "FR";
      setCountry(loadedCountry);
      setSelectedState(filterRegionCodesForCountry(config.departments, loadedCountry));
      setRegionCitiesState(
        pruneRegionCities(config.region_cities ?? {}, config.departments ?? [])
      );
      setExaSearchType(config.exa_search_type || "auto");
      setExaCategory(config.exa_category || "news");
      setExaPublishedDatePreset(
        inferPublishedDatePreset(
          config.exa_published_date_preset,
          config.exa_start_published_date,
          config.exa_end_published_date
        )
      );
      setExaStartPublishedDate(config.exa_start_published_date || "");
      setExaEndPublishedDate(config.exa_end_published_date || "");
      setGeographicalGranularityState(
        config.geographical_granularity === GEOGRAPHICAL_GRANULARITY_CITY_FOCUS
          ? GEOGRAPHICAL_GRANULARITY_CITY_FOCUS
          : GEOGRAPHICAL_GRANULARITY_LARGE
      );
      setSaved(true);
      setApiError(null);
    } catch (error) {
      setApiError(
        error instanceof Error
          ? error.message
          : "Unable to load configuration."
      );
    }
  }

  useEffect(() => {
    loadConfig();
  }, []);

  useEffect(() => {
    if (geographicalGranularity !== GEOGRAPHICAL_GRANULARITY_CITY_FOCUS || selected.length === 0) {
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const defaults = await fetchDefaultRegionCities(country, selected);
        if (cancelled) {
          return;
        }
        setRegionCitiesState((current) =>
          mergeWithDefaultRegionCities(current, selected, defaults)
        );
      } catch {
        // Les villes restent modifiables manuellement si l'API échoue.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [geographicalGranularity, country, selected]);

  function exaPublishedDatePayload() {
    const isCustom = exaPublishedDatePreset === PUBLISHED_DATE_PRESET_CUSTOM;
    return {
      exa_published_date_preset: exaPublishedDatePreset,
      exa_start_published_date: isCustom ? exaStartPublishedDate || null : null,
      exa_end_published_date: isCustom ? exaEndPublishedDate || null : null,
    };
  }

  function markDirty() {
    setSaved(false);
  }

  function setSelected(next: string[]) {
    setSelectedState(next);
    setRegionCitiesState((current) => pruneRegionCities(current, next));
    markDirty();
  }

  function setRegionCities(next: Record<string, string[]>) {
    setRegionCitiesState(next);
    markDirty();
  }

  function handleCountryChange(nextCountry: string) {
    setCountry(nextCountry);
    setSelectedState((current) => {
      const filtered = filterRegionCodesForCountry(current, nextCountry);
      setRegionCitiesState((cities) => pruneRegionCities(cities, filtered));
      return filtered;
    });
    markDirty();
  }

  function handlePublishedDatePresetChange(nextPreset: PublishedDatePreset) {
    setExaPublishedDatePreset(nextPreset);
    markDirty();
  }

  function handleGranularityChange(next: GeographicalGranularity) {
    setGeographicalGranularityState(next);
    markDirty();
  }

  function configPayload() {
    const isCityFocus = geographicalGranularity === GEOGRAPHICAL_GRANULARITY_CITY_FOCUS;
    return {
      country,
      departments: selected,
      region_cities: isCityFocus ? regionCities : {},
      geographical_granularity: geographicalGranularity,
      exa_search_type: exaSearchType,
      exa_category: exaCategory,
      ...exaPublishedDatePayload(),
    };
  }

  async function handleSave() {
    setLoading(true);
    try {
      await updateConfig(configPayload());
      setSaved(true);
      setApiError(null);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Failed to save.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRun() {
    setLoading(true);
    try {
      if (!saved) {
        await updateConfig(configPayload());
      }
      const run = await triggerRun();
      onRunStarted(run.id);
      setApiError(null);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Failed to start run.");
    } finally {
      setLoading(false);
    }
  }

  async function handleTestRun() {
    setLoading(true);
    try {
      if (!saved) {
        await updateConfig(configPayload());
      }
      const run = await triggerTestRun();
      onRunStarted(run.id);
      setApiError(null);
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Failed to start test run.");
    } finally {
      setLoading(false);
    }
  }

  return {
    country,
    setCountry: handleCountryChange,
    selected,
    setSelected,
    regionCities,
    setRegionCities,
    exaSearchType,
    setExaSearchType,
    exaCategory,
    setExaCategory,
    exaPublishedDatePreset,
    setExaPublishedDatePreset: handlePublishedDatePresetChange,
    exaStartPublishedDate,
    setExaStartPublishedDate,
    exaEndPublishedDate,
    setExaEndPublishedDate,
    geographicalGranularity,
    setGeographicalGranularity: handleGranularityChange,
    loading,
    saved,
    apiError,
    loadConfig,
    markDirty,
    handleSave,
    handleRun,
    handleTestRun,
  };
}
