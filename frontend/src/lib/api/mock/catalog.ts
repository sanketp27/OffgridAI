import type { CatalogItem } from "@/lib/api/types";

/** Seed catalog — curated local product art under /public/products */
export const MOCK_CATALOG: CatalogItem[] = [
  {
    sku_id: "TG-882",
    name: "TrailGrip Hiking Boot",
    price: 3799,
    currency: "INR",
    image_url: "/products/tg-882.svg",
    category: "footwear",
    return_prone: true,
  },
  {
    sku_id: "TG-882-9.5",
    name: "TrailGrip Hiking Boot · Size 9.5",
    price: 3799,
    currency: "INR",
    image_url: "/products/tg-882-95.svg",
    category: "footwear",
    return_prone: true,
  },
  {
    sku_id: "WP-441",
    name: "RidgeLine Waterproof Boot",
    price: 4499,
    currency: "INR",
    image_url: "/products/wp-441.svg",
    category: "footwear",
    return_prone: true,
  },
  {
    sku_id: "RN-210",
    name: "AeroRun Trainer",
    price: 2999,
    currency: "INR",
    image_url: "/products/rn-210.svg",
    category: "footwear",
    return_prone: true,
  },
  {
    sku_id: "CH-118",
    name: "Harbor Cotton Crew",
    price: 1299,
    currency: "INR",
    image_url: "/products/ch-118.svg",
    category: "apparel",
    return_prone: true,
  },
  {
    sku_id: "LK-055",
    name: "Nordic Desk Lamp",
    price: 2499,
    currency: "INR",
    image_url: "/products/lk-055.svg",
    category: "home",
    return_prone: false,
  },
  {
    sku_id: "ST-033",
    name: "Clay Stoneware Mug Set",
    price: 899,
    currency: "INR",
    image_url: "/products/st-033.svg",
    category: "home",
    return_prone: false,
  },
  {
    sku_id: "BG-901",
    name: "Summit Daypack 20L",
    price: 3299,
    currency: "INR",
    image_url: "/products/bg-901.svg",
    category: "gear",
    return_prone: false,
  },
];

export function getFeaturedCatalog(limit = 8): CatalogItem[] {
  return MOCK_CATALOG.filter((i) => !i.sku_id.includes("-9.5")).slice(0, limit);
}
