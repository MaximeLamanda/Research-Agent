"use client";

import { useEffect, useState } from "react";
import { filterRegionCodesForCountry } from "@/data/regions";
import {
  inferPublishedDatePreset,
  PUBLISHED_DATE_PRESET_ALL,
  PUBLISHED_DATE_PRESET_CUSTOM,
  type PublishedDatePreset,
} from "@/lib/published-date-presets";
import { getConfig, triggerRun, updateConfig } from "@/lib/api";

export function useAgentSettings(onRunStarted: (runId: string) => void) {
  const [country, setCountry] = useState("FR");
  const [selected, setSelectedState] = useState<string[]>([]);
  const [exaSearchType, setExaSearchType] = useState("auto");
  const [exaCategory, setExaCategory] = useState("news");
  const [exaPublishedDatePreset, setExaPublishedDatePreset] =
    useState<PublishedDatePreset>(PUBLISHED_DATE_PRESET_ALL);
  const [exaStartPublishedDate, setExaStartPublishedDate] = useState("");
  const [exaEndPublishedDate, setExaEndPublishedDate] = useState("");
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  async function loadConfig() {
    try {
      const config = await getConfig();
      const loadedCountry = config.country || "FR";
      setCountry(loadedCountry);
      setSelectedState(filterRegionCodesForCountry(config.departments, loadedCountry));
      setExaSearchType(
        config.exa_search_type === "deep" ? "auto" : config.exa_search_type || "auto"
      );
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
    markDirty();
  }

  function handleCountryChange(nextCountry: string) {
    setCountry(nextCountry);
    setSelectedState((current) => filterRegionCodesForCountry(current, nextCountry));
    markDirty();
  }

  function handlePublishedDatePresetChange(nextPreset: PublishedDatePreset) {
    setExaPublishedDatePreset(nextPreset);
    markDirty();
  }

  function configPayload() {
    return {
      country,
      departments: selected,
      exa_search_type: exaSearchType === "deep" ? "auto" : exaSearchType,
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

  return {
    country,
    setCountry: handleCountryChange,
    selected,
    setSelected,
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
    loading,
    saved,
    apiError,
    loadConfig,
    markDirty,
    handleSave,
    handleRun,
  };
}
