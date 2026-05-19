/**
 * Centralized React Query staleTime configuration.
 *
 * Why these values:
 *  - LIST (2 min): Balances navigation speed (cache hit on revisit) against
 *    the risk of a dispatcher missing a work order created by a colleague.
 *    Mutations that write data call invalidateQueries on success, so the cache
 *    busts immediately for the user who made the change.
 *  - DETAIL (1 min): Status changes (check-in, task completion) matter more
 *    on a detail view, so we refresh slightly more aggressively.
 *  - ANALYTICS (5 min): Aggregated/historical data; second-level freshness
 *    is not meaningful here.
 *  - SUMMARY (5 min): Secondary aggregate queries (e.g. invoice totals bar).
 *
 * To change app-wide cache behaviour, edit the constants here — one place,
 * takes effect everywhere. When a real-time strategy (SSE/WebSocket) is
 * implemented these values can be raised significantly since push
 * invalidation will handle freshness instead.
 */
/**
 * Active polling intervals for pages that need live data push.
 * Use sparingly — prefer cache invalidation via mutations over polling.
 *
 * FIELD_WORKER — field worker job detail polls at this interval so status
 *                changes made by dispatch are reflected without a manual
 *                refresh. Remove once SSE/WebSocket is implemented.
 */
export const REFETCH_INTERVAL = {
  FIELD_WORKER: 30_000,
} as const;

export const STALE_TIME = {
  LIST: 2 * 60_000,
  DETAIL: 60_000,
  ANALYTICS: 5 * 60_000,
  SUMMARY: 5 * 60_000,
} as const;
