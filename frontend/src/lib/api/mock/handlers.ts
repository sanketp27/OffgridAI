import { createId, delay } from "@/lib/api/client";
import { MOCK_CATALOG } from "@/lib/api/mock/catalog";
import type {
  FitCheckRequest,
  FitCheckResponse,
  GenerateInsightsRequest,
  GenerateInsightsResponse,
  ReturnAssessRequest,
  ReturnAssessment,
  ReturnConfirmRequest,
  ReturnConfirmResponse,
  SearchRequest,
  SearchResponse,
  SearchResult,
} from "@/lib/api/types";

function scoreToQuality(score: number): SearchResult["match_quality"] {
  if (score >= 0.75) return "exact";
  if (score >= 0.4) return "near";
  return "miss";
}

function isStockoutQuery(query: string) {
  const q = query.toLowerCase();
  return (
    q.includes("today") ||
    q.includes("in stock") ||
    q.includes("out of stock") ||
    (q.includes("running") && q.includes("shoe"))
  );
}

function isVagueOrHiking(query: string) {
  const q = query.toLowerCase();
  return (
    q.includes("waterproof") ||
    q.includes("hiking") ||
    q.includes("boot") ||
    q.includes("under") ||
    q.includes("cozy") ||
    q.length < 12
  );
}

export async function mockSearch(req: SearchRequest): Promise<SearchResponse> {
  await delay(520);

  const sessionId = req.session_id || createId("sess");
  const eventId = createId("evt");
  const query = (req.query_text ?? "").trim();
  const hasImage = Boolean(req.image_base64);

  if (isStockoutQuery(query)) {
    const preferred = MOCK_CATALOG.find((c) => c.sku_id === "RN-210")!;
    const sub = MOCK_CATALOG.find((c) => c.sku_id === "TG-882")!;
    const alt = MOCK_CATALOG.find((c) => c.sku_id === "WP-441")!;

    return {
      session_id: sessionId,
      event_id: eventId,
      results: [
        {
          sku_id: sub.sku_id,
          name: sub.name,
          price: sub.price,
          currency: sub.currency,
          image_url: sub.image_url,
          match_score: 0.74,
          match_explanation:
            "In-stock substitute with similar outdoor use; available for pickup today (SKU TG-882).",
          match_quality: "near",
        },
        {
          sku_id: alt.sku_id,
          name: alt.name,
          price: alt.price,
          currency: alt.currency,
          image_url: alt.image_url,
          match_score: 0.68,
          match_explanation:
            "Premium waterproof alternative; ships same day from nearby store (SKU WP-441).",
          match_quality: "near",
        },
      ],
      fit_check: { triggered: false, sku_id: null, question: null },
      rescue: {
        triggered: true,
        preferred_sku_id: preferred.sku_id,
        preferred_name: preferred.name,
        reason: `${preferred.name} (size 9) is out of stock at this store today.`,
        options: [
          {
            option_id: "opt-sub",
            type: "substitute",
            sku_id: sub.sku_id,
            name: sub.name,
            price: sub.price,
            currency: sub.currency,
            image_url: sub.image_url,
            tradeoff:
              "₹800 more than AeroRun promo price, but ready for pickup in 20 minutes.",
          },
          {
            option_id: "opt-nearby",
            type: "nearby_store",
            sku_id: preferred.sku_id,
            name: `${preferred.name} · Koramangala store`,
            price: preferred.price,
            currency: preferred.currency,
            image_url: preferred.image_url,
            tradeoff: "Exact SKU available 2.4 km away — reserve & pick up in ~35 min.",
          },
          {
            option_id: "opt-ship",
            type: "ship",
            sku_id: preferred.sku_id,
            name: `${preferred.name} · ship today`,
            price: preferred.price,
            currency: preferred.currency,
            image_url: preferred.image_url,
            tradeoff: "Same SKU delivered by 8pm — ₹49 express fee.",
          },
        ],
      },
    };
  }

  const hikingPath = hasImage || isVagueOrHiking(query) || !query;

  if (hikingPath) {
    const trail = MOCK_CATALOG.find((c) => c.sku_id === "TG-882")!;
    const ridge = MOCK_CATALOG.find((c) => c.sku_id === "WP-441")!;
    const pack = MOCK_CATALOG.find((c) => c.sku_id === "BG-901")!;

    const results: SearchResult[] = [
      {
        sku_id: trail.sku_id,
        name: trail.name,
        price: trail.price,
        currency: trail.currency,
        image_url: trail.image_url,
        match_score: 0.81,
        match_explanation:
          "Matches waterproof + hiking intent and falls under ₹4,000 (SKU TG-882).",
        match_quality: scoreToQuality(0.81),
      },
      {
        sku_id: ridge.sku_id,
        name: ridge.name,
        price: ridge.price,
        currency: ridge.currency,
        image_url: ridge.image_url,
        match_score: 0.62,
        match_explanation:
          "Strong waterproof hiking attributes; ₹700 over the stated budget (SKU WP-441).",
        match_quality: scoreToQuality(0.62),
      },
      {
        sku_id: pack.sku_id,
        name: pack.name,
        price: pack.price,
        currency: pack.currency,
        image_url: pack.image_url,
        match_score: 0.48,
        match_explanation:
          "Adjacent outdoor gear often bought with hiking boots (SKU BG-901).",
        match_quality: scoreToQuality(0.48),
      },
    ];

    return {
      session_id: sessionId,
      results,
      fit_check: {
        triggered: true,
        sku_id: trail.sku_id,
        question:
          "TrailGrip runs about a half size small — do you usually wear 9 or prefer sizing up to 9.5?",
      },
      rescue: null,
      event_id: eventId,
    };
  }

  const lamp = MOCK_CATALOG.find((c) => c.sku_id === "LK-055")!;
  const mug = MOCK_CATALOG.find((c) => c.sku_id === "ST-033")!;

  return {
    session_id: sessionId,
    results: [
      {
        sku_id: lamp.sku_id,
        name: lamp.name,
        price: lamp.price,
        currency: lamp.currency,
        image_url: lamp.image_url,
        match_score: 0.88,
        match_explanation:
          "Matches cozy living-room lighting intent within budget (SKU LK-055).",
        match_quality: "exact",
      },
      {
        sku_id: mug.sku_id,
        name: mug.name,
        price: mug.price,
        currency: mug.currency,
        image_url: mug.image_url,
        match_score: 0.71,
        match_explanation:
          "Complements a cozy home setup; not lighting but often co-purchased (SKU ST-033).",
        match_quality: "near",
      },
    ],
    fit_check: { triggered: false, sku_id: null, question: null },
    rescue: null,
    event_id: eventId,
  };
}

export async function mockFitCheck(
  req: FitCheckRequest,
): Promise<FitCheckResponse> {
  await delay(380);
  const text = req.response_text.toLowerCase();
  const sizeUp =
    text.includes("9.5") ||
    text.includes("size up") ||
    text.includes("wider") ||
    text.includes("wide");

  return {
    resolution: sizeUp ? "size_changed" : "confirmed",
    new_sku_id: sizeUp ? "TG-882-9.5" : req.sku_id,
    cart_updated: true,
    event_id: createId("evt"),
  };
}

export async function mockGenerateInsights(
  _req: GenerateInsightsRequest,
): Promise<GenerateInsightsResponse> {
  await delay(700);
  const generatedAt = new Date().toISOString();

  return {
    generated_at: generatedAt,
    event_count_processed: 47,
    insights: [
      {
        insight_id: createId("ins"),
        signal_type: "unmet_demand",
        label: "waterproof hiking boots under ₹4,000",
        occurrences: 14,
        unique_shoppers: 12,
        trend_pct: 40,
        est_revenue_at_risk: 42000,
        urgency_days: 5,
        brief:
          "14 shoppers searched for waterproof hiking boots under ₹4,000 this week (↑40% vs last week) and left without buying — ~₹42,000 in weekly revenue at risk. Consider adding a matching SKU.",
        recommended_action:
          "Source a waterproof hiking boot priced under ₹4,000",
        generated_at: generatedAt,
      },
      {
        insight_id: createId("ins"),
        signal_type: "fit_issue",
        label: "TrailGrip size 9 → 9.5 flip",
        occurrences: 8,
        unique_shoppers: 7,
        trend_pct: null,
        est_revenue_at_risk: 18500,
        urgency_days: 10,
        brief:
          "Running shoe / boot size 9 has a high fit-check flip rate — shoppers keep switching to 9.5 after one question. Your size chart likely shows incorrect sizing for TrailGrip.",
        recommended_action: "Update TrailGrip size chart and PDP guidance",
        generated_at: generatedAt,
      },
      {
        insight_id: createId("ins"),
        signal_type: "stock_gap",
        label: "AeroRun Trainer size 9 · same-day demand",
        occurrences: 5,
        unique_shoppers: 5,
        trend_pct: 12,
        est_revenue_at_risk: 22495,
        urgency_days: 3,
        brief:
          "Shoppers asking for AeroRun today are hitting stockouts and accepting substitutes — protect TG-882 inventory and consider express transfer from Koramangala.",
        recommended_action: "Transfer 6 units of RN-210 from Koramangala today",
        generated_at: generatedAt,
      },
    ],
  };
}

export async function mockListInsights(): Promise<GenerateInsightsResponse> {
  return {
    insights: [],
    generated_at: new Date().toISOString(),
    event_count_processed: 0,
  };
}

export async function mockAssessReturn(
  req: ReturnAssessRequest,
): Promise<ReturnAssessment> {
  await delay(650);
  void req;
  return {
    assessment_id: createId("asmt"),
    condition: "lightly_used",
    condition_justification:
      "Minor creasing on the toe box; sole wear consistent with short indoor use. No structural damage visible.",
    return_risk_tier: "medium",
    risk_factors: ["rapid_return", "missing_tags"],
    recommended_disposition: "refurbish_and_relist",
    requires_confirmation: true,
  };
}

export async function mockConfirmReturn(
  req: ReturnConfirmRequest,
): Promise<ReturnConfirmResponse> {
  await delay(320);
  return {
    assessment_id: req.assessment_id,
    status: req.override ? "overridden" : "confirmed",
    disposition: req.disposition,
    message: req.override
      ? "Override recorded. Item held for manager review before inventory update."
      : "Disposition confirmed. Inventory workflow queued — no automatic restock without confirmation.",
  };
}
