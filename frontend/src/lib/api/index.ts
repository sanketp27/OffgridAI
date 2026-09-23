import { API_CONFIG } from "@/config/api";
import { apiFetch } from "@/lib/api/client";
import {
  mockAssessReturn,
  mockConfirmReturn,
  mockFitCheck,
  mockGenerateInsights,
  mockListInsights,
  mockSearch,
} from "@/lib/api/mock/handlers";
import { getFeaturedCatalog } from "@/lib/api/mock/catalog";
import {
  FitCheckRequestSchema,
  FitCheckResponseSchema,
  GenerateInsightsRequestSchema,
  GenerateInsightsResponseSchema,
  ReturnAssessRequestSchema,
  ReturnAssessmentSchema,
  ReturnConfirmRequestSchema,
  ReturnConfirmResponseSchema,
  SearchRequestSchema,
  SearchResponseSchema,
  type CatalogItem,
  type FitCheckRequest,
  type FitCheckResponse,
  type GenerateInsightsRequest,
  type GenerateInsightsResponse,
  type ReturnAssessRequest,
  type ReturnAssessment,
  type ReturnConfirmRequest,
  type ReturnConfirmResponse,
  type SearchRequest,
  type SearchResponse,
} from "@/lib/api/types";

export async function searchProducts(
  input: Omit<SearchRequest, "store_id" | "platform"> &
    Partial<Pick<SearchRequest, "store_id" | "platform">>,
): Promise<SearchResponse> {
  const req = SearchRequestSchema.parse({
    store_id: API_CONFIG.defaultStoreId,
    platform: API_CONFIG.platform,
    ...input,
  });

  if (API_CONFIG.useMock) {
    return SearchResponseSchema.parse(await mockSearch(req));
  }

  return apiFetch("/search", {
    method: "POST",
    body: JSON.stringify(req),
    parse: (data) => SearchResponseSchema.parse(data),
  });
}

export async function submitFitCheck(
  input: FitCheckRequest,
): Promise<FitCheckResponse> {
  const req = FitCheckRequestSchema.parse(input);

  if (API_CONFIG.useMock) {
    return FitCheckResponseSchema.parse(await mockFitCheck(req));
  }

  return apiFetch("/fit-check", {
    method: "POST",
    body: JSON.stringify(req),
    parse: (data) => FitCheckResponseSchema.parse(data),
  });
}

export async function listInsights(
  storeId = API_CONFIG.defaultStoreId,
): Promise<GenerateInsightsResponse> {
  if (API_CONFIG.useMock) {
    return GenerateInsightsResponseSchema.parse(await mockListInsights());
  }

  return apiFetch(`/insights?store_id=${encodeURIComponent(storeId)}`, {
    method: "GET",
    parse: (data) => GenerateInsightsResponseSchema.parse(data),
  });
}

export async function generateInsights(
  input: Partial<GenerateInsightsRequest> = {},
): Promise<GenerateInsightsResponse> {
  const req = GenerateInsightsRequestSchema.parse({
    store_id: API_CONFIG.defaultStoreId,
    time_window_days: 7,
    ...input,
  });

  if (API_CONFIG.useMock) {
    return GenerateInsightsResponseSchema.parse(await mockGenerateInsights(req));
  }

  return apiFetch("/insights/generate", {
    method: "POST",
    body: JSON.stringify(req),
    parse: (data) => GenerateInsightsResponseSchema.parse(data),
  });
}

export async function assessReturn(
  input: Omit<ReturnAssessRequest, "store_id"> &
    Partial<Pick<ReturnAssessRequest, "store_id">>,
): Promise<ReturnAssessment> {
  const req = ReturnAssessRequestSchema.parse({
    store_id: API_CONFIG.defaultStoreId,
    ...input,
  });

  if (API_CONFIG.useMock) {
    return ReturnAssessmentSchema.parse(await mockAssessReturn(req));
  }

  return apiFetch("/return", {
    method: "POST",
    body: JSON.stringify(req),
    parse: (data) => ReturnAssessmentSchema.parse(data),
  });
}

export async function confirmReturn(
  input: ReturnConfirmRequest,
): Promise<ReturnConfirmResponse> {
  const req = ReturnConfirmRequestSchema.parse(input);

  if (API_CONFIG.useMock) {
    return ReturnConfirmResponseSchema.parse(await mockConfirmReturn(req));
  }

  return apiFetch(`/return/${encodeURIComponent(req.assessment_id)}/confirm`, {
    method: "POST",
    body: JSON.stringify(req),
    parse: (data) => ReturnConfirmResponseSchema.parse(data),
  });
}

export async function getCatalog(): Promise<CatalogItem[]> {
  if (API_CONFIG.useMock) {
    await new Promise((r) => setTimeout(r, 120));
    return getFeaturedCatalog();
  }

  return apiFetch("/catalog", {
    method: "GET",
    parse: (data) => data as CatalogItem[],
  });
}

export { API_CONFIG };
export type * from "@/lib/api/types";
