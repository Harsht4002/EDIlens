"use client";

import { useState } from "react";

const API_BASE = "http://localhost:8000";

type ParsedSegment = {
  index?: number;
  segment: string;
  elements: string[];
  raw?: string;
  error?: string;
};

type ParseResult = {
  segments: ParsedSegment[];
  errors: { segment: string; index?: number; error: string; raw?: string }[];
  complete?: {
    summary?: {
      interchangeCount: number;
      groupCount: number;
      transactionCount: number;
      segmentCount: number;
      errorCount: number;
    };
    interchanges?: Array<{
      functionalGroups?: Array<{
        transactions?: Array<{
          tree?: Array<{
            type?: string;
            claims?: unknown[];
            services?: unknown[];
            entities?: unknown[];
            children?: unknown[];
            segment?: { segment?: string; elements?: string[] };
          }>;
        }>;
      }>;
    }>;
  };
};

const SAMPLE_EDI = `ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250321*1200*^*00501*000000001*0*T*:~
GS*HC*SENDER*RECEIVER*20250321*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*12345*20250321*1200*CH~
NM1*41*2*ACME CORP*****46*12345~
NM1*IL*1*DOE*JOHN****MI*123456789A~
CLM*ABC123*100.00***11:B:1*Y*A*Y*Y~
SE*8*0001~
GE*1*1~
IEA*1*000000001~`;

export default function Home() {
  const [input, setInput] = useState(SAMPLE_EDI);
  const [result, setResult] = useState<ParseResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [explanation, setExplanation] = useState("");
  const [explainLoading, setExplainLoading] = useState(false);
  const [explainCache, setExplainCache] = useState<Record<string, string>>({});
  const [completeParse, setCompleteParse] = useState(false);

  const parse = async () => {
    setLoading(true);
    setResult(null);
    setExplanation("");
    setExplainCache({});
    try {
      const res = await fetch(`${API_BASE}/parse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw: input, complete_parse: completeParse }),
      });
      if (!res.ok) {
        throw new Error(`Parse failed: ${res.status}`);
      }
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setResult({
        segments: [],
        errors: [{ segment: "Error", elements: [], error: String(e) }],
      });
    } finally {
      setLoading(false);
    }
  };

  const explain = async (type: "segment" | "error", seg: ParsedSegment) => {
    const cacheKey = `${type}|${seg.segment}|${seg.elements.join("*")}|${seg.error ?? ""}|${seg.raw ?? ""}`;
    if (explainCache[cacheKey]) {
      setExplanation(explainCache[cacheKey]);
      return;
    }

    setExplainLoading(true);
    setExplanation("");
    try {
      const body =
        type === "segment"
          ? { type: "segment", segment: seg.segment, elements: seg.elements }
          : {
              type: "error",
              segment: seg.segment,
              error: seg.error,
            };
      const payload =
        type === "segment"
          ? { ...body, raw: seg.raw ?? "" }
          : body;
      const res = await fetch(`${API_BASE}/explain`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Explain failed: ${res.status}`);
      }
      const data = await res.json();
      const text = data.explanation || "No explanation returned.";
      setExplanation(text);
      setExplainCache((prev) => ({ ...prev, [cacheKey]: text }));
    } catch (e) {
      setExplanation(`Failed to get explanation: ${e}`);
    } finally {
      setExplainLoading(false);
    }
  };

  return (
    <div
      style={{
        maxWidth: 980,
        margin: "0 auto",
        padding: 20,
        color: "#111827",
      }}
    >
      <h1 style={{ marginBottom: 6 }}>Healthcare EDI X12 Parser</h1>
      <p style={{ marginTop: 0, color: "#4b5563", marginBottom: 18 }}>
        Paste or upload EDI, parse segments, and click any segment/error for AI explanation.
      </p>
      <div
        style={{
          marginBottom: 16,
          border: "1px solid #d1fae5",
          borderRadius: 10,
          padding: 12,
          background: "#ecfdf5",
          color: "#065f46",
          fontSize: 14,
        }}
      >
        <strong>How to use:</strong> 1) Paste EDI text or upload a file. 2) Optionally enable{" "}
        <strong>Complete Parse</strong> for deeper hierarchical parsing. 3) Click <strong>Parse</strong>. 4) Click
        any parsed segment or error to get AI explanation.
      </div>

      <div
        style={{
          marginBottom: 16,
          border: "1px solid #e5e7eb",
          borderRadius: 10,
          padding: 14,
          background: "#ffffff",
          boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
        }}
      >
        <div style={{ marginBottom: 10 }}>
          <input
            type="file"
            accept=".edi,.txt,.835,.837,*"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) {
                f.text().then((t) => setInput(t));
              }
            }}
          />
        </div>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Paste EDI content or upload a file..."
          style={{
            width: "100%",
            height: 150,
            fontFamily: "monospace",
            fontSize: 12.5,
            padding: 10,
            boxSizing: "border-box",
            border: "1px solid #d1d5db",
            borderRadius: 8,
          }}
        />
        <div style={{ marginTop: 10 }}>
          <label style={{ marginRight: 12, fontSize: 14, color: "#374151" }}>
            <input
              type="checkbox"
              checked={completeParse}
              onChange={(e) => setCompleteParse(e.target.checked)}
              style={{ marginRight: 6 }}
            />
            Complete Parse (deeper structure)
          </label>
        </div>
        <div style={{ marginTop: 10 }}>
          <button
            onClick={parse}
            disabled={loading}
            style={{
              padding: "8px 16px",
              borderRadius: 8,
              border: "1px solid #1d4ed8",
              background: "#2563eb",
              color: "white",
              cursor: loading ? "not-allowed" : "pointer",
              opacity: loading ? 0.8 : 1,
            }}
          >
            {loading ? "Parsing..." : "Parse"}
          </button>
        </div>
      </div>

      {result && (
        <div style={{ marginTop: 16, display: "grid", gap: 16 }}>
          {!completeParse && (
            <div
              style={{
                border: "1px solid #e5e7eb",
                borderRadius: 10,
                padding: 14,
                background: "#ffffff",
              }}
            >
              <h2 style={{ marginTop: 0, marginBottom: 8 }}>Parsed Segments</h2>
              <p style={{ marginTop: 0, color: "#6b7280", fontSize: 14 }}>
                {result.segments.length} segments parsed. Click any row for explanation.
              </p>
              <ul style={{ listStyle: "none", padding: 0 }}>
                {result.segments.map((seg, i) => (
                  <li
                    key={i}
                    onClick={() => explain(seg.error ? "error" : "segment", seg)}
                    style={{
                      padding: "10px 12px",
                      marginBottom: 6,
                      cursor: "pointer",
                      border: "1px solid #d1d5db",
                      borderRadius: 8,
                      backgroundColor: seg.error ? "#fffbeb" : "#f9fafb",
                    }}
                  >
                    <strong>{seg.segment}</strong> * {seg.elements.join(" * ")}
                    {seg.error && (
                      <span style={{ color: "#92400e", marginLeft: 8 }}>
                        — {seg.error}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {result.errors.length > 0 && (
            <div
              style={{
                border: "1px solid #fecaca",
                borderRadius: 10,
                padding: 14,
                background: "#fff7f7",
              }}
            >
              <h2 style={{ marginTop: 0, marginBottom: 8 }}>Detected Errors</h2>
              <ul style={{ listStyle: "none", padding: 0 }}>
                {result.errors.map((err, i) => (
                  <li
                    key={`err-${i}`}
                    onClick={() =>
                      explain("error", {
                        segment: err.segment,
                        elements: [],
                        error: err.error,
                        raw: err.raw,
                      })
                    }
                    style={{
                      padding: "10px 12px",
                      marginBottom: 6,
                      cursor: "pointer",
                      border: "1px solid #fca5a5",
                      borderRadius: 8,
                      backgroundColor: "#fff1f2",
                    }}
                  >
                    <strong>{err.segment}</strong> — {err.error}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {completeParse && result.complete && (
            <div
              style={{
                border: "1px solid #dbeafe",
                borderRadius: 10,
                padding: 14,
                background: "#f8fbff",
              }}
            >
              <h2 style={{ marginTop: 0, marginBottom: 8 }}>Complete Parse Summary</h2>
              <p style={{ marginTop: 0, color: "#4b5563", fontSize: 14 }}>
                Interchanges: {result.complete.summary?.interchangeCount ?? 0} | Groups:{" "}
                {result.complete.summary?.groupCount ?? 0} | Transactions:{" "}
                {result.complete.summary?.transactionCount ?? 0}
              </p>
              <div style={{ marginBottom: 10, fontSize: 14, color: "#1f2937" }}>
                {result.complete.interchanges?.map((ix, i) =>
                  (ix.functionalGroups || []).map((fg, j) =>
                    (fg.transactions || []).map((tx, k) => {
                      const nodes = tx.tree || [];
                      const hlNodes = nodes.filter((n) => n.type === "hlLoop").length;
                      const claimNodes = nodes.reduce((acc, n) => acc + ((n.claims?.length || 0)), 0);
                      const serviceNodes = nodes.reduce((acc, n) => acc + ((n.services?.length || 0)), 0);
                      const entityNodes = nodes.reduce((acc, n) => acc + ((n.entities?.length || 0)), 0);
                      return (
                        <div
                          key={`tx-${i}-${j}-${k}`}
                          style={{
                            border: "1px solid #bfdbfe",
                            background: "#eff6ff",
                            borderRadius: 8,
                            padding: "8px 10px",
                            marginBottom: 6,
                          }}
                        >
                          <strong>Transaction {k + 1}</strong> - HL loops: {hlNodes}, Claims: {claimNodes},
                          Services: {serviceNodes}, Entities: {entityNodes}
                        </div>
                      );
                    })
                  )
                )}
              </div>
              <details>
                <summary style={{ cursor: "pointer", color: "#1d4ed8" }}>
                  View full complete parse JSON
                </summary>
                <pre
                  style={{
                    marginTop: 10,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    background: "#0f172a",
                    color: "#e2e8f0",
                    padding: 12,
                    borderRadius: 8,
                    maxHeight: 320,
                    overflow: "auto",
                    fontSize: 12,
                  }}
                >
                  {JSON.stringify(result.complete, null, 2)}
                </pre>
              </details>
            </div>
          )}
        </div>
      )}

      {(explanation || explainLoading) && (
        <div
          style={{
            marginTop: 20,
            padding: 16,
            border: "1px solid #c7d2fe",
            borderRadius: 10,
            background: "#eef2ff",
          }}
        >
          <h3 style={{ marginTop: 0 }}>AI Explanation</h3>
          {explainLoading ? (
            <p>Loading...</p>
          ) : (
            <p style={{ whiteSpace: "pre-wrap" }}>{explanation}</p>
          )}
        </div>
      )}
    </div>
  );
}
