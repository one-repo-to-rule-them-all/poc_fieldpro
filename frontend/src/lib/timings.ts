/**
 * Centralized UI timing constants.
 *
 * DEBOUNCE_SEARCH_MS  — delay before firing a search/filter API call after
 *                       the user stops typing. Keeps request count low without
 *                       making the UI feel unresponsive.
 *
 * GEO_TIMEOUT_MS      — how long to wait for the browser to return a GPS fix
 *                       before rejecting. 10 s is the practical ceiling before
 *                       users assume it's broken.
 *
 * GEO_MAX_AGE_MS      — accept a cached GPS reading up to this age. 30 s is
 *                       fine for check-in; the worker hasn't moved that far.
 *
 * GEOFENCE_RADIUS_M   — distance (metres) within which a check-in is considered
 *                       "on-site". Matches the backend validation threshold.
 *
 * TOAST_SUCCESS_MS    — how long a success banner stays visible before
 *                       auto-dismissing.
 *
 * TOAST_ERROR_MS      — error banners stay longer so the user can read them.
 *
 * FORM_SAVE_DELAY_MS  — artificial debounce on form save to avoid double-clicks
 *                       triggering two API calls in quick succession.
 */
export const TIMINGS = {
  DEBOUNCE_SEARCH_MS: 500,
  GEO_TIMEOUT_MS: 10_000,
  GEO_MAX_AGE_MS: 30_000,
  GEOFENCE_RADIUS_M: 200,
  TOAST_SUCCESS_MS: 3_000,
  TOAST_ERROR_MS: 5_000,
  FORM_SAVE_DELAY_MS: 600,
} as const;
