import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  getGroupActivity,
  getGroupGrowth,
  getGroupPlaces,
} from "../lib/api";
import type {
  ActivityEventResponse,
  GrowthResponse,
  PlaceSummary,
} from "../lib/types";

type SocialTab = "activity" | "log" | "growth" | "discover";

type SocialPanelProps = {
  groupId: string;
  groupName?: string | null;
  /** Fly the map to a contributed place selected from the discovery list. */
  onFlyToPlace: (place: PlaceSummary) => void;
  onClose: () => void;
};

/** How often the feed / growth silently refresh while the panel is open. */
const SOCIAL_POLL_INTERVAL_MS = 30_000;

const TABS: { id: SocialTab; label: string }[] = [
  { id: "activity", label: "Activity" },
  { id: "log", label: "Contributions" },
  { id: "growth", label: "Growth" },
  { id: "discover", label: "Discover" },
];

function formatRelativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) {
    return "";
  }
  const seconds = Math.round((Date.now() - then) / 1000);
  if (seconds < 60) {
    return "just now";
  }
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m ago`;
  }
  const hours = Math.round(minutes / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }
  const days = Math.round(hours / 24);
  if (days < 30) {
    return `${days}d ago`;
  }
  return new Date(iso).toLocaleDateString();
}

function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function describeEvent(event: ActivityEventResponse): string {
  const label = event.payload?.label?.trim();
  const actor = event.actor_username;
  if (event.event_type === "pin_created") {
    return label
      ? `${actor} pinned "${label}"`
      : `${actor} pinned a new building`;
  }
  if (event.event_type === "object_placed") {
    return label
      ? `${actor} added a 3D model of "${label}"`
      : `${actor} added a 3D model to the map`;
  }
  return `${actor} contributed to the map`;
}

function eventPlaceText(event: ActivityEventResponse): string {
  const { lat, lng } = event.payload ?? {};
  if (typeof lat === "number" && typeof lng === "number") {
    return `${lat.toFixed(4)}, ${lng.toFixed(4)}`;
  }
  return "—";
}

/** Bar-and-line SVG chart of daily placements with a cumulative overlay. */
function GrowthChart({ growth }: { growth: GrowthResponse }) {
  const points = growth.points;
  if (points.length === 0) {
    return (
      <p className="text-sm text-gray-500">
        No models have been placed yet. Add a location to grow this map.
      </p>
    );
  }

  const width = 320;
  const height = 140;
  const padding = { top: 12, right: 8, bottom: 24, left: 8 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;
  const maxCount = Math.max(...points.map((p) => p.count), 1);
  const maxCumulative = Math.max(...points.map((p) => p.cumulative), 1);
  const barGap = 4;
  const barW = Math.max(2, plotW / points.length - barGap);

  const linePath = points
    .map((p, i) => {
      const x = padding.left + (i + 0.5) * (plotW / points.length);
      const y = padding.top + plotH - (p.cumulative / maxCumulative) * plotH;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-40 w-full"
      role="img"
      aria-label="Map growth over time"
    >
      {points.map((p, i) => {
        const x = padding.left + i * (plotW / points.length) + barGap / 2;
        const barH = (p.count / maxCount) * plotH;
        const y = padding.top + plotH - barH;
        return (
          <rect
            key={p.date}
            x={x}
            y={y}
            width={barW}
            height={barH}
            rx={2}
            className="fill-blue-200"
          >
            <title>{`${p.date}: ${p.count} placed (${p.cumulative} total)`}</title>
          </rect>
        );
      })}
      <path
        d={linePath}
        fill="none"
        className="stroke-blue-600"
        strokeWidth={2}
      />
    </svg>
  );
}

function SocialPanel({
  groupId,
  groupName,
  onFlyToPlace,
  onClose,
}: SocialPanelProps) {
  const [activeTab, setActiveTab] = useState<SocialTab>("activity");
  const [events, setEvents] = useState<ActivityEventResponse[] | null>(null);
  const [growth, setGrowth] = useState<GrowthResponse | null>(null);
  const [places, setPlaces] = useState<PlaceSummary[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [activity, growthData, placesData] = await Promise.all([
        getGroupActivity(groupId, { limit: 50 }),
        getGroupGrowth(groupId),
        getGroupPlaces(groupId),
      ]);
      setEvents(activity.events);
      setGrowth(growthData);
      setPlaces(placesData.places);
      setError("");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not load group activity.",
      );
    }
  }, [groupId]);

  useEffect(() => {
    setEvents(null);
    setGrowth(null);
    setPlaces(null);
    setError("");
    void load();

    const interval = window.setInterval(() => {
      void load();
    }, SOCIAL_POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [load]);

  const isLoading = events === null && growth === null && places === null;

  return (
    <div className="pointer-events-auto absolute right-0 top-0 z-30 flex h-full w-full max-w-md flex-col bg-white shadow-2xl">
      <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Group activity</h2>
          <p className="text-sm text-gray-500">
            {groupName ?? "This group"}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md p-2 text-gray-500 transition hover:bg-gray-100 hover:text-gray-700"
          aria-label="Close activity panel"
        >
          <svg
            className="h-5 w-5"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden="true"
          >
            <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
          </svg>
        </button>
      </div>

      <div className="flex border-b border-gray-200 px-2">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 border-b-2 px-2 py-2.5 text-sm font-medium transition ${
              activeTab === tab.id
                ? "border-blue-600 text-blue-700"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {error && (
          <p className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        {isLoading && !error && (
          <p className="text-sm text-gray-500">Loading activity…</p>
        )}

        {activeTab === "activity" && events !== null && (
          <ul className="space-y-3">
            {events.length === 0 && (
              <li className="text-sm text-gray-500">
                No activity yet. Contributions will appear here.
              </li>
            )}
            {events.map((event) => (
              <li key={event.id} className="flex gap-3">
                <span
                  className={`mt-1 h-2 w-2 shrink-0 rounded-full ${
                    event.event_type === "object_placed"
                      ? "bg-blue-500"
                      : "bg-gray-300"
                  }`}
                  aria-hidden="true"
                />
                <div className="min-w-0">
                  <p className="text-sm text-gray-800">{describeEvent(event)}</p>
                  <p className="text-xs text-gray-400">
                    {formatRelativeTime(event.created_at)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}

        {activeTab === "log" && events !== null && (
          <div className="overflow-hidden rounded-md border border-gray-200">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-3 py-2 font-medium">Who</th>
                  <th className="px-3 py-2 font-medium">What</th>
                  <th className="px-3 py-2 font-medium">When</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {events.length === 0 && (
                  <tr>
                    <td
                      colSpan={3}
                      className="px-3 py-3 text-center text-gray-500"
                    >
                      No contributions logged yet.
                    </td>
                  </tr>
                )}
                {events.map((event) => (
                  <tr key={event.id} className="align-top">
                    <td className="px-3 py-2 text-gray-800">
                      {event.actor_username}
                    </td>
                    <td className="px-3 py-2 text-gray-700">
                      <div>
                        {event.event_type === "object_placed"
                          ? "Placed model"
                          : "Pinned building"}
                      </div>
                      <div className="text-xs text-gray-400">
                        {event.payload?.label?.trim() || eventPlaceText(event)}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-500">
                      {formatDateTime(event.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === "growth" && growth !== null && (
          <div>
            <p className="text-sm text-gray-600">
              <span className="text-2xl font-semibold text-gray-900">
                {growth.total}
              </span>{" "}
              model{growth.total === 1 ? "" : "s"} placed all-time
            </p>
            <p className="mb-3 mt-1 text-xs text-gray-400">
              Daily placements (bars) and cumulative total (line), last 30 days.
            </p>
            <GrowthChart growth={growth} />
          </div>
        )}

        {activeTab === "discover" && places !== null && (
          <ul className="space-y-2">
            {places.length === 0 && (
              <li className="text-sm text-gray-500">
                No places to explore yet. Add the first model to this map.
              </li>
            )}
            {places.map((place) => (
              <li key={place.map_object_id}>
                <button
                  type="button"
                  onClick={() => onFlyToPlace(place)}
                  className="w-full rounded-md border border-gray-200 px-3 py-2.5 text-left transition hover:border-blue-300 hover:bg-blue-50"
                >
                  <div className="text-sm font-medium text-gray-800">
                    {place.label?.trim() || "Unnamed place"}
                  </div>
                  <div className="mt-0.5 text-xs text-gray-400">
                    {place.contributor_username
                      ? `Added by ${place.contributor_username} · `
                      : ""}
                    {formatRelativeTime(place.created_at)}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default SocialPanel;
