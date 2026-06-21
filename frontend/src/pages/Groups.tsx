import { FormEvent, useEffect, useState } from "react";
import { ApiError, createGroup, joinGroup } from "../lib/api";
import { useApp } from "../context/AppContext";
import type { GroupResponse } from "../lib/types";

const GROUP_NAME_MIN = 1;
const GROUP_NAME_MAX = 100;

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function GroupCard({
  group,
  isOwner,
  onSelect,
}: {
  group: GroupResponse;
  isOwner: boolean;
  onSelect: () => void;
}) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div>
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold">{group.name}</h3>
          {isOwner && (
            <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
              Owner
            </span>
          )}
        </div>
        <p className="text-sm text-gray-500">Created {formatDate(group.created_at)}</p>
      </div>
      <button
        type="button"
        onClick={onSelect}
        className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700"
      >
        Enter
      </button>
    </div>
  );
}

function Groups() {
  const { user, groups, isGroupsLoading, refreshGroups, selectGroup } = useApp();

  const [createName, setCreateName] = useState("");
  const [createError, setCreateError] = useState("");
  const [createSubmitting, setCreateSubmitting] = useState(false);

  const [inviteCode, setInviteCode] = useState("");
  const [joinError, setJoinError] = useState("");
  const [joinSubmitting, setJoinSubmitting] = useState(false);

  useEffect(() => {
    void refreshGroups();
  }, [refreshGroups]);

  const isCreateValid =
    !createSubmitting &&
    createName.trim().length >= GROUP_NAME_MIN &&
    createName.trim().length <= GROUP_NAME_MAX;

  const isJoinValid = !joinSubmitting && inviteCode.trim().length > 0;

  async function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!isCreateValid) {
      return;
    }

    setCreateError("");
    setCreateSubmitting(true);
    try {
      const group = await createGroup({ name: createName.trim() });
      await refreshGroups();
      setCreateName("");
      selectGroup(group.id);
    } catch (error) {
      if (error instanceof ApiError) {
        setCreateError(error.message);
      } else {
        setCreateError("Unable to reach the server. Please try again.");
      }
    } finally {
      setCreateSubmitting(false);
    }
  }

  async function handleJoin(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!isJoinValid) {
      return;
    }

    setJoinError("");
    setJoinSubmitting(true);
    try {
      await joinGroup({ invite_code: inviteCode.trim() });
      await refreshGroups();
      setInviteCode("");
    } catch (error) {
      if (error instanceof ApiError) {
        setJoinError(error.message);
      } else {
        setJoinError("Unable to reach the server. Please try again.");
      }
    } finally {
      setJoinSubmitting(false);
    }
  }

  return (
    <div className="h-full overflow-y-auto bg-gray-100">
      <div className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-10">
        <header>
          <h1 className="text-3xl font-bold">Your Groups</h1>
          {user && (
            <p className="mt-1 text-gray-600">
              Signed in as <span className="font-medium">{user.username}</span>
            </p>
          )}
        </header>

        <section className="flex flex-col gap-4">
          <h2 className="text-xl font-semibold">Groups you belong to</h2>

          {isGroupsLoading ? (
            <p className="text-gray-600">Loading groups...</p>
          ) : groups.length === 0 ? (
            <div className="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center">
              <p className="text-gray-600">
                You&apos;re not in any groups yet. Create one below or join with an
                invite code.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {groups.map((group) => (
                <GroupCard
                  key={group.id}
                  group={group}
                  isOwner={user?.id === group.owner_id}
                  onSelect={() => selectGroup(group.id)}
                />
              ))}
            </div>
          )}
        </section>

        <section className="rounded-xl bg-white p-6 shadow-lg">
          <h2 className="mb-4 text-xl font-semibold">Create a group</h2>
          <form onSubmit={handleCreate} noValidate className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <label htmlFor="group-name" className="font-medium">
                Group name
              </label>
              <input
                id="group-name"
                type="text"
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                maxLength={GROUP_NAME_MAX}
                className="rounded-md border p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="My exploration crew"
                required
              />
              <p className="text-sm text-gray-500">
                {createName.length}/{GROUP_NAME_MAX}
              </p>
            </div>

            {createError && (
              <p className="text-sm text-red-600">{createError}</p>
            )}

            <button
              type="submit"
              disabled={!isCreateValid}
              className="rounded-md bg-blue-600 py-2 text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {createSubmitting ? "Creating..." : "Create group"}
            </button>
          </form>
        </section>

        <section className="rounded-xl bg-white p-6 shadow-lg">
          <h2 className="mb-4 text-xl font-semibold">Join with invite code</h2>
          <form onSubmit={handleJoin} noValidate className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <label htmlFor="invite-code" className="font-medium">
                Invite code
              </label>
              <input
                id="invite-code"
                type="text"
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value)}
                className="rounded-md border p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Paste invite code"
                required
              />
            </div>

            {joinError && <p className="text-sm text-red-600">{joinError}</p>}

            <button
              type="submit"
              disabled={!isJoinValid}
              className="rounded-md bg-gray-800 py-2 text-white transition hover:bg-gray-900 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {joinSubmitting ? "Joining..." : "Join group"}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}

export default Groups;
