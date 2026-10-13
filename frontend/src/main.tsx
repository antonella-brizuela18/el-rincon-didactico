import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App } from "./App";
import type { Bootstrap } from "./api";
import "./storefront.css";
const data = JSON.parse(
  document.getElementById("rincon-bootstrap")!.textContent!,
) as Bootstrap;
const client = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 120000,
      gcTime: 600000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});
client.setQueryData(["cart"], data.cart);
client.setQueryData(["catalog", window.location.search.slice(1)], data.catalog);
for (const p of data.catalog.products)
  client.setQueryData(["product", p.id], p);
if (data.checkout)
  client.setQueryData(
    [
      "checkout",
      JSON.stringify(data.cart.items.map((i) => [i.product.id, i.quantity])),
    ],
    data.checkout,
  );
if (data.product)
  client.setQueryData(["product", data.product.id], data.product);
// The existing page remains usable until the JS bundle has actually loaded.
document.getElementById("rincon-fallback")?.remove();
createRoot(document.getElementById("rincon-react")!).render(
  <QueryClientProvider client={client}>
    <BrowserRouter>
      <App bootstrap={data} />
    </BrowserRouter>
  </QueryClientProvider>,
);
