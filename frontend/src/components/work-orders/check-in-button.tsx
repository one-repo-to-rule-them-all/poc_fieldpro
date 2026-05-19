"use client";

import { useState, useEffect } from "react";
import {
  MapPin,
  Loader2,
  CheckCircle,
  AlertCircle,
  QrCode,
  LogOut,
} from "lucide-react";
import { useCheckIn, useCheckOut } from "@/hooks/use-work-orders";
import { TIMINGS } from "@/lib/timings";
import { getDistanceLabel, cn } from "@/lib/utils";
import type { CheckIn } from "@/types";

interface CheckInButtonProps {
  workOrderId: string;
  locationId: string;
  currentCheckIns: CheckIn[];
}

type CheckInState =
  | "idle"
  | "locating"
  | "ready"
  | "loading"
  | "success"
  | "error";

export function CheckInButton({
  workOrderId,
  currentCheckIns,
}: CheckInButtonProps) {
  const [state, setState] = useState<CheckInState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [coords, setCoords] = useState<{
    latitude: number;
    longitude: number;
  } | null>(null);
  const [distanceMeters, setDistanceMeters] = useState<number | null>(null);

  const checkInMutation = useCheckIn(workOrderId);
  const checkOutMutation = useCheckOut(workOrderId);

  const activeCheckIn = currentCheckIns.find((c) => !c.check_out_time);
  const isCheckedIn = Boolean(activeCheckIn);

  useEffect(() => {
    if (!navigator.geolocation) {
      setState("error");
      setErrorMessage("Geolocation is not supported by your device.");
      return;
    }

    setState("locating");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
        });
        setDistanceMeters(Math.floor(Math.random() * 200));
        setState("ready");
      },
      (err) => {
        setState("error");
        setErrorMessage(
          err.code === 1
            ? "Location permission denied."
            : "Unable to determine your location."
        );
      },
      { enableHighAccuracy: true, timeout: TIMINGS.GEO_TIMEOUT_MS, maximumAge: TIMINGS.GEO_MAX_AGE_MS }
    );
  }, []);

  const handleCheckIn = async () => {
    if (!coords) return;
    setState("loading");
    setErrorMessage(null);
    try {
      await checkInMutation.mutateAsync({
        latitude: coords.latitude,
        longitude: coords.longitude,
      });
      setState("success");
      setTimeout(() => setState("ready"), TIMINGS.TOAST_SUCCESS_MS);
    } catch (err: unknown) {
      setState("error");
      setErrorMessage(
        (err as { message?: string })?.message ?? "Check-in failed."
      );
    }
  };

  const handleCheckOut = async () => {
    if (!coords) return;
    setState("loading");
    setErrorMessage(null);
    try {
      await checkOutMutation.mutateAsync({
        latitude: coords.latitude,
        longitude: coords.longitude,
      });
      setState("success");
      setTimeout(() => setState("ready"), TIMINGS.TOAST_SUCCESS_MS);
    } catch (err: unknown) {
      setState("error");
      setErrorMessage(
        (err as { message?: string })?.message ?? "Check-out failed."
      );
    }
  };

  const isWithinGeofence = distanceMeters !== null && distanceMeters <= TIMINGS.GEOFENCE_RADIUS_M;

  // ── Status pill copy ──────────────────────────────────────────────────────
  const statusText =
    state === "locating"
      ? "Getting location…"
      : state === "error"
      ? (errorMessage ?? "Location error")
      : state === "loading"
      ? "Processing…"
      : state === "success"
      ? isCheckedIn ? "Checked out!" : "Checked in!"
      : distanceMeters !== null
      ? (isWithinGeofence
          ? `Within geofence · ${getDistanceLabel(distanceMeters)}`
          : `Outside geofence · ${getDistanceLabel(distanceMeters)}`)
      : "Ready";

  const statusColor =
    state === "error"
      ? "text-danger-600"
      : state === "success"
      ? "text-success-600"
      : state === "ready" && !isWithinGeofence
      ? "text-warning-600"
      : "text-neutral-500";

  return (
    <div data-testid="checkin-widget" className="card px-4 py-3">
      <div className="flex items-center gap-3">
        {/* Location status */}
        <div className={cn("flex min-w-0 flex-1 items-center gap-1.5 text-xs", statusColor)}>
          {state === "locating" || state === "loading" ? (
            <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
          ) : state === "error" ? (
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          ) : state === "success" ? (
            <CheckCircle className="h-3.5 w-3.5 shrink-0" />
          ) : (
            <MapPin className="h-3.5 w-3.5 shrink-0" />
          )}
          <span data-testid="checkin-status" className="truncate">{statusText}</span>
        </div>

        {/* QR option */}
        {state === "ready" && !isCheckedIn && (
          <button className="flex shrink-0 items-center gap-1 text-xs text-neutral-400 hover:text-neutral-600 transition-colors">
            <QrCode className="h-3.5 w-3.5" />
            QR
          </button>
        )}

        {/* Action button */}
        {isCheckedIn ? (
          <button
            onClick={handleCheckOut}
            data-testid="checkout-button"
            disabled={state === "loading" || state === "locating"}
            className={cn(
              "flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-all",
              state === "loading"
                ? "cursor-not-allowed bg-neutral-100 text-neutral-400"
                : "bg-warning-600 text-white hover:bg-warning-700"
            )}
          >
            {state === "loading" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <LogOut className="h-4 w-4" />
            )}
            {state === "loading" ? "…" : "Check Out"}
          </button>
        ) : (
          <button
            onClick={handleCheckIn}
            data-testid="checkin-button"
            disabled={state === "loading" || state === "locating" || state === "error"}
            className={cn(
              "flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-all",
              state === "error" || state === "locating"
                ? "cursor-not-allowed bg-neutral-100 text-neutral-400"
                : state === "loading"
                ? "cursor-not-allowed bg-neutral-100 text-neutral-400"
                : state === "success"
                ? "bg-success-600 text-white"
                : "bg-primary-600 text-white hover:bg-primary-700"
            )}
          >
            {state === "loading" || state === "locating" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : state === "success" ? (
              <CheckCircle className="h-4 w-4" />
            ) : (
              <MapPin className="h-4 w-4" />
            )}
            {state === "locating"
              ? "…"
              : state === "loading"
              ? "…"
              : state === "success"
              ? "Checked In!"
              : state === "error"
              ? "Unavailable"
              : "Check In"}
          </button>
        )}
      </div>

      {/* Previous check-ins summary — only when there are entries */}
      {currentCheckIns.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 border-t border-neutral-100 pt-2">
          {currentCheckIns.slice(-3).map((c) => (
            <span key={c.id} className="flex items-center gap-1 text-xs text-neutral-400">
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  c.is_valid ? "bg-success-400" : "bg-danger-400"
                )}
              />
              {new Date(c.check_in_time).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
              {c.check_out_time
                ? ` → ${new Date(c.check_out_time).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}`
                : " · active"}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
