"use client";

import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";

export interface AccountInfo {
  id: string;
  display_name: string;
  role: string;
  risk_score: number;
  risk_level: "Safe" | "Watch" | "High risk";
  verdict_reasons: string[];
}

export interface PeerItem {
  id: string;
  display_name: string;
  amount: number;
  count: number;
  risk_level: "Safe" | "Watch" | "High risk";
  status: string;
  first_ts?: number | null;
  last_ts?: number | null;
}

export interface SharedDevice {
  device_label: string;
  device_id?: string;
  other_accounts: number;
  other_account_ids?: string[];
  other_account_names?: string[];
}

export interface HeldPayment {
  to: string;
  to_name?: string;
  amount: number;
  minutes_left: number;
}

export interface MoneyMapData {
  account: AccountInfo;
  received: {
    total_amount: number;
    count: number;
    senders: PeerItem[];
  };
  sent: {
    total_amount: number;
    count: number;
    payees: PeerItem[];
  };
  shared_devices: SharedDevice[];
  held_payments: HeldPayment[];
  summary_sentence: string;
}

export interface AccountOption {
  id: string;
  display_name: string;
  role?: string;
}

interface MoneyMapProps {
  initialAccountId?: string;
  apiBaseUrl?: string;
}

export default function MoneyMap({
  initialAccountId = "acc_1",
  apiBaseUrl = "http://localhost:8000",
}: MoneyMapProps) {
  const [currentAccountId, setCurrentAccountId] = useState<string>(initialAccountId);
  const [data, setData] = useState<MoneyMapData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // View mode: Map or Table
  const [viewMode, setViewMode] = useState<"map" | "table">("map");

  // History / Breadcrumbs
  const [historyTrail, setHistoryTrail] = useState<Array<{ id: string; name: string }>>([]);

  // Account search & list
  const [accountList, setAccountList] = useState<AccountOption[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [isSearchOpen, setIsSearchOpen] = useState<boolean>(false);

  // Expand toggles
  const [expandSenders, setExpandSenders] = useState<boolean>(false);
  const [expandPayees, setExpandPayees] = useState<boolean>(false);

  // Hover state for interactive highlight
  const [hoveredPeerId, setHoveredPeerId] = useState<string | null>(null);
  const [hoveredPeerType, setHoveredPeerType] = useState<"sender" | "payee" | null>(null);

  // Collapsible technical details
  const [showTechDetails, setShowTechDetails] = useState<boolean>(false);

  // Shared devices drawer panel
  const [activeSharedDevice, setActiveSharedDevice] = useState<SharedDevice | null>(null);

  // Live countdown for held payments
  const [liveMinutesLeft, setLiveMinutesLeft] = useState<Record<string, number>>({});

  // Container refs for measuring SVG arrow coordinates
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const leftColRef = useRef<HTMLDivElement>(null);
  const centreCardRef = useRef<HTMLDivElement>(null);
  const rightColRef = useRef<HTMLDivElement>(null);

  const [coords, setCoords] = useState<{
    leftPointers: Array<{ id: string; x1: number; y1: number; x2: number; y2: number; amount: number; isHeld: boolean }>;
    rightPointers: Array<{ id: string; x1: number; y1: number; x2: number; y2: number; amount: number; isHeld: boolean }>;
  }>({ leftPointers: [], rightPointers: [] });

  // Fetch available accounts for the picker
  const fetchAccounts = useCallback(async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/v1/accounts`);
      if (res.ok) {
        const json: AccountOption[] = await res.json();
        setAccountList(json);
      }
    } catch {
      // Non-critical, fallback will allow direct typing
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    fetchAccounts();
  }, [fetchAccounts]);

  // Fetch Money Map Data
  const fetchMoneyMap = useCallback(
    async (accId: string) => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${apiBaseUrl}/v1/graph/account/${encodeURIComponent(accId)}?hops=1`);
        if (!res.ok) {
          throw new Error(`Failed to load money map (status ${res.status})`);
        }
        const json: MoneyMapData = await res.json();
        setData(json);

        // Initialize countdown timers
        const initialTimers: Record<string, number> = {};
        json.held_payments?.forEach((hp) => {
          initialTimers[hp.to] = hp.minutes_left;
        });
        setLiveMinutesLeft(initialTimers);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Unable to connect to backend server";
        setError(msg);
        setData(null);
      } finally {
        setLoading(false);
      }
    },
    [apiBaseUrl]
  );

  useEffect(() => {
    fetchMoneyMap(currentAccountId);
  }, [currentAccountId, fetchMoneyMap]);

  // Live countdown timer ticker (ticks every 60s)
  useEffect(() => {
    const interval = setInterval(() => {
      setLiveMinutesLeft((prev) => {
        const updated = { ...prev };
        let changed = false;
        Object.keys(updated).forEach((key) => {
          if (updated[key] > 1) {
            updated[key] -= 1;
            changed = true;
          }
        });
        return changed ? updated : prev;
      });
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  // Check URL param or external trigger on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const acc = params.get("account");
      if (acc) {
        setCurrentAccountId(acc);
      }
      (window as unknown as { __setMoneyMapAccount?: (id: string) => void }).__setMoneyMapAccount = (id: string) => {
        if (id) setCurrentAccountId(id);
      };
    }
  }, []);

  // Navigate to new account with history tracking
  const handleSelectAccount = (newId: string, displayName?: string) => {
    if (!newId || newId === currentAccountId) return;
    const currentName = data?.account.display_name || currentAccountId;
    setHistoryTrail((prev) => [...prev, { id: currentAccountId, name: currentName }]);
    setCurrentAccountId(newId);
    setSearchQuery("");
    setIsSearchOpen(false);
    setExpandSenders(false);
    setExpandPayees(false);
    setHoveredPeerId(null);
  };

  // Back button navigation
  const handleGoBack = () => {
    if (historyTrail.length === 0) return;
    const last = historyTrail[historyTrail.length - 1];
    setHistoryTrail((prev) => prev.slice(0, -1));
    setCurrentAccountId(last.id);
    setSearchQuery("");
    setIsSearchOpen(false);
    setExpandSenders(false);
    setExpandPayees(false);
    setHoveredPeerId(null);
  };

  // Compute 2D SVG arrow coordinates dynamically
  const updateArrowCoordinates = useCallback(() => {
    if (!mapContainerRef.current || !centreCardRef.current || !data) return;

    const containerRect = mapContainerRef.current.getBoundingClientRect();
    const centreRect = centreCardRef.current.getBoundingClientRect();

    const centreLeftX = centreRect.left - containerRect.left;
    const centreRightX = centreRect.right - containerRect.left;
    const centreMidY = centreRect.top - containerRect.top + centreRect.height / 2;

    // Senders (Left)
    const leftPointers: typeof coords.leftPointers = [];
    const visibleSenders = expandSenders ? data.received.senders : data.received.senders.slice(0, 5);

    visibleSenders.forEach((s, idx) => {
      const el = document.getElementById(`sender-card-${s.id}`);
      if (el) {
        const r = el.getBoundingClientRect();
        const startX = r.right - containerRect.left;
        const startY = r.top - containerRect.top + r.height / 2;
        const isHeld = (data.held_payments || []).some((h) => h.to === currentAccountId);
        const count = visibleSenders.length;
        const targetY = count <= 1 ? centreMidY : (centreRect.top - containerRect.top + 50 + (idx * (centreRect.height - 100)) / (count - 1));
        leftPointers.push({
          id: s.id,
          x1: startX,
          y1: startY,
          x2: centreLeftX,
          y2: targetY,
          amount: s.amount,
          isHeld,
        });
      }
    });

    // Payees (Right)
    const rightPointers: typeof coords.rightPointers = [];
    const visiblePayees = expandPayees ? data.sent.payees : data.sent.payees.slice(0, 5);

    visiblePayees.forEach((p, idx) => {
      const el = document.getElementById(`payee-card-${p.id}`);
      if (el) {
        const r = el.getBoundingClientRect();
        const endX = r.left - containerRect.left;
        const endY = r.top - containerRect.top + r.height / 2;
        const isHeld = (data.held_payments || []).some((h) => h.to === p.id);
        const count = visiblePayees.length;
        const startRightY = count <= 1 ? centreMidY : (centreRect.top - containerRect.top + 50 + (idx * (centreRect.height - 100)) / (count - 1));
        rightPointers.push({
          id: p.id,
          x1: centreRightX,
          y1: startRightY,
          x2: endX,
          y2: endY,
          amount: p.amount,
          isHeld,
        });
      }
    });

    setCoords({ leftPointers, rightPointers });
  }, [data, expandSenders, expandPayees, currentAccountId]);

  useEffect(() => {
    const handleResize = () => updateArrowCoordinates();
    window.addEventListener("resize", handleResize);
    const timeout = setTimeout(updateArrowCoordinates, 60);
    return () => {
      window.removeEventListener("resize", handleResize);
      clearTimeout(timeout);
    };
  }, [updateArrowCoordinates]);

  // Calculate arrow thickness (min 2px, max 10px) based on amount
  const getArrowStrokeWidth = (amount: number): number => {
    if (!amount || amount <= 0) return 2;
    // Scale logarithmic: 100 -> 2.5px, 10,000 -> 5px, 200,000 -> 10px
    const width = 2 + Math.min(8, Math.log10(Math.max(10, amount)) * 1.6);
    return Math.max(2, Math.min(10, Math.round(width * 10) / 10));
  };

  // Format currency in Indian Rupees
  const formatINR = (val: number): string => {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);
  };

  // Format timestamp
  const formatTime = (ts?: number | null): string => {
    if (!ts) return "—";
    return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  // Verdict visual properties (Safe / Watch / High risk)
  const getVerdictProps = (verdict: "Safe" | "Watch" | "High risk") => {
    switch (verdict) {
      case "Safe":
        return {
          label: "Safe",
          icon: "✓",
          color: "#10b981", // Emerald
          bg: "rgba(16, 185, 129, 0.12)",
          border: "rgba(16, 185, 129, 0.4)",
        };
      case "Watch":
        return {
          label: "Watch",
          icon: "👁",
          color: "#f59e0b", // Amber
          bg: "rgba(245, 158, 11, 0.12)",
          border: "rgba(245, 158, 11, 0.4)",
        };
      case "High risk":
      default:
        return {
          label: "High risk",
          icon: "⚠",
          color: "#ef4444", // Crimson
          bg: "rgba(239, 68, 68, 0.14)",
          border: "rgba(239, 68, 68, 0.45)",
        };
    }
  };

  // Filtered account search options
  const filteredAccounts = useMemo(() => {
    if (!searchQuery.trim()) return accountList.slice(0, 15);
    const q = searchQuery.toLowerCase();
    return accountList.filter(
      (a) => a.id.toLowerCase().includes(q) || a.display_name.toLowerCase().includes(q)
    );
  }, [accountList, searchQuery]);

  // Inbound & Outbound calculations for summary strip
  const totalReceived = data?.received.total_amount || 0;
  const totalSent = data?.sent.total_amount || 0;
  const passThroughPct =
    totalReceived > 0 ? Math.round((totalSent / totalReceived) * 100) : totalSent > 0 ? 100 : 0;
  const totalSharedCount =
    data?.shared_devices?.reduce((acc, curr) => acc + curr.other_accounts, 0) || 0;

  // Render Loading / Error
  if (loading && !data) {
    return (
      <div style={styles.loadingContainer}>
        <div style={styles.spinner}></div>
        <p style={styles.loadingText}>Loading Money Map...</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div style={styles.errorContainer}>
        <div style={styles.errorIcon}>⚠</div>
        <h2 style={styles.errorTitle}>Backend Connection Error</h2>
        <p style={styles.errorMessage}>{error}</p>
        <button style={styles.retryButton} onClick={() => fetchMoneyMap(currentAccountId)}>
          Retry Connection
        </button>
      </div>
    );
  }

  if (!data) return null;

  const currentVerdict = getVerdictProps(data.account.risk_level);
  const ringRadius = 36;
  const ringCircumference = 2 * Math.PI * ringRadius;
  const strokeDashoffset =
    ringCircumference - (Math.min(100, Math.max(0, data.account.risk_score)) / 100) * ringCircumference;

  const visibleSenders = expandSenders ? data.received.senders : data.received.senders.slice(0, 5);
  const hiddenSendersCount = Math.max(0, data.received.senders.length - 5);

  const visiblePayees = expandPayees ? data.sent.payees : data.sent.payees.slice(0, 5);
  const hiddenPayeesCount = Math.max(0, data.sent.payees.length - 5);

  return (
    <div style={styles.wrapper}>
      <style>{`
        .stats-strip {
          display: grid;
          grid-template-columns: repeat(4, 1fr) !important;
          gap: 16px;
          margin-bottom: 24px;
        }
        .three-columns-grid {
          display: grid;
          grid-template-columns: 1fr 1.15fr 1fr;
          gap: 88px !important;
          position: relative;
          z-index: 2;
        }
        .header-bar {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 20px;
          margin-bottom: 24px;
          flex-wrap: wrap;
        }
        @media (max-width: 990px) {
          .stats-strip {
            grid-template-columns: repeat(2, 1fr) !important;
          }
          .three-columns-grid {
            grid-template-columns: 1fr !important;
            gap: 20px !important;
          }
          .svg-overlay {
            display: none !important;
          }
          .header-bar {
            flex-direction: column !important;
            align-items: stretch !important;
            gap: 16px !important;
          }
        }
        @media (max-width: 640px) {
          .stats-strip {
            gap: 10px !important;
          }
          .moneymap-wrapper {
            padding: 16px 12px !important;
          }
          .centre-card {
            padding: 18px 12px !important;
          }
          .centre-name {
            font-size: 19px !important;
          }
        }
      `}</style>

      {/* Top Header: Account Picker, Breadcrumbs, Table Toggle */}
      <div style={styles.headerBar} className="header-bar">
        <div style={styles.headerLeft}>
          <div style={styles.searchWrap}>
            <label htmlFor="accountSearchInput" style={styles.fieldLabel}>Search Account:</label>
            <div style={styles.inputContainer}>
              <input
                id="accountSearchInput"
                type="text"
                placeholder="Type name or account ID..."
                value={searchQuery}
                onFocus={() => setIsSearchOpen(true)}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setIsSearchOpen(true);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    if (filteredAccounts.length > 0) {
                      handleSelectAccount(filteredAccounts[0].id, filteredAccounts[0].display_name);
                    } else if (searchQuery.trim()) {
                      handleSelectAccount(searchQuery.trim());
                    }
                  }
                }}
                style={styles.searchInput}
              />
              {isSearchOpen && (
                <div style={styles.dropdown}>
                  {filteredAccounts.length === 0 ? (
                    <div style={styles.dropdownItemEmpty}>No matching accounts found</div>
                  ) : (
                    filteredAccounts.map((opt) => (
                      <div
                        key={opt.id}
                        style={styles.dropdownItem}
                        onClick={() => handleSelectAccount(opt.id, opt.display_name)}
                      >
                        <span style={styles.dropdownItemName}>{opt.display_name}</span>
                        <span style={styles.dropdownItemId}>{opt.id}</span>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Breadcrumb Trail & Back Button */}
          <div style={styles.breadcrumbBar}>
            {historyTrail.length > 0 && (
              <button style={styles.backButton} onClick={handleGoBack} title="Back to previous account">
                ← Back
              </button>
            )}
            <div style={styles.breadcrumbs}>
              {historyTrail.map((item, idx) => (
                <span key={item.id + idx} style={styles.breadcrumbItem}>
                  <button
                    style={styles.breadcrumbLink}
                    onClick={() => {
                      const newTrail = historyTrail.slice(0, idx);
                      setHistoryTrail(newTrail);
                      setCurrentAccountId(item.id);
                    }}
                  >
                    {item.name}
                  </button>
                  <span style={styles.breadcrumbSeparator}>›</span>
                </span>
              ))}
              <span style={styles.breadcrumbCurrent}>{data.account.display_name}</span>
            </div>
          </div>
        </div>

        {/* View Toggle: Map vs Table */}
        <div style={styles.toggleWrap}>
          <div style={styles.viewToggleGroup}>
            <button
              style={viewMode === "map" ? styles.viewToggleActive : styles.viewToggleBtn}
              onClick={() => setViewMode("map")}
            >
              Map View
            </button>
            <button
              style={viewMode === "table" ? styles.viewToggleActive : styles.viewToggleBtn}
              onClick={() => setViewMode("table")}
            >
              Table View
            </button>
          </div>
        </div>
      </div>

      {/* Stats Strip: 4 per row on desktop, 2 per row on mobile */}
      <div style={styles.statsStrip} className="stats-strip">
        <div style={styles.statBox}>
          <span style={styles.statLabel}>Total Received</span>
          <span style={styles.statNumber}>{formatINR(totalReceived)}</span>
          <span style={styles.statSub}>{data.received.count} transfers</span>
        </div>
        <div style={styles.statBox}>
          <span style={styles.statLabel}>Total Sent</span>
          <span style={styles.statNumber}>{formatINR(totalSent)}</span>
          <span style={styles.statSub}>{data.sent.count} transfers</span>
        </div>
        <div style={styles.statBox}>
          <span style={styles.statLabel}>Pass-Through</span>
          <span style={styles.statNumber}>{passThroughPct}%</span>
          <span style={styles.statSub}>of inflow re-routed</span>
        </div>
        <div style={styles.statBox}>
          <span style={styles.statLabel}>Shared Devices</span>
          <span style={styles.statNumber}>{totalSharedCount}</span>
          <span style={styles.statSub}>linked accounts</span>
        </div>
      </div>

      {/* 20px Executive Summary Sentence Headline */}
      <div style={styles.headlineCard}>
        <h1 style={styles.summaryHeadline}>{data.summary_sentence}</h1>
      </div>

      {viewMode === "map" ? (
        /* MONEY MAP 2D VISUALIZATION */
        <div style={styles.mapContainer} ref={mapContainerRef}>
          {/* SVG Overlay for arrows */}
          <svg style={styles.svgOverlay} className="svg-overlay">
            <defs>
              <marker id="arrowhead" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
                <polygon points="0 0, 8 4, 0 8" fill="#475569" />
              </marker>
              <marker id="arrowhead-highlight" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
                <polygon points="0 0, 8 4, 0 8" fill="#38bdf8" />
              </marker>
              <marker id="arrowhead-held" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
                <polygon points="0 0, 8 4, 0 8" fill="#f59e0b" />
              </marker>
            </defs>

            {/* Left Senders Arrows -> Centre */}
            {coords.leftPointers.map((p) => {
              const isHovered = hoveredPeerId === p.id && hoveredPeerType === "sender";
              const strokeColor = p.isHeld ? "#f59e0b" : isHovered ? "#38bdf8" : "#334155";
              const strokeW = isHovered ? Math.max(4, getArrowStrokeWidth(p.amount) + 2) : getArrowStrokeWidth(p.amount);
              const marker = p.isHeld ? "url(#arrowhead-held)" : isHovered ? "url(#arrowhead-highlight)" : "url(#arrowhead)";

              const midX = (p.x1 + p.x2) / 2;
              const midY = (p.y1 + p.y2) / 2;
              const pathD = `M ${p.x1} ${p.y1} C ${p.x1 + 40} ${p.y1}, ${p.x2 - 40} ${p.y2}, ${p.x2} ${p.y2}`;

              return (
                <g key={`arrow-left-${p.id}`}>
                  <path
                    d={pathD}
                    fill="none"
                    stroke={strokeColor}
                    strokeWidth={strokeW}
                    strokeDasharray={p.isHeld ? "6,6" : "none"}
                    markerEnd={marker}
                    style={{ transition: "stroke 0.2s, stroke-width 0.2s" }}
                  />
                  {/* Amount label on the line */}
                  <rect
                    x={midX - 44}
                    y={midY - 13}
                    width="88"
                    height="24"
                    rx="6"
                    fill="#0b111e"
                    stroke="#233354"
                    strokeWidth="1"
                  />
                  <text
                    x={midX}
                    y={midY + 4}
                    textAnchor="middle"
                    fill={isHovered ? "#38bdf8" : "#cbd5e1"}
                    style={styles.svgAmountLabel}
                  >
                    {formatINR(p.amount)}
                  </text>
                </g>
              );
            })}

            {/* Centre -> Right Payees Arrows */}
            {coords.rightPointers.map((p) => {
              const isHovered = hoveredPeerId === p.id && hoveredPeerType === "payee";
              const strokeColor = p.isHeld ? "#f59e0b" : isHovered ? "#38bdf8" : "#334155";
              const strokeW = isHovered ? Math.max(4, getArrowStrokeWidth(p.amount) + 2) : getArrowStrokeWidth(p.amount);
              const marker = p.isHeld ? "url(#arrowhead-held)" : isHovered ? "url(#arrowhead-highlight)" : "url(#arrowhead)";

              const midX = (p.x1 + p.x2) / 2;
              const midY = (p.y1 + p.y2) / 2;
              const pathD = `M ${p.x1} ${p.y1} C ${p.x1 + 40} ${p.y1}, ${p.x2 - 40} ${p.y2}, ${p.x2} ${p.y2}`;

              return (
                <g key={`arrow-right-${p.id}`}>
                  <path
                    d={pathD}
                    fill="none"
                    stroke={strokeColor}
                    strokeWidth={strokeW}
                    strokeDasharray={p.isHeld ? "6,6" : "none"}
                    markerEnd={marker}
                    style={{ transition: "stroke 0.2s, stroke-width 0.2s" }}
                  />
                  {/* Amount label on the line */}
                  <rect
                    x={midX - 44}
                    y={midY - 13}
                    width="88"
                    height="24"
                    rx="6"
                    fill="#0b111e"
                    stroke="#233354"
                    strokeWidth="1"
                  />
                  <text
                    x={midX}
                    y={midY + 4}
                    textAnchor="middle"
                    fill={isHovered ? "#38bdf8" : "#cbd5e1"}
                    style={styles.svgAmountLabel}
                  >
                    {formatINR(p.amount)}
                  </text>

                  {/* Held Payment Stamp & Countdown */}
                  {p.isHeld && (
                    <g transform={`translate(${midX - 35}, ${midY + 16})`}>
                      <rect x="0" y="0" width="70" height="20" rx="4" fill="#b45309" stroke="#f59e0b" strokeWidth="1" />
                      <text x="35" y="14" textAnchor="middle" fill="#ffffff" style={styles.svgHeldText}>
                        HELD ({liveMinutesLeft[p.id] || 10}m)
                      </text>
                    </g>
                  )}
                </g>
              );
            })}
          </svg>

          {/* Three Main Columns Grid */}
          <div style={styles.threeColumnsGrid} className="three-columns-grid">
            {/* LEFT COLUMN: Money came from */}
            <div style={styles.column} ref={leftColRef}>
              <div style={styles.columnHeader}>
                <h2 style={styles.columnTitle}>Money came from</h2>
                <span style={styles.columnCount}>{data.received.senders.length} accounts</span>
              </div>

              <div style={styles.cardsList}>
                {data.received.senders.length === 0 ? (
                  <div style={styles.calmPlaceholderCard}>
                    <span style={styles.placeholderIcon}>✦</span>
                    <span style={styles.placeholderText}>No money received yet</span>
                  </div>
                ) : (
                  visibleSenders.map((s) => {
                    const verdict = getVerdictProps(s.risk_level);
                    const isHovered = hoveredPeerId === s.id && hoveredPeerType === "sender";

                    return (
                      <div
                        id={`sender-card-${s.id}`}
                        key={`sender-${s.id}`}
                        tabIndex={0}
                        style={{
                          ...styles.personCard,
                          ...(isHovered ? styles.personCardHovered : {}),
                        }}
                        onMouseEnter={() => {
                          setHoveredPeerId(s.id);
                          setHoveredPeerType("sender");
                        }}
                        onMouseLeave={() => {
                          setHoveredPeerId(null);
                          setHoveredPeerType(null);
                        }}
                        onClick={() => handleSelectAccount(s.id, s.display_name)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            handleSelectAccount(s.id, s.display_name);
                          }
                        }}
                        title={`Click to inspect ${s.display_name}. Total: ${formatINR(s.amount)}, ${s.count} transfer(s).`}
                      >
                        <div style={styles.cardHeaderRow}>
                          <div style={styles.personName} title={s.display_name}>
                            {s.display_name}
                          </div>
                          <div
                            style={{
                              ...styles.verdictDot,
                              backgroundColor: verdict.color,
                            }}
                            title={`Risk verdict: ${verdict.label}`}
                          >
                            <span style={styles.verdictDotIcon}>{verdict.icon}</span>
                          </div>
                        </div>

                        <div style={styles.cardIdMono} title={s.id}>
                          {s.id}
                        </div>

                        <div style={styles.cardDetailsRow}>
                          <span style={styles.amountMono}>{formatINR(s.amount)}</span>
                          <span style={styles.transfersCount}>
                            {s.count} {s.count === 1 ? "payment" : "payments"}
                          </span>
                        </div>

                        {/* Hover detailed tooltip */}
                        {isHovered && (
                          <div style={styles.tooltipBox}>
                            <div>First: {formatTime(s.first_ts)}</div>
                            <div>Last: {formatTime(s.last_ts)}</div>
                            <div>Status: {s.status}</div>
                          </div>
                        )}
                      </div>
                    );
                  })
                )}

                {/* +N More expand card */}
                {hiddenSendersCount > 0 && (
                  <button
                    style={styles.expandCard}
                    onClick={() => setExpandSenders(!expandSenders)}
                  >
                    {expandSenders ? "▲ Show fewer senders" : `+ ${hiddenSendersCount} more senders`}
                  </button>
                )}
              </div>
            </div>

            {/* CENTRE COLUMN: This account */}
            <div style={styles.columnCentre}>
              <div style={styles.columnHeader}>
                <h2 style={styles.columnTitle}>This account</h2>
                <span style={styles.columnRoleBadge}>{data.account.role}</span>
              </div>

              <div style={styles.centreCard} ref={centreCardRef}>
                {/* Risk Ring & Score */}
                <div style={styles.centreRingWrap}>
                  <svg width="92" height="92" style={styles.ringSvg}>
                    <circle
                      cx="46"
                      cy="46"
                      r={ringRadius}
                      fill="none"
                      stroke="#1e293b"
                      strokeWidth="8"
                    />
                    <circle
                      cx="46"
                      cy="46"
                      r={ringRadius}
                      fill="none"
                      stroke={currentVerdict.color}
                      strokeWidth="8"
                      strokeDasharray={ringCircumference}
                      strokeDashoffset={strokeDashoffset}
                      strokeLinecap="round"
                      style={{
                        transform: "rotate(-90deg)",
                        transformOrigin: "46px 46px",
                        transition: "stroke-dashoffset 0.4s ease-out",
                      }}
                    />
                  </svg>
                  <div style={styles.centreScoreDisplay}>
                    <span style={styles.scoreNumber}>{Math.round(data.account.risk_score)}</span>
                    <span style={styles.scoreLabel}>RISK</span>
                  </div>
                </div>

                {/* Account Details */}
                <div style={styles.centreName} title={data.account.display_name}>
                  {data.account.display_name}
                </div>
                <div style={styles.centreIdMono} title={data.account.id}>
                  {data.account.id}
                </div>

                {/* Verdict Badge with Icon + Word */}
                <div
                  style={{
                    ...styles.verdictBadgeLarge,
                    backgroundColor: currentVerdict.bg,
                    borderColor: currentVerdict.border,
                    color: currentVerdict.color,
                  }}
                >
                  <span style={styles.verdictBadgeIcon}>{currentVerdict.icon}</span>
                  <span style={styles.verdictBadgeText}>{currentVerdict.label}</span>
                </div>

                {/* Shared Device Chip */}
                {data.shared_devices && data.shared_devices.length > 0 && (
                  <button
                    style={styles.sharedDeviceChip}
                    onClick={() => setActiveSharedDevice(data.shared_devices[0])}
                    title="Click to view all accounts sharing this phone"
                  >
                    <span>📱</span>
                    <span>
                      Phone shared with {data.shared_devices[0].other_accounts} other{" "}
                      {data.shared_devices[0].other_accounts === 1 ? "account" : "accounts"}
                    </span>
                    <span style={styles.infoBadge}>ⓘ</span>
                  </button>
                )}
              </div>
            </div>

            {/* RIGHT COLUMN: Money went to */}
            <div style={styles.column} ref={rightColRef}>
              <div style={styles.columnHeader}>
                <h2 style={styles.columnTitle}>Money went to</h2>
                <span style={styles.columnCount}>{data.sent.payees.length} accounts</span>
              </div>

              <div style={styles.cardsList}>
                {data.sent.payees.length === 0 ? (
                  <div style={styles.calmPlaceholderCard}>
                    <span style={styles.placeholderIcon}>✦</span>
                    <span style={styles.placeholderText}>No money sent yet</span>
                  </div>
                ) : (
                  visiblePayees.map((p) => {
                    const verdict = getVerdictProps(p.risk_level);
                    const isHovered = hoveredPeerId === p.id && hoveredPeerType === "payee";

                    return (
                      <div
                        id={`payee-card-${p.id}`}
                        key={`payee-${p.id}`}
                        tabIndex={0}
                        style={{
                          ...styles.personCard,
                          ...(isHovered ? styles.personCardHovered : {}),
                        }}
                        onMouseEnter={() => {
                          setHoveredPeerId(p.id);
                          setHoveredPeerType("payee");
                        }}
                        onMouseLeave={() => {
                          setHoveredPeerId(null);
                          setHoveredPeerType(null);
                        }}
                        onClick={() => handleSelectAccount(p.id, p.display_name)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            handleSelectAccount(p.id, p.display_name);
                          }
                        }}
                        title={`Click to inspect ${p.display_name}. Total: ${formatINR(p.amount)}, ${p.count} transfer(s).`}
                      >
                        <div style={styles.cardHeaderRow}>
                          <div style={styles.personName} title={p.display_name}>
                            {p.display_name}
                          </div>
                          <div
                            style={{
                              ...styles.verdictDot,
                              backgroundColor: verdict.color,
                            }}
                            title={`Risk verdict: ${verdict.label}`}
                          >
                            <span style={styles.verdictDotIcon}>{verdict.icon}</span>
                          </div>
                        </div>

                        <div style={styles.cardIdMono} title={p.id}>
                          {p.id}
                        </div>

                        <div style={styles.cardDetailsRow}>
                          <span style={styles.amountMono}>{formatINR(p.amount)}</span>
                          <span style={styles.transfersCount}>
                            {p.count} {p.count === 1 ? "payment" : "payments"}
                          </span>
                        </div>

                        {/* Hover detailed tooltip */}
                        {isHovered && (
                          <div style={styles.tooltipBox}>
                            <div>First: {formatTime(p.first_ts)}</div>
                            <div>Last: {formatTime(p.last_ts)}</div>
                            <div>Status: {p.status}</div>
                          </div>
                        )}
                      </div>
                    );
                  })
                )}

                {/* +N More expand card */}
                {hiddenPayeesCount > 0 && (
                  <button
                    style={styles.expandCard}
                    onClick={() => setExpandPayees(!expandPayees)}
                  >
                    {expandPayees ? "▲ Show fewer payees" : `+ ${hiddenPayeesCount} more payees`}
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* 3-Item Legend & Thickness guidance */}
          <div style={styles.legendContainer}>
            <div style={styles.legendItems}>
              <div style={styles.legendItem}>
                <span style={{ ...styles.legendDot, backgroundColor: "#10b981" }}>✓</span>
                <span style={styles.legendText}>Safe</span>
              </div>
              <div style={styles.legendItem}>
                <span style={{ ...styles.legendDot, backgroundColor: "#f59e0b" }}>👁</span>
                <span style={styles.legendText}>Watch</span>
              </div>
              <div style={styles.legendItem}>
                <span style={{ ...styles.legendDot, backgroundColor: "#ef4444" }}>⚠</span>
                <span style={styles.legendText}>High risk</span>
              </div>
            </div>
            <div style={styles.legendNote}>Arrow thickness = amount.</div>
          </div>
        </div>
      ) : (
        /* ACCESSIBLE TABLE VIEW FALLBACK */
        <div style={styles.tableFallbackContainer}>
          <h2 style={styles.tableTitle}>Account Transaction Ledger</h2>
          <div style={styles.tableScroll}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Direction</th>
                  <th style={styles.th}>Account Name</th>
                  <th style={styles.th}>Account ID</th>
                  <th style={styles.th}>Total Amount</th>
                  <th style={styles.th}>Transfers</th>
                  <th style={styles.th}>Verdict</th>
                  <th style={styles.th}>Action</th>
                </tr>
              </thead>
              <tbody>
                {data.received.senders.map((s) => {
                  const v = getVerdictProps(s.risk_level);
                  return (
                    <tr key={`tbl-s-${s.id}`} style={styles.tr}>
                      <td style={styles.td}>IN (From)</td>
                      <td style={styles.td}>{s.display_name}</td>
                      <td style={styles.tdMono}>{s.id}</td>
                      <td style={styles.tdMono}>{formatINR(s.amount)}</td>
                      <td style={styles.td}>{s.count}</td>
                      <td style={styles.td}>
                        <span style={{ ...styles.tableBadge, color: v.color }}>
                          {v.icon} {v.label}
                        </span>
                      </td>
                      <td style={styles.td}>
                        <button
                          style={styles.tableInspectBtn}
                          onClick={() => handleSelectAccount(s.id, s.display_name)}
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  );
                })}
                {data.sent.payees.map((p) => {
                  const v = getVerdictProps(p.risk_level);
                  return (
                    <tr key={`tbl-p-${p.id}`} style={styles.tr}>
                      <td style={styles.td}>OUT (To)</td>
                      <td style={styles.td}>{p.display_name}</td>
                      <td style={styles.tdMono}>{p.id}</td>
                      <td style={styles.tdMono}>{formatINR(p.amount)}</td>
                      <td style={styles.td}>{p.count}</td>
                      <td style={styles.td}>
                        <span style={{ ...styles.tableBadge, color: v.color }}>
                          {v.icon} {v.label}
                        </span>
                      </td>
                      <td style={styles.td}>
                        <button
                          style={styles.tableInspectBtn}
                          onClick={() => handleSelectAccount(p.id, p.display_name)}
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* WHY THIS VERDICT & TECHNICAL DETAILS */}
      <div style={styles.bottomSection}>
        <div style={styles.whyCard}>
          <h2 style={styles.sectionHeading}>Why this verdict</h2>
          <ul style={styles.reasonsList}>
            {data.account.verdict_reasons.map((r, i) => (
              <li key={i} style={styles.reasonItem}>
                <span style={styles.reasonBullet}>•</span>
                <span style={styles.reasonText}>{r}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Collapsible Technical Details for Analysts */}
        <div style={styles.techCard}>
          <button
            style={styles.techToggleBtn}
            onClick={() => setShowTechDetails(!showTechDetails)}
            aria-expanded={showTechDetails}
          >
            <span style={styles.techToggleTitle}>Technical details for analysts</span>
            <span style={styles.techToggleArrow}>{showTechDetails ? "▲" : "▼"}</span>
          </button>

          {showTechDetails && (
            <div style={styles.techDetailsBody}>
              <div style={styles.techRow}>
                <span style={styles.techLabel}>Account Identifier:</span>
                <span style={styles.techValMono}>{data.account.id}</span>
              </div>
              <div style={styles.techRow}>
                <span style={styles.techLabel}>Computed Risk Score:</span>
                <span style={styles.techValMono}>{data.account.risk_score} / 100</span>
              </div>
              <div style={styles.techRow}>
                <span style={styles.techLabel}>Classification Role:</span>
                <span style={styles.techValMono}>{data.account.role}</span>
              </div>
              <div style={styles.techRow}>
                <span style={styles.techLabel}>Active Liens / Holds:</span>
                <span style={styles.techValMono}>
                  {data.held_payments?.length ? `${data.held_payments.length} lien(s) active` : "None"}
                </span>
              </div>
              <div style={styles.techRow}>
                <span style={styles.techLabel}>Device Fingerprint Nodes:</span>
                <span style={styles.techValMono}>
                  {data.shared_devices?.map((d) => `${d.device_label} (${d.other_accounts} others)`).join(", ") || "Unique device"}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Shared Devices Side Panel Drawer */}
      {activeSharedDevice && (
        <div style={styles.drawerOverlay} onClick={() => setActiveSharedDevice(null)}>
          <div style={styles.drawerContent} onClick={(e) => e.stopPropagation()}>
            <div style={styles.drawerHeader}>
              <h2 style={styles.drawerTitle}>Device Sharing Details</h2>
              <button style={styles.drawerCloseBtn} onClick={() => setActiveSharedDevice(null)}>
                ✕
              </button>
            </div>
            <p style={styles.drawerSub}>
              Device Label: <b>{activeSharedDevice.device_label}</b>
            </p>
            <p style={styles.drawerDesc}>
              This physical device or emulator is actively linked with{" "}
              <b>{activeSharedDevice.other_accounts}</b> other user account(s):
            </p>
            <div style={styles.drawerList}>
              {activeSharedDevice.other_account_ids?.map((accId, i) => {
                const accName = activeSharedDevice.other_account_names?.[i] || accId;
                return (
                  <div key={accId} style={styles.drawerItem}>
                    <div>
                      <div style={styles.drawerItemName}>{accName}</div>
                      <div style={styles.drawerItemId}>{accId}</div>
                    </div>
                    <button
                      style={styles.drawerSwitchBtn}
                      onClick={() => {
                        setActiveSharedDevice(null);
                        handleSelectAccount(accId, accName);
                      }}
                    >
                      Inspect
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Inline CSS Styles adhering to DESIGN.md (Navy / Emerald Palette, 18px body, nothing under 14px)
const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Helvetica Neue", sans-serif',
    fontSize: "18px",
    color: "#f8fafc",
    backgroundColor: "#0b111e",
    minHeight: "100%",
    padding: "24px 28px",
    boxSizing: "border-box",
  },
  headerBar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    flexWrap: "wrap",
    gap: "18px",
    marginBottom: "24px",
  },
  headerLeft: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    flex: "1 1 500px",
  },
  searchWrap: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    position: "relative",
  },
  fieldLabel: {
    fontSize: "16px",
    fontWeight: 600,
    color: "#94a3b8",
  },
  inputContainer: {
    position: "relative",
    flex: "1 1 300px",
    maxWidth: "420px",
  },
  searchInput: {
    width: "100%",
    boxSizing: "border-box",
    backgroundColor: "#111a2e",
    border: "1px solid #233354",
    borderRadius: "10px",
    padding: "10px 14px",
    fontSize: "16px",
    color: "#f8fafc",
    outline: "none",
  },
  dropdown: {
    position: "absolute",
    top: "calc(100% + 4px)",
    left: 0,
    right: 0,
    backgroundColor: "#111a2e",
    border: "1px solid #233354",
    borderRadius: "10px",
    boxShadow: "0 10px 25px rgba(0,0,0,0.5)",
    zIndex: 90,
    maxHeight: "260px",
    overflowY: "auto",
  },
  dropdownItem: {
    padding: "12px 14px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    borderBottom: "1px solid #18243e",
    cursor: "pointer",
  },
  dropdownItemEmpty: {
    padding: "14px",
    fontSize: "15px",
    color: "#94a3b8",
    textAlign: "center",
  },
  dropdownItemName: {
    fontSize: "16px",
    fontWeight: 600,
    color: "#f8fafc",
  },
  dropdownItemId: {
    fontSize: "14px",
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
    color: "#94a3b8",
  },
  breadcrumbBar: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    flexWrap: "wrap",
  },
  backButton: {
    backgroundColor: "#18243e",
    border: "1px solid #233354",
    borderRadius: "8px",
    padding: "6px 14px",
    color: "#cbd5e1",
    fontSize: "15px",
    cursor: "pointer",
    fontWeight: 600,
  },
  breadcrumbs: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    flexWrap: "wrap",
    fontSize: "16px",
  },
  breadcrumbItem: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
  },
  breadcrumbLink: {
    background: "none",
    border: "none",
    color: "#38bdf8",
    fontSize: "16px",
    cursor: "pointer",
    padding: 0,
    textDecoration: "underline",
  },
  breadcrumbSeparator: {
    color: "#64748b",
  },
  breadcrumbCurrent: {
    color: "#f8fafc",
    fontWeight: 700,
  },
  toggleWrap: {
    display: "flex",
    alignItems: "center",
  },
  viewToggleGroup: {
    display: "flex",
    backgroundColor: "#111a2e",
    border: "1px solid #233354",
    borderRadius: "10px",
    overflow: "hidden",
  },
  viewToggleBtn: {
    background: "none",
    border: "none",
    padding: "10px 18px",
    fontSize: "16px",
    color: "#94a3b8",
    cursor: "pointer",
    fontWeight: 600,
  },
  viewToggleActive: {
    backgroundColor: "#233354",
    border: "none",
    padding: "10px 18px",
    fontSize: "16px",
    color: "#f8fafc",
    cursor: "pointer",
    fontWeight: 700,
  },
  statsStrip: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: "16px",
    marginBottom: "24px",
  },
  statBox: {
    backgroundColor: "#111a2e",
    border: "1px solid #233354",
    borderRadius: "12px",
    padding: "18px 20px",
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  statLabel: {
    fontSize: "14px",
    textTransform: "uppercase",
    letterSpacing: "0.6px",
    color: "#94a3b8",
    fontWeight: 600,
  },
  statNumber: {
    fontSize: "26px",
    fontWeight: 800,
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
    color: "#f8fafc",
  },
  statSub: {
    fontSize: "14px",
    color: "#64748b",
  },
  headlineCard: {
    backgroundColor: "#111a2e",
    border: "1px solid #233354",
    borderRadius: "12px",
    padding: "18px 24px",
    marginBottom: "24px",
  },
  summaryHeadline: {
    margin: 0,
    fontSize: "20px",
    lineHeight: "1.4",
    fontWeight: 600,
    color: "#f8fafc",
  },
  mapContainer: {
    position: "relative",
    backgroundColor: "#111a2e",
    border: "1px solid #233354",
    borderRadius: "16px",
    padding: "24px 20px",
    marginBottom: "24px",
    overflow: "hidden",
  },
  svgOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    width: "100%",
    height: "100%",
    pointerEvents: "none",
    zIndex: 10,
  },
  svgAmountLabel: {
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
    fontSize: "16px",
    fontWeight: 700,
  },
  svgHeldText: {
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
    fontSize: "14px",
    fontWeight: 800,
  },
  threeColumnsGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1.15fr 1fr",
    gap: "28px",
    position: "relative",
    zIndex: 20,
  },
  column: {
    display: "flex",
    flexDirection: "column",
    gap: "14px",
  },
  columnCentre: {
    display: "flex",
    flexDirection: "column",
    gap: "14px",
  },
  columnHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    paddingBottom: "8px",
    borderBottom: "1px solid #233354",
  },
  columnTitle: {
    margin: 0,
    fontSize: "18px",
    fontWeight: 700,
    color: "#94a3b8",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  },
  columnCount: {
    fontSize: "14px",
    color: "#64748b",
  },
  columnRoleBadge: {
    fontSize: "14px",
    color: "#94a3b8",
    backgroundColor: "#18243e",
    padding: "2px 8px",
    borderRadius: "6px",
    textTransform: "capitalize",
  },
  cardsList: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  personCard: {
    backgroundColor: "#18243e",
    border: "1px solid #233354",
    borderRadius: "12px",
    padding: "14px 16px",
    cursor: "pointer",
    transition: "border-color 0.2s, background-color 0.2s, transform 0.2s",
    outline: "none",
    position: "relative",
  },
  personCardHovered: {
    backgroundColor: "#203052",
    borderColor: "#38bdf8",
  },
  cardHeaderRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "8px",
  },
  personName: {
    fontSize: "18px",
    fontWeight: 700,
    color: "#f8fafc",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  verdictDot: {
    width: "22px",
    height: "22px",
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  verdictDotIcon: {
    color: "#ffffff",
    fontSize: "14px",
    fontWeight: "bold",
    lineHeight: "1",
  },
  cardIdMono: {
    fontSize: "14px",
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
    color: "#94a3b8",
    marginTop: "2px",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  cardDetailsRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: "10px",
    paddingTop: "8px",
    borderTop: "1px solid rgba(255,255,255,0.06)",
    flexWrap: "wrap",
    gap: "6px",
  },
  amountMono: {
    fontSize: "17px",
    fontWeight: 800,
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
    color: "#f8fafc",
  },
  transfersCount: {
    fontSize: "14px",
    color: "#94a3b8",
  },
  tooltipBox: {
    marginTop: "8px",
    padding: "8px 10px",
    backgroundColor: "#0b111e",
    border: "1px solid #233354",
    borderRadius: "6px",
    fontSize: "14px",
    color: "#cbd5e1",
    lineHeight: "1.3",
  },
  calmPlaceholderCard: {
    backgroundColor: "rgba(24, 36, 62, 0.4)",
    border: "1px dashed #233354",
    borderRadius: "12px",
    padding: "28px 16px",
    textAlign: "center",
    color: "#64748b",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "6px",
  },
  placeholderIcon: {
    fontSize: "20px",
    color: "#475569",
  },
  placeholderText: {
    fontSize: "16px",
  },
  expandCard: {
    backgroundColor: "#18243e",
    border: "1px dashed #233354",
    borderRadius: "10px",
    padding: "10px",
    color: "#38bdf8",
    fontSize: "15px",
    fontWeight: 600,
    cursor: "pointer",
    textAlign: "center",
  },
  centreCard: {
    backgroundColor: "#18243e",
    border: "2px solid #233354",
    borderRadius: "16px",
    padding: "24px 20px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    textAlign: "center",
    gap: "10px",
    boxShadow: "0 8px 30px rgba(0,0,0,0.3)",
  },
  centreRingWrap: {
    position: "relative",
    width: "92px",
    height: "92px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  ringSvg: {
    position: "absolute",
    top: 0,
    left: 0,
  },
  centreScoreDisplay: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
  },
  scoreNumber: {
    fontSize: "24px",
    fontWeight: 800,
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
    color: "#f8fafc",
    lineHeight: "1",
  },
  scoreLabel: {
    fontSize: "14px",
    letterSpacing: "0.8px",
    color: "#94a3b8",
    fontWeight: 700,
  },
  centreName: {
    fontSize: "22px",
    fontWeight: 800,
    color: "#f8fafc",
    marginTop: "4px",
    maxWidth: "100%",
    wordBreak: "break-word",
    lineHeight: "1.25",
  },
  centreIdMono: {
    fontSize: "14px",
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
    color: "#94a3b8",
  },
  verdictBadgeLarge: {
    display: "inline-flex",
    alignItems: "center",
    gap: "8px",
    padding: "8px 16px",
    borderRadius: "99px",
    border: "1px solid",
    fontSize: "16px",
    fontWeight: 700,
    marginTop: "4px",
  },
  verdictBadgeIcon: {
    fontSize: "18px",
    lineHeight: "1",
  },
  verdictBadgeText: {
    textTransform: "capitalize",
  },
  sharedDeviceChip: {
    backgroundColor: "#111a2e",
    border: "1px solid #233354",
    borderRadius: "99px",
    padding: "6px 14px",
    fontSize: "14px",
    color: "#cbd5e1",
    display: "flex",
    alignItems: "center",
    gap: "6px",
    cursor: "pointer",
    marginTop: "10px",
  },
  infoBadge: {
    fontSize: "14px",
    color: "#38bdf8",
  },
  legendContainer: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: "24px",
    paddingTop: "14px",
    borderTop: "1px solid #233354",
    flexWrap: "wrap",
    gap: "10px",
  },
  legendItems: {
    display: "flex",
    gap: "18px",
    alignItems: "center",
  },
  legendItem: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
  },
  legendDot: {
    width: "22px",
    height: "22px",
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#ffffff",
    fontSize: "14px",
    fontWeight: "bold",
  },
  legendText: {
    fontSize: "15px",
    color: "#cbd5e1",
    fontWeight: 600,
  },
  legendNote: {
    fontSize: "15px",
    color: "#94a3b8",
  },
  tableFallbackContainer: {
    backgroundColor: "#111a2e",
    border: "1px solid #233354",
    borderRadius: "16px",
    padding: "20px",
    marginBottom: "24px",
  },
  tableTitle: {
    margin: "0 0 16px 0",
    fontSize: "20px",
    fontWeight: 700,
  },
  tableScroll: {
    overflowX: "auto",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "16px",
  },
  th: {
    textAlign: "left",
    padding: "12px",
    borderBottom: "2px solid #233354",
    color: "#94a3b8",
    fontSize: "14px",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  },
  tr: {
    borderBottom: "1px solid #18243e",
  },
  td: {
    padding: "12px",
    color: "#f8fafc",
  },
  tdMono: {
    padding: "12px",
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
    color: "#cbd5e1",
  },
  tableBadge: {
    fontSize: "14px",
    fontWeight: 700,
  },
  tableInspectBtn: {
    backgroundColor: "#18243e",
    border: "1px solid #233354",
    borderRadius: "6px",
    padding: "4px 10px",
    fontSize: "14px",
    color: "#38bdf8",
    cursor: "pointer",
  },
  bottomSection: {
    display: "flex",
    flexDirection: "column",
    gap: "18px",
  },
  whyCard: {
    backgroundColor: "#111a2e",
    border: "1px solid #233354",
    borderRadius: "16px",
    padding: "20px 24px",
  },
  sectionHeading: {
    margin: "0 0 12px 0",
    fontSize: "18px",
    fontWeight: 700,
    color: "#94a3b8",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  },
  reasonsList: {
    listStyle: "none",
    margin: 0,
    padding: 0,
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  reasonItem: {
    display: "flex",
    alignItems: "flex-start",
    gap: "10px",
    fontSize: "18px",
    lineHeight: "1.4",
  },
  reasonBullet: {
    color: "#38bdf8",
    fontWeight: 700,
  },
  reasonText: {
    color: "#f8fafc",
  },
  techCard: {
    backgroundColor: "#111a2e",
    border: "1px solid #233354",
    borderRadius: "16px",
    padding: "16px 24px",
  },
  techToggleBtn: {
    width: "100%",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    background: "none",
    border: "none",
    color: "#94a3b8",
    fontSize: "16px",
    fontWeight: 600,
    cursor: "pointer",
    padding: 0,
  },
  techToggleTitle: {
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  },
  techToggleArrow: {
    fontSize: "14px",
  },
  techDetailsBody: {
    marginTop: "16px",
    paddingTop: "14px",
    borderTop: "1px solid #18243e",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  techRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "10px",
    flexWrap: "wrap",
    fontSize: "15px",
  },
  techLabel: {
    color: "#94a3b8",
  },
  techValMono: {
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
    color: "#f8fafc",
  },
  drawerOverlay: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0,0,0,0.65)",
    zIndex: 100,
    display: "flex",
    justifyContent: "flex-end",
  },
  drawerContent: {
    backgroundColor: "#111a2e",
    borderLeft: "2px solid #233354",
    width: "100%",
    maxWidth: "420px",
    height: "100%",
    padding: "24px",
    boxSizing: "border-box",
    display: "flex",
    flexDirection: "column",
    gap: "14px",
    boxShadow: "-10px 0 30px rgba(0,0,0,0.6)",
  },
  drawerHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  drawerTitle: {
    margin: 0,
    fontSize: "20px",
    fontWeight: 700,
  },
  drawerCloseBtn: {
    background: "none",
    border: "none",
    color: "#94a3b8",
    fontSize: "20px",
    cursor: "pointer",
  },
  drawerSub: {
    margin: 0,
    fontSize: "16px",
    color: "#cbd5e1",
  },
  drawerDesc: {
    margin: 0,
    fontSize: "15px",
    color: "#94a3b8",
    lineHeight: "1.4",
  },
  drawerList: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    overflowY: "auto",
    marginTop: "8px",
  },
  drawerItem: {
    backgroundColor: "#18243e",
    border: "1px solid #233354",
    borderRadius: "10px",
    padding: "12px 14px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  drawerItemName: {
    fontSize: "16px",
    fontWeight: 600,
    color: "#f8fafc",
  },
  drawerItemId: {
    fontSize: "14px",
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
    color: "#94a3b8",
  },
  drawerSwitchBtn: {
    backgroundColor: "#111a2e",
    border: "1px solid #233354",
    borderRadius: "6px",
    padding: "6px 12px",
    fontSize: "14px",
    color: "#38bdf8",
    cursor: "pointer",
    fontWeight: 600,
  },
  loadingContainer: {
    padding: "80px 20px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "16px",
  },
  spinner: {
    width: "40px",
    height: "40px",
    border: "4px solid rgba(255,255,255,0.1)",
    borderTopColor: "#10b981",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
  loadingText: {
    fontSize: "18px",
    color: "#94a3b8",
  },
  errorContainer: {
    backgroundColor: "#111a2e",
    border: "1px solid #ef4444",
    borderRadius: "16px",
    padding: "40px 24px",
    textAlign: "center",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "12px",
  },
  errorIcon: {
    fontSize: "36px",
    color: "#ef4444",
  },
  errorTitle: {
    margin: 0,
    fontSize: "22px",
    color: "#f8fafc",
  },
  errorMessage: {
    margin: 0,
    fontSize: "16px",
    color: "#94a3b8",
    maxWidth: "500px",
  },
  retryButton: {
    backgroundColor: "#ef4444",
    color: "#ffffff",
    border: "none",
    borderRadius: "8px",
    padding: "10px 20px",
    fontSize: "16px",
    fontWeight: 600,
    cursor: "pointer",
    marginTop: "8px",
  },
};
