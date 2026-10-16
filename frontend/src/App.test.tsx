import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App } from "./App";
import { nextCart, type Bootstrap, type Product } from "./api";
const p: Product = {
  id: 1,
  title: "Colores para jugar",
  description: "Un imprimible de colores.",
  category: "Colores",
  age: "Sala de 3",
  kind: "digital",
  price: 123456,
  image: null,
};
const physical: Product = {
  ...p,
  id: 2,
  title: "Juego de tela",
  kind: "physical",
  price: 200000,
};
const boot: Bootstrap = {
  store: {
    brand_name: "El Rincón Didáctico",
    brand_tagline: "Aprender jugando",
    hero_eyebrow: "Ideas para crecer",
    hero_title: "Aprender empieza jugando",
    hero_text: "Recursos para el aula",
    hero_cta: "Explorar recursos",
    hero_note: "Hecho con amor",
    featured_ids: "",
    default_mode: "light",
    show_categories: "1",
    preparation_days: "10",
    delivery_note: "Envío aparte",
    checkout_enabled: "1",
    instagram: "elrincondidactico_",
    analytics_enabled: "0",
    whatsapp_label: "Consultanos",
  },
  csrf: "csrf-test",
  cart: { items: [], total: 0 },
  catalog: { products: [p, physical], total: 2, page: 1, pages: 1 },
  categories: ["Colores"],
  whatsapp: "https://wa.me/5492915090223",
  consent: false,
  admin: false,
  revision: "development",
};
let client: QueryClient;
function mount(path = "/catalogo", b = boot) {
  client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  client.setQueryData(["cart"], b.cart);
  client.setQueryData(["catalog", ""], b.catalog);
  for (const product of b.catalog.products)
    client.setQueryData(["product", product.id], product);
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App bootstrap={b} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  vi.stubGlobal("matchMedia", () => ({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
  vi.stubGlobal("scrollTo", vi.fn());
  vi.stubGlobal("fetch", vi.fn());
  localStorage.clear();
});
afterEach(() => {
  cleanup();
  client?.clear();
  vi.unstubAllGlobals();
});
describe("cached storefront navigation", () => {
  it("opens catalog and a product without requesting HTML or JSON again", async () => {
    mount();
    fireEvent.click(screen.getAllByText("Colores para jugar")[0]);
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Colores para jugar",
      }),
    ).toBeTruthy();
    expect(fetch).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Volver al catálogo"));
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Recursos para aprender jugando",
      }),
    ).toBeTruthy();
    expect(fetch).not.toHaveBeenCalled();
    expect(screen.queryByText("Cargando…")).toBeNull();
  });
  it("updates the cart immediately and reconciles the authoritative server total", async () => {
    let resolve!: (value: Response) => void;
    vi.mocked(fetch).mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }) as Promise<Response>,
    );
    mount();
    fireEvent.click(
      screen.getAllByRole("button", { name: /Agregar al carrito/ })[0],
    );
    await waitFor(() =>
      expect(client.getQueryData<{ total: number }>(["cart"])?.total).toBe(
        123456,
      ),
    );
    expect(
      screen
        .getAllByRole("button", { name: /Agregar al carrito/ })[0]
        .hasAttribute("disabled"),
    ).toBe(true);
    expect(screen.getByRole("button", { name: "Agregando…" }).getAttribute("aria-busy")).toBe("true");
    expect(screen.getByText("Agregando al carrito")).toBeTruthy();
    resolve(
      new Response(
        JSON.stringify({
          items: [{ product: p, quantity: 1 }],
          total: 125000,
          messages: ["Agregado"],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    await waitFor(() =>
      expect(client.getQueryData<{ total: number }>(["cart"])?.total).toBe(
        125000,
      ),
    );
    expect(await screen.findByText("Agregado a tu carrito")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Ver mi carrito/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cerrar aviso" }));
    expect(screen.queryByText("Agregado a tu carrito")).toBeNull();
    expect(vi.mocked(fetch).mock.calls[0][1]?.headers).toEqual(
      expect.objectContaining({ "X-CSRFToken": "csrf-test" }),
    );
  });
  it("rolls back a failed cart write and does not repeat the POST", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ error: "Sesión vencida" }), {
          status: 400,
        }),
      )
      .mockResolvedValue(
        new Response(JSON.stringify(boot.cart), { status: 200 }),
      );
    mount();
    fireEvent.click(
      screen.getAllByRole("button", { name: /Agregar al carrito/ })[0],
    );
    expect(await screen.findByRole("alert")).toBeTruthy();
    await waitFor(() =>
      expect(client.getQueryData<{ total: number }>(["cart"])?.total).toBe(0),
    );
    expect(
      vi
        .mocked(fetch)
        .mock.calls.filter(([, options]) => options?.method === "POST"),
    ).toHaveLength(1);
  });
  it("uses server checkout key and payment options rather than deriving payment from client prices", async () => {
    const cart = { items: [{ product: p, quantity: 1 }], total: p.price };
    vi.mocked(fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          ...cart,
          checkout_key: "server-key",
          methods: [
            ["transfer", "Transferencia bancaria", "Confirmación manual"],
          ],
        }),
        { status: 200 },
      ),
    );
    mount("/pedido/nuevo", { ...boot, cart });
    expect(await screen.findByText("Transferencia bancaria")).toBeTruthy();
    const key = document.querySelector<HTMLInputElement>(
      'input[name="checkout_key"]',
    );
    expect(key?.value).toBe("server-key");
    expect(screen.getByRole("button", { name: /Crear pedido/ })).toBeTruthy();
  });
});
describe("catalog category shortcuts", () => {
  it("filters by category and clears both filters and the search field", async () => {
    mount();
    client.setQueryData(["catalog", "categoria=Colores"], { ...boot.catalog, products: [p], total: 1 });
    fireEvent.click(screen.getByRole("button", { name: "Colores" }));
    expect(await screen.findByRole("button", { name: "Colores", pressed: true })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Juego de tela" })).toBeNull();
    fireEvent.change(screen.getByPlaceholderText("¿Qué te gustaría encontrar?"), { target: { value: "otra idea" } });
    fireEvent.click(screen.getByRole("button", { name: "Limpiar filtros ×" }));
    expect((screen.getByPlaceholderText("¿Qué te gustaría encontrar?") as HTMLInputElement).value).toBe("");
    expect(await screen.findByRole("heading", { name: "Juego de tela" })).toBeTruthy();
    expect(fetch).not.toHaveBeenCalled();
  });
});
describe("cart limits", () => {
  it("keeps digital quantity at one and physical quantity at ten", () => {
    expect(
      nextCart(
        { items: [{ product: p, quantity: 1 }], total: p.price },
        p,
        "add",
      ).items[0].quantity,
    ).toBe(1);
    expect(
      nextCart(
        { items: [{ product: physical, quantity: 10 }], total: 2000000 },
        physical,
        "add",
      ).items[0].quantity,
    ).toBe(10);
  });
});
