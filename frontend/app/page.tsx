"use client";

import { useCallback, useEffect, useState } from "react";
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
import { saathiApi } from "@/components/saathi-api";
import type {
  AgentAction,
  AutonomySettings,
  Handoff,
  Health,
  Merchant,
  MerchantDetail,
  Message,
  Scoreboard,
} from "@/components/saathi-data";

export default function Home() {
  const [hash, setHash] = useState("home");
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [actions, setActions] = useState<AgentAction[]>([]);
  const [handoffs, setHandoffs] = useState<Handoff[]>([]);
  const [autonomy, setAutonomy] = useState<AutonomySettings>({});
  const [scoreboard, setScoreboard] = useState<Scoreboard | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [merchant, setMerchant] = useState<MerchantDetail | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [merchantActions, setMerchantActions] = useState<AgentAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [refreshVersion, setRefreshVersion] = useState(0);

  const chatMerchantId = hash.startsWith("chat-") ? hash.slice(5) : "";
  const merchantId = hash.startsWith("m-") ? hash.slice(2) : chatMerchantId;

  useEffect(() => {
    const syncHash = () => setHash(window.location.hash.slice(1) || "home");
    syncHash();
    window.addEventListener("hashchange", syncHash);
    return () => window.removeEventListener("hashchange", syncHash);
  }, []);

  const refreshCore = useCallback(async () => {
    try {
      const [healthResult, merchantResult, actionResult, handoffResult, autonomyResult, scoreboardResult] =
        await Promise.all([
          saathiApi.health(),
          saathiApi.merchants(),
          saathiApi.actions(),
          saathiApi.handoffs(),
          saathiApi.autonomy(),
          saathiApi.scoreboard(),
        ]);
      setHealth(healthResult);
      setMerchants(merchantResult.items);
      setActions(actionResult);
      setHandoffs(handoffResult);
      setAutonomy(autonomyResult);
      setScoreboard(scoreboardResult);
      setError("");
      return true;
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The backend request failed.");
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const [healthResult, merchantResult, actionResult, handoffResult, autonomyResult, scoreboardResult] =
          await Promise.all([
            saathiApi.health(),
            saathiApi.merchants(),
            saathiApi.actions(),
            saathiApi.handoffs(),
            saathiApi.autonomy(),
            saathiApi.scoreboard(),
          ]);
        if (!active) return;
        setHealth(healthResult);
        setMerchants(merchantResult.items);
        setActions(actionResult);
        setHandoffs(handoffResult);
        setAutonomy(autonomyResult);
        setScoreboard(scoreboardResult);
      } catch (requestError) {
        if (active) setError(requestError instanceof Error ? requestError.message : "The backend request failed.");
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!merchantId) return;
    let active = true;
    Promise.all([
      saathiApi.merchant(merchantId),
      saathiApi.messages(merchantId),
      saathiApi.merchantActions(merchantId),
    ]).then(([merchantResult, messageResult, actionResult]) => {
      if (!active) return;
      setMerchant(merchantResult);
      setMessages(messageResult.slice().sort((left, right) => left.created_at.localeCompare(right.created_at)));
      setMerchantActions(actionResult);
      setError("");
    }).catch((requestError: unknown) => {
      if (active) setError(requestError instanceof Error ? requestError.message : "Could not load this merchant.");
    });
    return () => { active = false; };
  }, [merchantId, refreshVersion]);

  const refresh = async () => {
    setNotice("");
    await refreshCore();
    setRefreshVersion((version) => version + 1);
  };

  const perform = async (operation: () => Promise<string | void>) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await operation();
      const refreshed = await refreshCore();
      setRefreshVersion((version) => version + 1);
      if (result) setNotice(result);
      if (!refreshed) setNotice("The action completed, but refreshing backend data failed.");
      return true;
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The backend action failed.");
      return false;
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    if (!window.confirm("Reset the backend demo data to its seeded state?")) return;
    void perform(async () => {
      await saathiApi.reset();
      window.location.hash = "home";
    });
  };

  const content = (() => {
    if (merchantId) {
      if (merchant?.id !== merchantId) return <div className="wrap"><div className="box loading-state">{error || "Loading merchant from backend…"}</div></div>;
      return <MerchantDetailView
        merchant={merchant}
        messages={messages}
        actions={merchantActions}
        isChat={Boolean(chatMerchantId)}
        busy={busy}
        onDeviceEvent={(event) => perform(async () => {
          const result = await saathiApi.recordDeviceEvent(merchantId, event);
          return event === "installed"
            ? `Demo device installed. Merchant status: ${result.merchant_state}.`
            : `Demo transaction recorded. Total successful transactions: ${result.total_transactions ?? 0}.`;
        })}
        onAdvanceClock={() => perform(async () => {
          const result = await saathiApi.advanceDemoClock(24);
          return `Demo clock advanced 24 hours. ${result.jobs_executed} scheduled job(s) ran.`;
        })}
        onSend={(text) => perform(async () => {
          const result = await saathiApi.sendMessage(merchantId, text);
          return result.reply ? `Agent replied. Merchant status: ${result.merchant_state}.` : `Message processed. Merchant status: ${result.merchant_state}.`;
        })}
        onUpload={(file, docType) => void perform(async () => {
          const result = await saathiApi.uploadDocument(merchantId, file, docType);
          if (!result.precheck_passed) {
            return `The ${docType === "pan" ? "PAN" : "address proof"} needs attention: ${result.issues.map((issue) => issue.replaceAll("_", " ")).join(", ") || result.quality}. Please upload a clearer, correct document.`;
          }
          return result.reply || `The ${docType === "pan" ? "PAN" : "address proof"} passed its automated pre-check.`;
        })}
      />;
    }
    switch (hash) {
      case "dashboard":
        return <DashboardView scoreboard={scoreboard} actions={actions} merchants={merchants} />;
      case "merchants":
        return <MerchantsView merchants={merchants} actions={actions} />;
      case "approvals":
        return <ApprovalsView
          actions={actions}
          autonomy={autonomy}
          busy={busy}
          onDecide={(id, approved) => void perform(async () => {
            if (approved) await saathiApi.approveAction(id);
            else await saathiApi.rejectAction(id);
            return `Action ${approved ? "approved" : "rejected"}.`;
          })}
          onAutonomyChange={(action, level) => void perform(async () => {
            await saathiApi.setAutonomy(action, level);
            return `${action} autonomy updated to ${level}.`;
          })}
        />;
      case "handoffs":
        return <HandoffsView
          handoffs={handoffs}
          busy={busy}
          onResolve={(id, note) => void perform(async () => {
            await saathiApi.resolveHandoff(id, note);
            return "Handoff resolved.";
          })}
        />;
      case "scoreboard":
        return <ScoreboardView />;
      default:
        return <HomeView />;
    }
  })();

  const pendingApprovals = actions.filter((action) => action.status === "pending_approval").length;
  const openHandoffs = handoffs.filter((handoff) => handoff.status === "open").length;

  return <>
    <SiteHeader
      hash={hash}
      health={health}
      pendingApprovals={pendingApprovals}
      openHandoffs={openHandoffs}
      busy={busy || loading}
      onReset={reset}
      onRefresh={() => void refresh()}
    />
    <main>
      {error && <div className="notice error" role="alert"><span>{error}</span><button onClick={() => void refresh()}>Retry</button></div>}
      {notice && <div className="notice success" role="status">{notice}</div>}
      {loading ? <div className="wrap"><div className="box loading-state">Connecting to the Saathi backend…</div></div> : content}
    </main>
  </>;
}
