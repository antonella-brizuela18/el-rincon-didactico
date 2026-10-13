"""Run against an isolated temporary schema on the CI PostgreSQL service."""
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app import create_app
from app.models import Base, Order, Product


@pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="PostgreSQL service is provided in CI")
def test_concurrent_buyers_cannot_oversell(tmp_path):
    app = create_app({"TESTING":True, "SECRET_KEY":"ci-only", "DATABASE_URL":os.environ["TEST_POSTGRES_URL"],
                      "STORAGE_DIR":str(tmp_path/"storage"), "SESSION_COOKIE_SECURE":False,
                      "WTF_CSRF_ENABLED":False, "PAYMENT_INSTRUCTIONS":"Test only"})
    engine = app.extensions["database"]
    schema = "test_"+secrets.token_hex(8)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = engine.execution_options(schema_translate_map={None:schema})
    app.extensions["sessions"] = sessionmaker(bind=isolated, expire_on_commit=False)
    try:
        Base.metadata.create_all(isolated)
        with app.extensions["sessions"]() as db:
            db.add(Product(title="Unique item", description="Test", category="Test", kind="physical", price_cents=1000, stock=1, published=True))
            db.commit()
        barrier = Barrier(2)
        def buy(index):
            client = app.test_client()
            client.post("/carrito/agregar/1")
            client.get("/pedido/nuevo")
            with client.session_transaction() as state:
                key = state["checkout_key"]
            barrier.wait(timeout=10)
            return client.post("/pedido/nuevo", data={"checkout_key":key,"name":"Test Customer","email":f"buyer{index}@example.test"}).location
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(buy, (1,2)))
        assert sum(location.endswith("/carrito") for location in results)==1
        with app.extensions["sessions"]() as db:
            assert db.query(Order).count()==1
            assert db.get(Product, 1).stock==0
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()
