"use client";

import { useState } from "react";
import { AgentStatus } from "@/components/agent-status";
import { RunArticleBatches } from "@/components/run-article-batches";
import { ProjectList } from "@/components/project-list";
import { RunList } from "@/components/run-list";
import { SettingsAccordion } from "@/components/settings-accordion";
import { Button } from "@/components/ui/button";
import { ColorOrb } from "@/components/ui/color-orb";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAgentSettings } from "@/hooks/use-agent-settings";
import { useRunStream } from "@/hooks/use-run-stream";

export default function HomePage() {
  const [runId, setRunId] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const settings = useAgentSettings(setRunId);
  const { active, message, stats, batches, toggleBatch } = useRunStream(runId, () =>
    setRefreshKey((k) => k + 1)
  );

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 space-y-8">
      {settings.apiError && (
        <p className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-center text-sm text-destructive">
          {settings.apiError}
        </p>
      )}

      <section className="mx-auto flex w-full max-w-md flex-col items-center gap-6">
        <header className="flex w-full flex-col items-center gap-4 text-center">
          <div
            className="flex items-center justify-center"
            style={{
              width: active ? "112px" : "80px",
              height: active ? "112px" : "80px",
            }}
          >
            <ColorOrb dimension={active ? "96px" : "64px"} />
          </div>

          {active && (
            <>
              <AgentStatus active={active} message={message} stats={null} />
              <RunArticleBatches batches={batches} onToggleBatch={toggleBatch} />
            </>
          )}

          <div className="flex w-full flex-col items-center gap-3">
            <h1 className="text-2xl font-bold">Research Agent</h1>
            <p className="max-w-sm text-sm text-muted-foreground">
              C&I construction project monitoring — industrial, logistics, retail
            </p>

            {!active && (
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button
                  size="xl"
                  onClick={settings.handleRun}
                  disabled={settings.loading || settings.selected.length === 0 || !!settings.apiError}
                  className="min-w-48"
                >
                  Run now
                </Button>
                <Button
                  variant="outline"
                  size="xl"
                  onClick={settings.handleTestRun}
                  disabled={settings.loading || settings.selected.length === 0 || !!settings.apiError}
                  className="min-w-48"
                >
                  Test (1 lien)
                </Button>
              </div>
            )}

            {!active && stats && (
              <AgentStatus active={false} message="" stats={stats} />
            )}
          </div>
        </header>

        <SettingsAccordion settings={settings} />
      </section>

      <Tabs defaultValue="projects" className="mx-auto w-full max-w-5xl">
        <TabsList variant="line" className="w-full justify-center border-b rounded-none px-0">
          <TabsTrigger value="projects">Projects</TabsTrigger>
          <TabsTrigger value="runs">Runs</TabsTrigger>
        </TabsList>
        <TabsContent value="projects" className="mt-6">
          <ProjectList refreshKey={refreshKey} />
        </TabsContent>
        <TabsContent value="runs" className="mt-6">
          <RunList refreshKey={refreshKey} />
        </TabsContent>
      </Tabs>
    </main>
  );
}
