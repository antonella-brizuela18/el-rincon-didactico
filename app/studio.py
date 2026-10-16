"""Store presentation settings, first-party consented analytics and operator tools."""
import json
import re
import secrets
from datetime import timedelta
from xml.etree.ElementTree import Element, SubElement, tostring
from flask import Blueprint, Response, abort, current_app, g, redirect, render_template, request, session, url_for, flash
from sqlalchemy import select, func, delete
from sqlalchemy.exc import SQLAlchemyError
from app.models import Base, Product, Order, MailOutbox, now
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from app.routes import db, admin_required
from app import customization

studio = Blueprint('studio', __name__)

class StoreSetting(Base):
    __tablename__ = 'store_settings'
    key = Column(String(60), primary_key=True)
    value = Column(Text, nullable=False)

class VisitEvent(Base):
    __tablename__ = 'visit_events'
    id = Column(Integer, primary_key=True)
    visit = Column(String(48), nullable=False, index=True)
    kind = Column(String(30), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey('products.id'))
    order_id = Column(Integer, ForeignKey('orders.id'))
    created_at = Column(DateTime, nullable=False, default=now, index=True)

DEFAULTS = dict(hero_title='Ideas que hacen crecer la imaginación.', hero_text='Materiales didácticos y recursos para transformar los momentos de cada día en pequeñas aventuras de aprendizaje.', announcement='Creado con amor para aprender jugando', theme='floral', contact_email='', order_email='', instagram='elrincondidactico_', seo_description='Materiales didácticos e imprimibles para docentes y familias. El Rincón Didáctico, desde Bahía Blanca: juego, creatividad y aprendizaje.', analytics_enabled='1')
DEFAULTS.update(payment_instructions='', transfer_mode='auto', mp_mode='auto', checkout_enabled='1', preparation_days='10', delivery_note='El envío se coordina por WhatsApp y se abona por separado. Podés consultar su estimación antes de confirmar.', font='editorial', default_mode='system', promo_title='', promo_text='', promo_link='/catalogo', promo_label='Ver recursos', accent='#345b32', shipping_origin='')

DEFAULTS.update(customization.DEFAULTS)
DEFAULTS['shipping_origin']='8000'

@studio.before_app_request
def restore_consent():
    choice = request.cookies.get('rincon_measurement')
    if choice in ('yes','no'):
        session['analytics_consent'] = choice=='yes'

def settings():
    if 'store_settings' not in g:
        values = DEFAULTS.copy()
        values['contact_email'] = current_app.config.get('CONTACT_EMAIL', '')
        values['payment_instructions'] = current_app.config.get('PAYMENT_INSTRUCTIONS', '')
        with current_app.extensions['sessions']() as connection:
            values.update({row.key:row.value for row in connection.scalars(select(StoreSetting)) if row.key in DEFAULTS})
        values['shipping_origin']=values['shipping_origin'] or '8000'
        g.store_settings = values
    return g.store_settings

@studio.app_context_processor
def context():
    private = request.path.startswith(('/admin', '/pedido', '/carrito'))
    canonical = current_app.config['SITE_URL'] + request.path
    if request.endpoint == 'main.catalog' and request.args.get('pagina', type=int) and request.args.get('pagina', type=int)>1:
        canonical += '?pagina='+str(request.args.get('pagina', type=int))
    from app.payments import payment_methods, mp_ready
    smtp_ready=all(current_app.config.get(k) for k in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD','SMTP_FROM'))
    return dict(payment_methods=payment_methods, mp_ready=mp_ready(), smtp_ready=smtp_ready, store=settings(), is_admin=request.path.startswith('/admin') and bool(session.get('admin_id')), private_page=private, canonical=canonical, whatsapp_url=lambda message=None:customization.whatsapp_url(settings(),message), seo_noindex=private or bool(request.args.get('q') or request.args.get('categoria') or request.args.get('tipo') or request.args.get('orden')))

@studio.post('/privacidad/medicion')
def consent():
    choice = request.form.get('choice')
    if choice not in ('yes','no'): abort(400)
    session['analytics_consent'] = choice == 'yes'
    session.pop('analytics_visit', None)
    target = request.form.get('next', '/')
    if not target.startswith('/') or target.startswith('//') or '\\' in target or any(ord(…11763 tokens truncated…`https://schema.org/${p.kind === "digital" ? "InStock" : "PreOrder"}`}
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
          {p.kind === 'physical' && <ShippingEstimator key={p.id} productId={p.id} csrf={b.csrf} origin={b.store.shipping_origin} days={b.store.preparation_days}/>}
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
