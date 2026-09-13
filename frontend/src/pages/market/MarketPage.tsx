/**
 * Energy Market Page
 *
 * Consumes:
 *   GET    /api/market/orders/pending
 *   POST   /api/market/orders
 *   DELETE /api/market/orders/{id}
 *   POST   /api/market/match
 *   GET    /api/market/trades
 */

import { useCallback, useEffect, useState } from "react";
import {
  marketApi,
  MarketOrder,
  MarketTrade,
  OrderCreate,
} from "../../services/api";
import styles from "../shared.module.css";

function formatTime(ts: string): string {
  return new Date(ts).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

const emptyForm: OrderCreate = {
  participant_id: "",
  participant_name: "",
  order_type: "bid",
  energy_kwh: 10,
  price_per_kwh: 5,
};

export default function MarketPage() {
  const [pending, setPending] = useState<MarketOrder[]>([]);
  const [trades, setTrades] = useState<MarketTrade[]>([]);
  const [form, setForm] = useState<OrderCreate>(emptyForm);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [pendingData, tradesData] = await Promise.all([
        marketApi.pendingOrders(),
        marketApi.trades(),
      ]);
      setPending(pendingData);
      setTrades(tradesData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 15_000);
    return () => clearInterval(interval);
  }, [refresh]);

  const placeOrder = useCallback(async () => {
    setBusy(true);
    setMessage(null);
    try {
      const payload: OrderCreate = {
        participant_id: form.participant_id.trim() || "household_1",
        participant_name: (form.participant_name ?? "").trim() || undefined,
        order_type: form.order_type,
        energy_kwh: Number(form.energy_kwh),
        price_per_kwh: Number(form.price_per_kwh),
      };
      await marketApi.placeOrder(payload);
      setMessage(`Order placed: ${payload.order_type.toUpperCase()} ${payload.energy_kwh} kWh @ ₹${payload.price_per_kwh}/kWh`);
      setForm((f) => ({ ...f, participant_id: "", participant_name: "" }));
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [form, refresh]);

  const cancelOrder = useCallback(async (orderId: number) => {
    setBusy(true);
    setMessage(null);
    try {
      await marketApi.cancelOrder(orderId);
      setMessage(`Order #${orderId} cancelled.`);
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [refresh]);

  const runMatching = useCallback(async () => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await marketApi.match();
      setMessage(
        `${result.message} — ${result.matched_pairs} pair(s), ${result.trades_executed} trade(s) executed.`,
      );
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }, [refresh]);

  if (loading && pending.length === 0 && trades.length === 0) {
    return (
      <section className={styles.page}>
        <div className={styles.loading}>
          <div className={styles.spinner} />
          <p>Loading energy market…</p>
        </div>
      </section>
    );
  }

  const bids = pending.filter((o) => o.order_type === "bid");
  const asks = pending.filter((o) => o.order_type === "ask");

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>Energy Market</h1>
          <p className={styles.subtitle}>
            Peer-to-peer energy trading — place bids/asks, run the matching
            engine, view executed trades.
          </p>
        </div>
        <div className={styles.headerActions}>
          <button
            type="button"
            className={styles.primaryButton}
            onClick={runMatching}
            disabled={busy}
          >
            Run matching engine
          </button>
        </div>
      </header>

      {error && (
        <div className={styles.error} style={{ marginBottom: 20 }}>
          <h2>Market error</h2>
          <p>{error}</p>
        </div>
      )}

      {message && (
        <p className={styles.reasoning} style={{ marginBottom: 16 }}>{message}</p>
      )}

      <div className={styles.grid}>
        {/* Order form */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2>Place Order</h2>
          </div>
          <div className={styles.formGrid}>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="order-participant">Participant ID</label>
              <input
                id="order-participant"
                className={styles.input}
                value={form.participant_id}
                placeholder="household_1"
                onChange={(e) => setForm({ ...form, participant_id: e.target.value })}
              />
            </div>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="order-name">Name (optional)</label>
              <input
                id="order-name"
                className={styles.input}
                value={form.participant_name ?? ""}
                placeholder="House 1"
                onChange={(e) => setForm({ ...form, participant_name: e.target.value })}
              />
            </div>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="order-type">Type</label>
              <select
                id="order-type"
                className={styles.select}
                value={form.order_type}
                onChange={(e) =>
                  setForm({ ...form, order_type: e.target.value as OrderCreate["order_type"] })
                }
              >
                <option value="bid">Bid (buy)</option>
                <option value="ask">Ask (sell)</option>
              </select>
            </div>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="order-energy">Energy (kWh)</label>
              <input
                id="order-energy"
                className={styles.input}
                type="number"
                min="0.1"
                step="0.5"
                value={form.energy_kwh}
                onChange={(e) => setForm({ ...form, energy_kwh: Number(e.target.value) })}
              />
            </div>
            <div className={styles.field}>
              <label className={styles.label} htmlFor="order-price">Price (₹/kWh)</label>
              <input
                id="order-price"
                className={styles.input}
                type="number"
                min="0"
                step="0.5"
                value={form.price_per_kwh}
                onChange={(e) => setForm({ ...form, price_per_kwh: Number(e.target.value) })}
              />
            </div>
            <button
              type="button"
              className={styles.primaryButton}
              onClick={placeOrder}
              disabled={busy}
            >
              Place order
            </button>
          </div>
        </div>

        {/* Order book summary */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2>Order Book</h2>
            <span className={styles.count}>{pending.length} pending</span>
          </div>
          <div className={styles.metrics}>
            <div className={styles.metric}>
              <dt>Pending bids</dt>
              <dd className={`${styles.value} ${styles.positive}`}>{bids.length}</dd>
            </div>
            <div className={styles.metric}>
              <dt>Pending asks</dt>
              <dd className={styles.value}>{asks.length}</dd>
            </div>
            <div className={styles.metric}>
              <dt>Executed trades</dt>
              <dd className={styles.value}>{trades.length}</dd>
            </div>
            {(() => {
              const last = trades[trades.length - 1];
              return (
                <div className={styles.metric}>
                  <dt>Last price</dt>
                  <dd className={styles.value}>
                    {last ? `₹${last.price_per_kwh.toFixed(2)}` : "—"}
                  </dd>
                </div>
              );
            })()}
          </div>
        </div>

        {/* Pending orders */}
        <div className={`${styles.card} ${styles.cardFull}`}>
          <div className={styles.cardHeader}>
            <h2>Pending Orders</h2>
            <span className={styles.count}>{pending.length}</span>
          </div>
          {pending.length === 0 ? (
            <p className={styles.empty}>No pending orders — place a bid or ask above.</p>
          ) : (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Participant</th>
                  <th>Type</th>
                  <th>Energy (kWh)</th>
                  <th>Price (₹/kWh)</th>
                  <th>Placed</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {pending.map((order) => (
                  <tr key={order.id}>
                    <td>#{order.id}</td>
                    <td>{order.participant_name ?? order.participant_id}</td>
                    <td>
                      <span
                        className={`${styles.pill} ${
                          order.order_type === "bid" ? styles.pillOk : styles.pillInfo
                        }`}
                      >
                        {order.order_type}
                      </span>
                    </td>
                    <td>{order.energy_kwh.toFixed(1)}</td>
                    <td>₹{order.price_per_kwh.toFixed(2)}</td>
                    <td>{formatTime(order.timestamp)}</td>
                    <td>
                      <button
                        type="button"
                        className={styles.dangerButton}
                        onClick={() => cancelOrder(order.id)}
                        disabled={busy}
                      >
                        Cancel
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Trade history */}
        <div className={`${styles.card} ${styles.cardFull}`}>
          <div className={styles.cardHeader}>
            <h2>Executed Trades</h2>
            <span className={styles.count}>{trades.length}</span>
          </div>
          {trades.length === 0 ? (
            <p className={styles.empty}>No trades yet — run the matching engine.</p>
          ) : (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Seller</th>
                  <th>Buyer</th>
                  <th>Energy (kWh)</th>
                  <th>Price (₹/kWh)</th>
                  <th>Total (₹)</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {[...trades].reverse().map((trade) => (
                  <tr key={trade.id}>
                    <td>#{trade.id}</td>
                    <td>{trade.seller_name ?? trade.seller_id}</td>
                    <td>{trade.buyer_name ?? trade.buyer_id}</td>
                    <td>{trade.energy_kwh.toFixed(1)}</td>
                    <td>₹{trade.price_per_kwh.toFixed(2)}</td>
                    <td>{trade.total_cost != null ? `₹${trade.total_cost.toFixed(2)}` : "—"}</td>
                    <td>{formatTime(trade.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <footer className={styles.footer}>
        <button type="button" className={styles.button} onClick={refresh}>
          Refresh market
        </button>
        <p className={styles.note}>
          Matching pairs the highest bids with the lowest asks. Prices are in ₹/kWh.
        </p>
      </footer>
    </section>
  );
}
