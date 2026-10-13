import {
  useEffect,
  useRef,
  useState,
  createContext,
  useContext,
  type ReactNode,
} from "react";
import {
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router-dom";
import {
  useMutation,
  useQuery,
  useQueryClient,
  useIsMutating,
} from "@tanstack/react-query";
import {
  ArrowRight,
  Check,
  ChevronLeft,
  Flower2,
  House,
  ShoppingBag,
  Search,
  Sun,
  Moon,
  Trash2,
  Plus,
  Minus,
  Download,
  Package,
  Instagram,
  ShieldCheck,
} from "lucide-react";
import {
  request,
  money,
  nextCart,
  type Bootstrap,
  type Cart,
  type Catalog,
  type Checkout,
  type Product,
} from "./api";
const Context = createContext<Bootstrap>(null!);
const useBoot = () => useContext(Context);
export function CatalogCard({
  product: p,
  onAdd,
  busy,
}: {
  product: Product;
  onAdd: (p: Product) => void;
  busy: boolean;
}) {
  return (
    <article className="r-card">
      <Link to={`/producto/${p.id}`} className="r-card-image">
        {p.image ? (
          <img
            src={p.image}
            alt={p.title}
            width="600"
            height="450"
            loading="lazy"
          />
        ) : (
          <Flower2 size={80} strokeWidth={1} />
        )}
        <span>
          {p.kind === "digital" ? "Imprimible digital" : "Material por encargo"}
        </span>
      </Link>
      <div className="r-card-copy">
        <small>{p.category}</small>
        <h3>
          <Link to={`/producto/${p.id}`}>{p.title}</Link>
        </h3>
        <p>{p.age || "Para aprender jugando"}</p>
        <strong>
          {money(p.price)} <small>ARS</small>
        </strong>
        <button className="r-button" onClick={() => onAdd(p)} disabled={busy}>
          <Plus size={18} /> Agregar al carrito
        </button>
        <Link className="r-detail-link" to={`/producto/${p.id}`}>
          Ver qué incluye <ArrowRight size={16} />
        </Link>
      </div>
    </article>
  );
}
function Skeleton() {
  return (
    <div
      className="r-skeleton"
      aria-label="Preparando contenido"
      aria-busy="true"
    >
      <div />
      <div />
      <div />
    </div>
  );
}
function ErrorBox({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div className="r-error" role="alert">
      <p>{error instanceof Error ? error.message : "Algo salió mal."}</p>
      {retry && (
        <button className="r-button" onClick={retry}>
          Volver a intentar
        </button>
      )}
    </div>
  );
}
function Steps({ current }: { current: number }) {
  return (
    <ol className="r-steps">
      {["Tu selección", "Datos y pago", "Tu pedido"].map((name, i) => (
        <li key={name} aria-current={i === current ? "step" : undefined}>
          <b>{i + 1}</b>
          <span>{name}</span>
        </li>
      ))}
    </ol>
  );
}
function HowTo() {
  return (
    <section className="r-how" id="como-comprar">
      <small className="r-eyebrow">DE TU IDEA A SUS MANOS</small>
      <h2>Elegir. Crear. Aprender.</h2>
      <div>
        {[
          [
            "01",
            "Encontrá tu recurso",
            "Explorá el formato, la edad y todo lo que incluye.",
          ],
          [
            "02",
            "Hacé tu pedido",
            "Completá tus datos y elegí cómo pagar. Sin registrarte.",
          ],
          [
            "03",
            "Empezá a jugar",
            "Descargá tus archivos después del pago o coordiná la entrega de tu material.",
          ],
        ].map(([n, t, d]) => (
          <article key={n}>
            <b>{n}</b>
            <h3>{t}</h3>
            <p>{d}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
function useCart() {
  const b = useBoot();
  return useQuery({
    queryKey: ["cart"],
    queryFn: ({ signal }) =>
      request<Cart>("/api/carrito", b.csrf, undefined, signal),
    initialData: b.cart,
    staleTime: 60000,
  });
}
function useCartActions() {
  const b = useBoot(),
    client = useQueryClient();
  const pending = useIsMutating({ mutationKey: ["cart-write"] }) > 0;
  const mutation = useMutation({
    mutationKey: ["cart-write"],
    scope: { id: "cart-write" },
    mutationFn: async ({
      p,
      action,
      quantity,
    }: {
      p: Product;
      action: "add" | "remove" | "quantity";
      quantity?: number;
    }) => {
      const form = new FormData();
      if (quantity) form.set("quantity", String(quantity));
      return request<Cart & { messages: string[] }>(
        `/carrito/${{ add: "agregar", remove: "quitar", quantity: "cantidad" }[action]}/${p.id}`,
        b.csrf,
        form,
      );
    },
    retry: false,
    onMutate: async ({ p, action, quantity }) => {
      await client.cancelQueries({ queryKey: ["cart"] });
      const before = client.getQueryData<Cart>(["cart"])!;
      client.setQueryData(["cart"], nextCart(before, p, action, quantity));
      return { before };
    },
    onSuccess: (value) => {
      client.setQueryData(["cart"], value);
      client.removeQueries({ queryKey: ["checkout"] });
    },
    onError: (_e, _v, context) => {
      if (context) client.setQueryData(["cart"], context.before);
      void client.invalidateQueries({ queryKey: ["cart"] });
    },
  });
  return { ...mutation, isPending: pending || mutation.isPending };
}
function Shop({ home = false }: { home?: boolean }) {
  const b = useBoot(),
    client = useQueryClient(),
    [params, setParams] = useSearchParams(),
    actions = useCartActions();
  const [notice, setNotice] = useState("");
  const searchKey = params.toString();
  const query = useQuery({
    queryKey: ["catalog", searchKey],
    queryFn: ({ signal }) =>
      request<Catalog>(`/api/catalogo?${searchKey}`, b.csrf, undefined, signal),
    staleTime: 120000,
    placeholderData: (previous) => previous,
  });
  const [search, setSearch] = useState(params.get("q") || "");
  useEffect(() => setSearch(params.get("q") || ""), [searchKey]);
  useEffect(() => {
    if (query.data)
      for (const p of query.data.products)
        client.setQueryData(["product", p.id], p);
  }, [query.data, client]);
  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    next.delete("pagina");
    value ? next.set(key, value) : next.delete(key);
    setParams(next);
  };
  const products = query.data?.products || [];
  const featured = b.store.featured_ids?.split(",").map(Number) || [];
  const visible =
    home && featured.filter(Boolean).length
      ? b.featured || products.filter((p) => featured.includes(p.id))
      : products;
  const add = (p: Product) =>
    actions.mutate(
      { p, action: "add" },
      {
        onSuccess: (value) =>
          setNotice(value.messages?.[0] || "Agregado al carrito"),
      },
    );
  return (
    <>
      {home ? (
        <section className="r-hero">
          <div>
            <span className="r-pill">
              <Flower2 size={16} />
              {b.store.hero_eyebrow}
            </span>
            <h1>{b.store.hero_title}</h1>
            <p>{b.store.hero_text}</p>
            <Link className="r-button" to="/catalogo">
              {b.store.hero_cta}
              <ArrowRight size={20} />
            </Link>
            <a className="r-text-link" href="#como-comprar">
              Cómo comprar
            </a>
            <small>{b.store.hero_note}</small>
          </div>
          <div className="r-hero-art">
            {b.store.hero_image ? (
              <img
                src={`/imagenes/${b.store.hero_image}`}
                alt={b.store.brand_name}
                width="620"
                height="560"
              />
            ) : products[0]?.image ? (
              <Link to={`/producto/${products[0].id}`}>
                <img
                  src={products[0].image}
                  alt={products[0].title}
                  width="620"
                  height="560"
                />
                <span>
                  {products[0].title} <ArrowRight size={20} />
                </span>
              </Link>
            ) : (
              <>
                <Flower2 size={140} strokeWidth={1} />
                <h2>
                  El juego es
                  <br />
                  el comienzo.
                </h2>
                <p>Imaginar · Crear · Aprender</p>
              </>
            )}
          </div>
        </section>
      ) : (
        <section className="r-page-intro">
          <small className="r-eyebrow">UN MUNDO POR DESCUBRIR</small>
          <h1>Recursos para aprender jugando</h1>
          <p>Una nueva idea para el aula, para casa y para cada etapa.</p>
        </section>
      )}
      {home && b.store.show_benefits === "1" && (
        <div className="r-benefits">
          <span>
            <Download size={20} /> Imprimibles digitales
          </span>
          <span>
            <Package size={20} /> Materiales por encargo
          </span>
          <span>
            <ShieldCheck size={20} /> Comprás sin registro
          </span>
        </div>
      )}
      <section className="r-catalog" id="catalogo">
        <div className="r-section-heading">
          <div>
            <small className="r-eyebrow">ELEGÍ TU PRÓXIMA IDEA</small>
            <h2>{home ? "Elegidos para vos" : "Encontrá tu recurso"}</h2>
            <p>{query.data?.total ?? b.catalog.total} recursos disponibles</p>
          </div>
          <div className="r-tabs">
            {[
              ["", "Todos"],
              ["digital", "Imprimibles"],
              ["physical", "Materiales"],
            ].map(([value, label]) => (
              <button
                key={value}
                aria-pressed={(params.get("tipo") || "") === value}
                onClick={() => setFilter("tipo", value)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <form
          className="r-filters"
          onSubmit={(e) => {
            e.preventDefault();
            setFilter("q", search);
          }}
        >
          <label className="r-search">
            <span className="sr-only">Buscar un recurso</span>
            <Search size={20} />
            <input
              type="search"
              placeholder="¿Qué te gustaría encontrar?"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <button aria-label="Buscar" type="submit">
              <ArrowRight size={20} />
            </button>
          </label>
          {b.store.show_categories === "1" && (
            <label>
              <span className="sr-only">Categoría</span>
              <select
                value={params.get("categoria") || ""}
                onChange={(e) => setFilter("categoria", e.target.value)}
              >
                <option value="">Todas las categorías</option>
                {b.categories.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
          )}
          <label>
            <span className="sr-only">Ordenar</span>
            <select
              value={params.get("orden") || "recent"}
              onChange={(e) => setFilter("orden", e.target.value)}
            >
              <option value="recent">Más recientes</option>
              <option value="price_asc">Menor precio</option>
              <option value="price_desc">Mayor precio</option>
              <option value="title">Nombre A–Z</option>
            </select>
          </label>
        </form>
        {searchKey && (
          <button className="r-text-link" onClick={() => setParams({})}>
            Limpiar filtros ×
          </button>
        )}
        {query.isError ? (
          <ErrorBox error={query.error} retry={() => void query.refetch()} />
        ) : !query.data ? (
          <Skeleton />
        ) : (
          <div className={`r-products ${query.isFetching ? "r-updating" : ""}`}>
            {visible.map((p) => (
              <CatalogCard
                key={p.id}
                product={p}
                onAdd={add}
                busy={actions.isPending}
              />
            ))}
            {!visible.length && (
              <div className="r-empty">
                <Flower2 size={48} />
                <h3>
                  {searchKey
                    ? "No encontramos recursos con esos filtros."
                    : "Estamos preparando nuestros recursos."}
                </h3>
                <p>
                  {searchKey
                    ? "Probá otra búsqueda."
                    : "Pronto vas a encontrar nuevas ideas en este rincón."}
                </p>
              </div>
            )}
          </div>
        )}
        {query.data && query.data.pages > 1 && (
          <nav className="r-pagination" aria-label="Páginas">
            {query.data.page > 1 && (
              <button
                onClick={() =>
                  setFilter("pagina", String(query.data!.page - 1))
                }
              >
                Anterior
              </button>
            )}
            <span>
              {query.data.page} de {query.data.pages}
            </span>
            {query.data.page < query.data.pages && (
              <button
                onClick={() =>
                  setFilter("pagina", String(query.data!.page + 1))
                }
              >
                Siguiente
              </button>
            )}
          </nav>
        )}
        {actions.isError && <ErrorBox error={actions.error} />}
      </section>
      {notice && (
        <div className="r-toast" role="status">
          <Check size={20} />
          <span>Agregado al carrito</span>
          <Link to="/carrito">Ver carrito →</Link>
          <button onClick={() => setNotice("")} aria-label="Cerrar aviso">
            ×
          </button>
        </div>
      )}
      <HowTo />
      {b.store.show_faq === "1" && (
        <section className="r-faq">
          <h2>Antes de comprar</h2>
          {[
            [
              "¿Necesito registrarme?",
              "No. Comprás como invitado y recibís un enlace privado para seguir tu pedido.",
            ],
            [
              "¿Cuándo recibo mis archivos?",
              "Después de la acreditación del pago. Podés descargarlos durante 7 días y guardarlos.",
            ],
            ["¿El precio incluye envío?", b.store.delivery_note],
            [
              "¿Cuánto tarda un material por encargo?",
              `Aproximadamente ${b.store.preparation_days} días desde el pago, más el tránsito del correo.`,
            ],
          ].map(([t, d]) => (
            <details key={t}>
              <summary>{t}</summary>
              <p>{d}</p>
            </details>
          ))}
        </section>
      )}
      {b.store.show_story === "1" && (
        <section className="r-story">
          <Flower2 size={36} />
          <h2>{b.store.story_title}</h2>
          <p>{b.store.story_text}</p>
        </section>
      )}
    </>
  );
}
function ProductPage() {
  const b = useBoot(),
    location = useLocation(),
    navigate = useNavigate(),
    id = Number(location.pathname.split("/").pop()),
    actions = useCartActions();
  const [added, setAdded] = useState(false);
  const query = useQuery({
    queryKey: ["product", id],
    queryFn: ({ signal }) =>
      request<Product>(`/api/producto/${id}`, b.csrf, undefined, signal),
    staleTime: 120000,
  });
  useEffect(() => setAdded(false), [id]);
  const p = query.data;
  useEffect(() => {
    if (p) {
      document.title = p.title + " · " + b.store.brand_name;
      const description = document.querySelector<HTMLMetaElement>(
        'meta[name="description"]',
      );
      if (description) description.content = p.description.slice(0, 180);
      const og = document.querySelector<HTMLMetaElement>(
        'meta[property="og:title"]',
      );
      if (og) og.content = document.title;
    }
  }, [p, b.store.brand_name]);
  if (query.isError)
    return <ErrorBox error={query.error} retry={() => void query.refetch()} />;
  if (!p) return <Skeleton />;
  return (
    <section className="r-product-page">
      <Link className="r-back" to="/catalogo">
        <ChevronLeft size={18} /> Volver al catálogo
      </Link>
      <div
        className="r-product-layout"
        itemScope
        itemType="https://schema.org/Product"
      >
        <meta itemProp="name" content={p.title} />
        <meta itemProp="description" content={p.description} />
        <div
          itemProp="offers"
          itemScope
          itemType="https://schema.org/Offer"
          hidden
        >
          <meta itemProp="priceCurrency" content="ARS" />
          <meta itemProp="price" content={(p.price / 100).toFixed(2)} />
          <link
            itemProp="availability"
            href={`https://schema.org/${p.kind === "digital" ? "InStock" : "PreOrder"}`}
          />
        </div>
        <div className="r-product-photo">
          {p.image ? (
            <img src={p.image} alt={p.title} width="600" height="600" />
          ) : (
            <Flower2 size={120} />
          )}
        </div>
        <div className="r-product-info">
          <span className="r-pill">
            {p.kind === "digital" ? (
              <Download size={16} />
            ) : (
              <Package size={16} />
            )}{" "}
            {p.kind === "digital"
              ? "Imprimible digital"
              : "Material por encargo"}
          </span>
          <small className="r-eyebrow">{p.category}</small>
          <h1>{p.title}</h1>
          <p>{p.age || "Para aprender jugando"}</p>
          <strong className="r-price">
            {money(p.price)} <small>ARS</small>
          </strong>
          <p className="r-description">{p.description}</p>
          <div className="r-delivery">
            <Check size={20} />
            <span>
              {p.kind === "digital"
                ? "Descarga privada después del pago. Sin envío."
                : `Preparación aproximada: ${b.store.preparation_days} días desde el pago. ${b.store.delivery_note}`}
            </span>
          </div>
          <button
            className="r-button"
            disabled={actions.isPending}
            onClick={() =>
              actions.mutate(
                { p, action: "add" },
                { onSuccess: () => navigate("/pedido/nuevo") },
              )
            }
          >
            Comprar ahora <ArrowRight size={20} />
          </button>
          <button
            className="r-button r-secondary"
            disabled={actions.isPending}
            onClick={() =>
              actions.mutate(
                { p, action: "add" },
                { onSuccess: () => setAdded(true) },
              )
            }
          >
            {added ? <Check size={20} /> : <Plus size={20} />}{" "}
            {added ? "Agregado al carrito" : "Agregar al carrito"}
          </button>
          {added && (
            <Link className="r-detail-link" to="/carrito">
              Revisar mi selección →
            </Link>
          )}
          {actions.isError && <ErrorBox error={actions.error} />}
          <small>
            Comprás como invitado. El pago se realiza después de crear el
            pedido.
          </small>
        </div>
      </div>
    </section>
  );
}
function CartPage() {
  const b = useBoot(),
    { data: cart } = useCart(),
    client = useQueryClient(),
    actions = useCartActions();
  useEffect(() => {
    if (cart.items.length && !actions.isPending)
      void client.prefetchQuery({
        queryKey: [
          "checkout",
          JSON.stringify(cart.items.map((i) => [i.product.id, i.quantity])),
        ],
        queryFn: () => request<Checkout>("/pedido/nuevo", b.csrf),
        staleTime: 30000,
      });
  }, [cart, actions.isPending, b.csrf, client]);
  return (
    <section className="r-shopping">
      <Steps current={0} />
      <div className="r-page-intro">
        <h1>Tu selección</h1>
        <p>Una nueva idea está a un paso de empezar.</p>
      </div>
      {!cart.items.length ? (
        <div className="r-empty">
          <ShoppingBag size={48} />
          <h2>Tu carrito está esperando una idea</h2>
          <Link className="r-button" to="/catalogo">
            Explorar recursos <ArrowRight size={18} />
          </Link>
        </div>
      ) : (
        <div className="r-shopping-layout">
          <div className="r-cart-items">
            {cart.items.map(({ product: p, quantity }) => (
              <article key={p.id} className="r-cart-item">
                <Link to={`/producto/${p.id}`}>
                  {p.image ? (
                    <img src={p.image} alt={p.title} width="100" height="100" />
                  ) : (
                    <Flower2 size={40} />
                  )}
                </Link>
                <div>
                  <Link to={`/producto/${p.id}`}>
                    <h2>{p.title}</h2>
                  </Link>
                  <p>
                    {p.kind === "digital"
                      ? "Imprimible digital"
                      : "Material por encargo"}
                  </p>
                  <strong>{money(p.price)}</strong>
                  <div className="r-quantity">
                    {p.kind === "physical" ? (
                      <>
                        <button
                          aria-label={`Quitar una unidad de ${p.title}`}
                          disabled={actions.isPending || quantity <= 1}
                          onClick={() =>
                            actions.mutate({
                              p,
                              action: "quantity",
                              quantity: quantity - 1,
                            })
                          }
                        >
                          <Minus size={18} />
                        </button>
                        <span>{quantity}</span>
                        <button
                          aria-label={`Agregar una unidad de ${p.title}`}
                          disabled={actions.isPending || quantity >= 10}
                          onClick={() =>
                            actions.mutate({
                              p,
                              action: "quantity",
                              quantity: quantity + 1,
                            })
                          }
                        >
                          <Plus size={18} />
                        </button>
                      </>
                    ) : (
                      <span>1 unidad</span>
                    )}
                    <button
                      className="r-remove"
                      aria-label={`Quitar ${p.title} del carrito`}
                      disabled={actions.isPending}
                      onClick={() => actions.mutate({ p, action: "remove" })}
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                </div>
                <strong>{money(p.price * quantity)}</strong>
              </article>
            ))}
            {actions.isError && <ErrorBox error={actions.error} />}
            <Link className="r-back" to="/catalogo">
              <ChevronLeft size={18} /> Seguir explorando
            </Link>
          </div>
          <Summary cart={cart}>
            <Link
              className={`r-button ${actions.isPending ? "r-disabled" : ""}`}
              aria-disabled={actions.isPending}
              onClick={(e) => {
                if (actions.isPending) e.preventDefault();
              }}
              to="/pedido/nuevo"
            >
              Continuar con mi pedido <ArrowRight size={18} />
            </Link>
          </Summary>
        </div>
      )}
    </section>
  );
}
function Summary({ cart, children }: { cart: Cart; children: ReactNode }) {
  const physical = cart.items.some((i) => i.product.kind === "physical");
  return (
    <aside className="r-summary">
      <small className="r-eyebrow">CASI ES TUYO</small>
      <h2>Resumen del pedido</h2>
      {cart.items.map((i) => (
        <div className="r-summary-line" key={i.product.id}>
          <span>
            {i.quantity} × {i.product.title}
          </span>
          <strong>{money(i.quantity * i.product.price)}</strong>
        </div>
      ))}
      <div className="r-summary-line">
        <span>Envío</span>
        <span>{physical ? "A coordinar" : "Digital · sin envío"}</span>
      </div>
      <div className="r-total">
        <span>Total de productos</span>
        <strong>{money(cart.total)}</strong>
      </div>
      {physical && <small>El envío se coordina y se abona por separado.</small>}
      {children}
      <p>
        <ShieldCheck size={16} /> Sin registro. Tus datos están protegidos.
      </p>
    </aside>
  );
}
function CheckoutPage() {
  const b = useBoot(),
    { data: cart } = useCart(),
    client = useQueryClient();
  const signature = JSON.stringify(
    cart.items.map((i) => [i.product.id, i.quantity]),
  );
  const query = useQuery({
    queryKey: ["checkout", signature],
    queryFn: ({ signal }) =>
      request<Checkout & { redirect?: string }>(
        "/pedido/nuevo",
        b.csrf,
        undefined,
        signal,
      ),
    staleTime: 30000,
    retry: false,
  });
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [shipping, setShipping] = useState(""),
    [quoting, setQuoting] = useState(false);
  const physical = cart.items.some((i) => i.product.kind === "physical");
  const d = query.data;
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const result = await request<{ redirect: string; messages: string[] }>(
        "/pedido/nuevo",
        b.csrf,
        form,
      );
      if (
        result.redirect.includes("/pedido/") &&
        !result.redirect.endsWith("/nuevo")
      ) {
        window.location.assign(result.redirect);
        return;
      }
      setError(result.messages.join(" ") || "Revisá los datos del pedido.");
      await client.invalidateQueries({ queryKey: ["cart"] });
      await query.refetch();
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "No se pudo crear el pedido.",
      );
    } finally {
      setBusy(false);
    }
  }
  if (!cart.items.length) return <CartPage />;
  if (query.isError)
    return (
      <section className="r-shopping">
        <ErrorBox error={query.error} retry={() => void query.refetch()} />
        <Link to="/carrito">Revisar carrito</Link>
      </section>
    );
  if (!d || !d.checkout_key) return <Skeleton />;
  return (
    <section className="r-shopping">
      <Steps current={1} />
      <div className="r-page-intro">
        <h1>Datos y medio de pago</h1>
        <p>Comprás como invitado. Te acompañamos en cada paso.</p>
        <Link to="/carrito">← Revisar carrito</Link>
      </div>
      <form className="r-shopping-layout" onSubmit={submit}>
        <input type="hidden" name="checkout_key" value={d.checkout_key} />
        <div className="r-checkout-fields">
          <fieldset>
            <legend>1. Tus datos</legend>
            <label>
              Nombre y apellido
              <input
                name="name"
                autoComplete="name"
                required
                minLength={2}
                maxLength={120}
              />
            </label>
            <label>
              Correo electrónico
              <input
                name="email"
                type="email"
                autoComplete="email"
                required
                maxLength={254}
              />
              <small>Te enviamos el acceso privado a tu pedido.</small>
            </label>
            {physical && (
              <>
                <label>
                  WhatsApp con código de país
                  <input
                    name="whatsapp"
                    type="tel"
                    autoComplete="tel"
                    placeholder="+5492915090223"
                    required
                    maxLength={25}
                  />
                </label>
                <label>
                  Código postal
                  <input
                    name="postal_code"
                    autoComplete="postal-code"
                    placeholder="8000"
                    maxLength={8}
                  />
                </label>
              </>
            )}
          </fieldset>
          <fieldset>
            <legend>2. Cómo querés pagar</legend>
            {d.methods.map(([value, label, help], i) => (
              <label className="r-payment" key={value}>
                <input
                  type="radio"
                  name="payment_method"
                  value={value}
                  defaultChecked={i === 0}
                  required
                />
                <span>
                  <strong>{label}</strong>
                  <small>{help}</small>
                </span>
              </label>
            ))}
            <p>
              Crear el pedido no confirma el pago. En el siguiente paso vas a
              encontrar las instrucciones.
            </p>
          </fieldset>
          {physical && (
            <fieldset>
              <legend>3. Preparación y entrega</legend>
              <p>
                Aproximadamente {b.store.preparation_days} días desde el pago.{" "}
                {b.store.delivery_note}
              </p>
              <button
                className="r-button r-secondary"
                type="button"
                disabled={quoting}
                onClick={async (e) => {
                  const form = e.currentTarget.form!;
                  const data = new FormData();
                  data.set(
                    "postal_code",
                    String(new FormData(form).get("postal_code") || ""),
                  );
                  setQuoting(true);
                  try {
                    const result = await request<{
                      message?: string;
                      error?: string;
                      rates?: {
                        cents: number;
                        name: string;
                        delivery: string;
                      }[];
                      test?: boolean;
                      valid_to?: string;
                    }>("/envios/cotizar", b.csrf, data);
                    setShipping(
                      result.message ||
                        result.error ||
                        (result.test
                          ? "PRUEBA — no es una tarifa real. "
                          : "") +
                          (result.rates || [])
                            .map(
                              (rate) =>
                                `${rate.name} · ${rate.delivery}: ${money(rate.cents)}`,
                            )
                            .join(" / "),
                    );
                  } catch (error) {
                    setShipping(
                      error instanceof Error
                        ? error.message
                        : "No se pudo estimar el envío.",
                    );
                  } finally {
                    setQuoting(false);
                  }
                }}
              >
                Estimar envío con MiCorreo
              </button>
              <p role="status">{shipping}</p>
              <small>
                Es una estimación. Se coordina y abona por separado.
              </small>
            </fieldset>
          )}
          <details>
            <summary>Agregar un comentario</summary>
            <label>
              Comentarios
              <textarea name="notes" rows={3} maxLength={1000} />
            </label>
          </details>
          {error && <ErrorBox error={new Error(error)} />}
        </div>
        <Summary cart={d}>
          <button className="r-button" disabled={busy} type="submit">
            {busy ? "Creando tu pedido…" : "Crear pedido y continuar al pago"}{" "}
            <ArrowRight size={18} />
          </button>
          <small>No se cobra al pulsar este botón.</small>
          <a href="/privacidad">Cómo cuidamos tus datos</a>
        </Summary>
      </form>
    </section>
  );
}
function NavigationEffects() {
  const b = useBoot(),
    location = useLocation(),
    first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    window.scrollTo({ top: 0, behavior: "instant" });
    const p = location.pathname;
    document.title =
      (p === "/catalogo"
        ? "Catálogo de recursos"
        : p === "/carrito"
          ? "Tu carrito"
          : p === "/pedido/nuevo"
            ? "Datos y pago"
            : p.startsWith("/producto/")
              ? "Recurso didáctico"
              : b.store.brand_name) +
      " · " +
      b.store.brand_name;
    const privatePage = p.startsWith("/carrito") || p.startsWith("/pedido");
    let robots = document.querySelector<HTMLMetaElement>('meta[name="robots"]');
    if (!robots) {
      robots = document.createElement("meta");
      robots.name = "robots";
      document.head.appendChild(robots);
    }
    robots.content =
      privatePage || location.search ? "noindex, follow" : "index, follow";
    const canonical = document.querySelector<HTMLLinkElement>(
      'link[rel="canonical"]',
    );
    if (canonical) canonical.href = window.location.origin + p;
    const kind = p.startsWith("/producto/")
      ? "product"
      : p === "/pedido/nuevo"
        ? "checkout"
        : p === "/catalogo"
          ? "catalog"
          : "visit";
    if (b.consent && !b.admin && p != "/carrito") {
      void fetch("/api/evento", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": b.csrf },
        body: JSON.stringify({
          kind,
          id: kind === "product" ? Number(p.split("/").pop()) : undefined,
        }),
      }).catch(() => {});
    }
    const timer = window.setTimeout(() => {
      const h = document.querySelector<HTMLElement>("#r-content h1");
      h?.setAttribute("tabindex", "-1");
      h?.focus({ preventScroll: true });
    }, 0);
    return () => clearTimeout(timer);
  }, [location.pathname, location.search, b]);
  return null;
}
export function App({ bootstrap: b }: { bootstrap: Bootstrap }) {
  return (
    <Context.Provider value={b}>
      <Layout />
    </Context.Provider>
  );
}
function Layout() {
  const b = useBoot(),
    { data: cart } = useCart(),
    [mode, setMode] = useState(() => {
      try {
        return localStorage.getItem("rincon-mode") || b.store.default_mode;
      } catch {
        return b.store.default_mode;
      }
    });
  useEffect(() => {
    const effective =
      mode === "system"
        ? matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light"
        : mode;
    document.body.dataset.mode = effective;
    try {
      localStorage.setItem("rincon-mode", mode);
    } catch {}
  }, [mode]);
  const count = cart.items.reduce((n, i) => n + i.quantity, 0);
  return (
    <div className="r-app">
      <NavigationEffects />
      <a className="skip" href="#r-content">
        Ir al contenido
      </a>
      {b.store.announcement && (
        <div className="r-announcement">✿ {b.store.announcement} ✿</div>
      )}
      <header className="r-header">
        <Link className="r-brand" to="/">
          {b.store.logo_image ? (
            <img
              src={`/imagenes/${b.store.logo_image}`}
              alt=""
              width="42"
              height="42"
            />
          ) : (
            <Flower2 size={38} strokeWidth={1.5} />
          )}
          <span>
            {b.store.brand_name}
            <small>{b.store.brand_tagline}</small>
          </span>
        </Link>
        <nav aria-label="Navegación principal">
          <NavLink to="/" end>
            <House size={20} />
            <span>Inicio</span>
          </NavLink>
          <NavLink to="/catalogo">
            <Search size={20} />
            <span>Catálogo</span>
          </NavLink>
          <NavLink to="/carrito">
            <ShoppingBag size={20} />
            <span>Carrito</span>
            <b>{count}</b>
          </NavLink>
          <button
            className="mode-toggle"
            onClick={() =>
              setMode(document.body.dataset.mode === "dark" ? "light" : "dark")
            }
            aria-label="Cambiar modo claro u oscuro"
          >
            {mode === "dark" ? <Sun size={20} /> : <Moon size={20} />}
            <span>Modo</span>
          </button>
        </nav>
      </header>
      <main id="r-content">
        {b.store.checkout_enabled !== "1" && (
          <p className="r-error">
            Las compras están pausadas por el momento. Podés explorar el
            catálogo y consultar.
          </p>
        )}
        {b.store.promo_title && (
          <aside className="r-promotion">
            <div>
              <strong>{b.store.promo_title}</strong>
              <p>{b.store.promo_text}</p>
            </div>
            <Link className="r-button r-secondary" to={b.store.promo_link}>
              {b.store.promo_label}
            </Link>
          </aside>
        )}
        <Routes>
          <Route path="/" element={<Shop home />} />
          <Route path="/catalogo" element={<Shop />} />
          <Route path="/producto/:id" element={<ProductPage />} />
          <Route path="/carrito" element={<CartPage />} />
          <Route path="/pedido/nuevo" element={<CheckoutPage />} />
          <Route
            path="*"
            element={
              <section className="r-empty">
                <h1>No encontramos esta página</h1>
                <Link to="/catalogo">Explorar el catálogo</Link>
              </section>
            }
          />
        </Routes>
      </main>
      <footer className="r-footer">
        <div>
          <Flower2 size={32} />
          <h2>{b.store.brand_name}</h2>
          <p>{b.store.brand_tagline}</p>
          <small>{b.store.location}</small>
        </div>
        <div>
          <a
            href={`https://www.instagram.com/${b.store.instagram}/`}
            rel="noopener"
          >
            <Instagram size={18} /> Instagram
          </a>
          {b.store.contact_email && (
            <a href={`mailto:${b.store.contact_email}`}>Contactanos</a>
          )}
          <a href="/privacidad">Preferencias de privacidad</a>
          <a
            className="admin-access"
            aria-label="Ingresar a administración"
            href={b.admin ? "/admin" : "/admin/login"}
          >
            Administración
          </a>
        </div>
        <a
          className="r-button r-secondary"
          href={b.whatsapp}
          target="_blank"
          rel="noopener noreferrer"
        >
          {b.store.whatsapp_label}
        </a>
      </footer>
      {b.consent == null && !b.admin && b.store.analytics_enabled === "1" && (
        <section className="r-consent">
          <h2>Vos elegís cómo navegar</h2>
          <p>
            Las cookies necesarias permiten comprar. Con tu permiso, medimos
            visitas y compras para mejorar la tienda.
          </p>
          <form method="post" action="/privacidad/medicion">
            <input type="hidden" name="csrf_token" value={b.csrf} />
            <input type="hidden" name="next" value="/" />
            <button className="r-button" name="choice" value="yes">
              Permitir medición
            </button>
            <button className="r-button r-secondary" name="choice" value="no">
              Solo lo necesario
            </button>
            <a href="/privacidad">Leer privacidad</a>
          </form>
        </section>
      )}
    </div>
  );
}
