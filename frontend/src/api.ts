export type Product = {
  id: number;
  title: string;
  description: string;
  category: string;
  age: string;
  kind: "digital" | "physical";
  price: number;
  image: string | null;
};
export type Cart = {
  items: { product: Product; quantity: number }[];
  total: number;
};
export type Catalog = {
  products: Product[];
  total: number;
  page: number;
  pages: number;
};
export type Checkout = Cart & {
  checkout_key: string;
  methods: [string, string, string][];
};
export type Bootstrap = {
  store: Record<string, string>;
  csrf: string;
  cart: Cart;
  catalog: Catalog;
  categories: string[];
  whatsapp: string;
  consent: boolean | null;
  admin: boolean;
  revision: string;
  product?: Product;
  featured?: Product[];
  checkout?: Checkout;
};
export const money = (cents: number) =>
  new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" }).format(
    cents / 100,
  );
export class RequestError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function request<T>(
  url: string,
  csrf: string,
  body?: FormData,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(url, {
    method: body ? "POST" : "GET",
    body,
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(body ? { "X-CSRFToken": csrf } : {}),
    },
    signal: signal
      ? AbortSignal.any([signal, AbortSignal.timeout(20000)])
      : AbortSignal.timeout(20000),
  });
  const json = await response.json().catch(() => null);
  if (!response.ok)
    throw new RequestError(
      json?.error ||
        "No pudimos completar la operación. Revisá tu conexión y volvé a intentar.",
      response.status,
    );
  return json;
}
export function nextCart(
  cart: Cart,
  p: Product,
  action: "add" | "remove" | "quantity",
  quantity?: number,
): Cart {
  const items = cart.items.filter((row) => row.product.id !== p.id);
  const previous =
    cart.items.find((row) => row.product.id === p.id)?.quantity || 0;
  if (action !== "remove")
    items.push({
      product: p,
      quantity:
        p.kind === "digital"
          ? 1
          : Math.max(1, Math.min(10, quantity ?? previous + 1)),
    });
  return {
    items,
    total: items.reduce(
      (sum, row) => sum + row.product.price * row.quantity,
      0,
    ),
  };
}
