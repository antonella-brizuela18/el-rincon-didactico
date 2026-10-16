import {afterEach, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {ShippingEstimator} from './App';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('quotes one product without changing the cart and identifies test rates',async()=>{
  const fetcher=vi.fn().mockResolvedValue(new Response(JSON.stringify({rates:[{name:'Clásico',delivery:'Domicilio',cents:123456}],test:true}),{status:200,headers:{'Content-Type':'application/json'}}));
  vi.stubGlobal('fetch',fetcher);
  render(<ShippingEstimator productId={2} csrf="csrf" origin="8000" days="10"/>);
  fireEvent.click(screen.getByText('Calculá tu envío'));
  fireEvent.change(screen.getByLabelText('Código postal de destino'),{target:{value:'1425'}});
  fireEvent.click(screen.getByRole('button',{name:'Calcular'}));
  expect(await screen.findByText('PRUEBA — estos valores no son tarifas reales.')).toBeTruthy();
  expect(screen.getByText('Clásico · Domicilio')).toBeTruthy();
  const body=fetcher.mock.calls[0][1].body as FormData;
  expect(body.get('product_id')).toBe('2'); expect(body.get('postal_code')).toBe('1425');
  fireEvent.change(screen.getByLabelText('Código postal de destino'),{target:{value:'5000'}});
  expect(screen.queryByText('Clásico · Domicilio')).toBeNull();
});
it('keeps the manual fallback available when MiCorreo cannot quote',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({error:'El envío se cotiza por WhatsApp mientras conectamos MiCorreo.'}),{status:422,headers:{'Content-Type':'application/json'}})));
  render(<ShippingEstimator productId={2} csrf="csrf" origin="8000" days="10"/>);
  fireEvent.click(screen.getByText('Calculá tu envío'));
  fireEvent.change(screen.getByLabelText('Código postal de destino'),{target:{value:'1425'}});
  fireEvent.click(screen.getByRole('button',{name:'Calcular'}));
  expect(await screen.findByText('El envío se cotiza por WhatsApp mientras conectamos MiCorreo.')).toBeTruthy();
});
