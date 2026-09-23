"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { SearchResult } from "@/lib/api";

export type CartLine = {
  sku_id: string;
  name: string;
  price: number;
  currency: string;
  image_url: string;
};

type SessionState = {
  sessionId: string | null;
  lastEventId: string | null;
  cart: CartLine[];
  setSession: (sessionId: string, eventId: string) => void;
  setLastEventId: (eventId: string) => void;
  addToCart: (item: SearchResult | CartLine) => void;
  replaceInCart: (fromSkuId: string, item: CartLine) => void;
  clearCart: () => void;
};

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [lastEventId, setLastEventIdState] = useState<string | null>(null);
  const [cart, setCart] = useState<CartLine[]>([]);

  const setSession = useCallback((id: string, eventId: string) => {
    setSessionId(id);
    setLastEventIdState(eventId);
  }, []);

  const setLastEventId = useCallback((eventId: string) => {
    setLastEventIdState(eventId);
  }, []);

  const addToCart = useCallback((item: SearchResult | CartLine) => {
    setCart((prev) => {
      const withoutDup = prev.filter((p) => p.sku_id !== item.sku_id);
      return [
        ...withoutDup,
        {
          sku_id: item.sku_id,
          name: item.name,
          price: item.price,
          currency: item.currency,
          image_url: item.image_url,
        },
      ];
    });
  }, []);

  const replaceInCart = useCallback((fromSkuId: string, item: CartLine) => {
    setCart((prev) => {
      const next = prev.filter(
        (p) => p.sku_id !== fromSkuId && p.sku_id !== item.sku_id,
      );
      return [...next, item];
    });
  }, []);

  const clearCart = useCallback(() => setCart([]), []);

  const value = useMemo(
    () => ({
      sessionId,
      lastEventId,
      cart,
      setSession,
      setLastEventId,
      addToCart,
      replaceInCart,
      clearCart,
    }),
    [
      sessionId,
      lastEventId,
      cart,
      setSession,
      setLastEventId,
      addToCart,
      replaceInCart,
      clearCart,
    ],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}
