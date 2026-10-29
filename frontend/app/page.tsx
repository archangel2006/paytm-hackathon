"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ApprovalsView,
  DashboardView,
  HandoffsView,
  HomeView,
  MerchantDetailView,
  MerchantsView,
  ScoreboardView,
  SiteHeader,
} from "@/components/saathi-ui";
import { createInitialState, type DemoState } from "@/components/saathi-data";

export default function Home() {
  const [hash, setHash] = useState("home");
  const [state, setState] = useState<DemoState>(() => createInitialState());

  useEffect(() => {
    const syncHash = () => setHash(window.location.hash.slice(1) || "home");
    syncHash();
    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
  }, []);

  const runScenario = (id: string) => {
    setState((current) => current.run(id));
  };
  const decideApproval = (id: number, approved: boolean) => {
    setState((current) => current.decide(id, approved));
  };
  const setAutonomy = (action: string, level: string) => {
    setState((current) => current.setAutonomy(action, level));
  };
  const resolveHandoff = (index: number) => {
    setState((current) => current.resolveHandoff(index));
  };
  const reset = () => {
    setState(createInitialState());
    window.location.hash = "home";
  };

  const content = useMemo(() => {
    if (hash.startsWith("m-") && state.merchants.some((merchant) => merchant.id === hash.slice(2))) {
      return (
        <MerchantDetailView
          merchantId={hash.slice(2)}
          state={state}
          onRun={runScenario}
        />
      );
    }
    switch (hash) {
      case "dashboard":
        return <DashboardView state={state} />;
      case "merchants":
        return <MerchantsView state={state} />;
      case "approvals":
        return <ApprovalsView state={state} onDecide={decideApproval} onAutonomyChange={setAutonomy} />;
      case "handoffs":
        return <HandoffsView state={state} onResolve={resolveHandoff} />;
      case "scoreboard":
        return <ScoreboardView />;
      default:
        return <HomeView />;
    }
  }, [hash, state]);

  return (
    <>
      <SiteHeader hash={hash} state={state} onReset={reset} />
      <main>{content}</main>
    </>
  );
}
