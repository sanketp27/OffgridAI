export const API_CONFIG = {
  baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
  useMock: (process.env.NEXT_PUBLIC_USE_MOCK_API ?? "true") === "true",
  defaultStoreId: "store_001",
  platform: "web_widget" as const,
} as const;
