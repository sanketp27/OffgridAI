import { z } from "zod";

export const MatchQualitySchema = z.enum(["exact", "near", "miss"]);
export type MatchQuality = z.infer<typeof MatchQualitySchema>;

export const SearchResultSchema = z.object({
  sku_id: z.string(),
  name: z.string(),
  price: z.number(),
  currency: z.string(),
  image_url: z.string(),
  match_score: z.number(),
  match_explanation: z.string(),
  match_quality: MatchQualitySchema,
});
export type SearchResult = z.infer<typeof SearchResultSchema>;

export const FitCheckPromptSchema = z.object({
  triggered: z.boolean(),
  sku_id: z.string().nullable().optional(),
  question: z.string().nullable().optional(),
});
export type FitCheckPrompt = z.infer<typeof FitCheckPromptSchema>;

export const RescueOptionSchema = z.object({
  option_id: z.string(),
  type: z.enum(["substitute", "nearby_store", "ship"]),
  sku_id: z.string().nullable().optional(),
  name: z.string(),
  price: z.number().nullable().optional(),
  currency: z.string().optional(),
  image_url: z.string().nullable().optional(),
  tradeoff: z.string(),
});
export type RescueOption = z.infer<typeof RescueOptionSchema>;

export const StockoutRescueSchema = z.object({
  triggered: z.boolean(),
  preferred_sku_id: z.string(),
  preferred_name: z.string(),
  reason: z.string(),
  options: z.array(RescueOptionSchema),
});
export type StockoutRescue = z.infer<typeof StockoutRescueSchema>;

export const SearchRequestSchema = z.object({
  session_id: z.string().nullable().optional(),
  query_text: z.string().optional(),
  image_base64: z.string().nullable().optional(),
  store_id: z.string(),
  platform: z.string(),
});
export type SearchRequest = z.infer<typeof SearchRequestSchema>;

export const SearchResponseSchema = z.object({
  session_id: z.string(),
  results: z.array(SearchResultSchema),
  fit_check: FitCheckPromptSchema,
  rescue: StockoutRescueSchema.nullable().optional(),
  event_id: z.string(),
});
export type SearchResponse = z.infer<typeof SearchResponseSchema>;

export const FitCheckRequestSchema = z.object({
  session_id: z.string(),
  sku_id: z.string(),
  response_text: z.string(),
  event_id: z.string(),
});
export type FitCheckRequest = z.infer<typeof FitCheckRequestSchema>;

export const FitCheckResponseSchema = z.object({
  resolution: z.string(),
  new_sku_id: z.string().nullable().optional(),
  cart_updated: z.boolean(),
  event_id: z.string(),
});
export type FitCheckResponse = z.infer<typeof FitCheckResponseSchema>;

export const SignalTypeSchema = z.enum([
  "stock_gap",
  "unmet_demand",
  "fit_issue",
  "price_gap",
  "discoverability",
  "other",
]);
export type SignalType = z.infer<typeof SignalTypeSchema>;

export const InsightSchema = z.object({
  insight_id: z.string(),
  signal_type: SignalTypeSchema.or(z.string()),
  label: z.string(),
  occurrences: z.number(),
  unique_shoppers: z.number(),
  trend_pct: z.number().nullable().optional(),
  est_revenue_at_risk: z.number(),
  urgency_days: z.number().nullable().optional(),
  brief: z.string(),
  recommended_action: z.string(),
  generated_at: z.string(),
});
export type Insight = z.infer<typeof InsightSchema>;

export const GenerateInsightsRequestSchema = z.object({
  store_id: z.string(),
  time_window_days: z.number().int().positive(),
});
export type GenerateInsightsRequest = z.infer<
  typeof GenerateInsightsRequestSchema
>;

export const GenerateInsightsResponseSchema = z.object({
  insights: z.array(InsightSchema),
  generated_at: z.string(),
  event_count_processed: z.number(),
});
export type GenerateInsightsResponse = z.infer<
  typeof GenerateInsightsResponseSchema
>;

export const CatalogItemSchema = z.object({
  sku_id: z.string(),
  name: z.string(),
  price: z.number(),
  currency: z.string(),
  image_url: z.string(),
  category: z.string(),
  return_prone: z.boolean().optional(),
});
export type CatalogItem = z.infer<typeof CatalogItemSchema>;

export const ReturnAssessmentSchema = z.object({
  assessment_id: z.string(),
  condition: z.string(),
  condition_justification: z.string(),
  return_risk_tier: z.string(),
  risk_factors: z.array(z.string()),
  recommended_disposition: z.string(),
  requires_confirmation: z.boolean(),
});
export type ReturnAssessment = z.infer<typeof ReturnAssessmentSchema>;

export const ReturnAssessRequestSchema = z.object({
  order_id: z.string().min(1),
  store_id: z.string(),
  image_base64: z.string().min(1),
});
export type ReturnAssessRequest = z.infer<typeof ReturnAssessRequestSchema>;

export const ReturnConfirmRequestSchema = z.object({
  assessment_id: z.string(),
  disposition: z.string(),
  override: z.boolean().optional(),
});
export type ReturnConfirmRequest = z.infer<typeof ReturnConfirmRequestSchema>;

export const ReturnConfirmResponseSchema = z.object({
  assessment_id: z.string(),
  status: z.enum(["confirmed", "overridden", "held"]),
  disposition: z.string(),
  message: z.string(),
});
export type ReturnConfirmResponse = z.infer<typeof ReturnConfirmResponseSchema>;
