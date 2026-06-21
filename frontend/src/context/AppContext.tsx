import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useNavigate } from "react-router-dom";
import {
  clearActiveGroupId,
  getActiveGroupId,
  onActiveGroupChange,
  setActiveGroupId,
} from "../lib/activeGroup";
import {
  getCurrentUser,
  listMyGroups,
  UnauthorizedError,
} from "../lib/api";
import {
  clearAuthToken,
  isLoggedIn,
  onAuthChange,
} from "../lib/auth";
import type { GroupResponse, UserResponse } from "../lib/types";

type AppContextValue = {
  user: UserResponse | null;
  groups: GroupResponse[];
  activeGroupId: string | null;
  activeGroup: GroupResponse | null;
  isBootstrapping: boolean;
  isGroupsLoading: boolean;
  refreshUser: () => Promise<void>;
  refreshGroups: () => Promise<void>;
  selectGroup: (groupId: string) => void;
  logout: () => void;
};

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [user, setUser] = useState<UserResponse | null>(null);
  const [groups, setGroups] = useState<GroupResponse[]>([]);
  const [activeGroupId, setActiveGroupIdState] = useState<string | null>(
    getActiveGroupId,
  );
  const [hasToken, setHasToken] = useState(isLoggedIn);
  const [isBootstrapping, setIsBootstrapping] = useState(isLoggedIn());
  const [isGroupsLoading, setIsGroupsLoading] = useState(false);

  const activeGroup = useMemo(
    () => groups.find((group) => group.id === activeGroupId) ?? null,
    [groups, activeGroupId],
  );

  const refreshUser = useCallback(async () => {
    if (!isLoggedIn()) {
      setUser(null);
      return;
    }

    try {
      const currentUser = await getCurrentUser();
      setUser(currentUser);
    } catch (error) {
      if (error instanceof UnauthorizedError) {
        clearAuthToken();
        clearActiveGroupId();
        setUser(null);
        setGroups([]);
        setActiveGroupIdState(null);
        navigate("/login");
      }
      throw error;
    }
  }, [navigate]);

  const refreshGroups = useCallback(async () => {
    if (!isLoggedIn()) {
      setGroups([]);
      return;
    }

    setIsGroupsLoading(true);
    try {
      const myGroups = await listMyGroups();
      setGroups(myGroups);

      const storedId = getActiveGroupId();
      if (storedId && !myGroups.some((group) => group.id === storedId)) {
        clearActiveGroupId();
        setActiveGroupIdState(null);
      }
    } catch (error) {
      if (error instanceof UnauthorizedError) {
        clearAuthToken();
        clearActiveGroupId();
        setUser(null);
        setGroups([]);
        setActiveGroupIdState(null);
        navigate("/login");
      }
      throw error;
    } finally {
      setIsGroupsLoading(false);
    }
  }, [navigate]);

  const selectGroup = useCallback((groupId: string) => {
    setActiveGroupId(groupId);
    setActiveGroupIdState(groupId);
    navigate("/app");
  }, [navigate]);

  const logout = useCallback(() => {
    clearAuthToken();
    clearActiveGroupId();
    setUser(null);
    setGroups([]);
    setActiveGroupIdState(null);
    navigate("/login");
  }, [navigate]);

  useEffect(() => {
    return onAuthChange(() => {
      const loggedIn = isLoggedIn();
      setHasToken(loggedIn);
      if (!loggedIn) {
        setUser(null);
        setGroups([]);
        setActiveGroupIdState(null);
        setIsBootstrapping(false);
      }
    });
  }, []);

  useEffect(() => {
    return onActiveGroupChange(() => {
      setActiveGroupIdState(getActiveGroupId());
    });
  }, []);

  useEffect(() => {
    if (!hasToken) {
      setIsBootstrapping(false);
      return;
    }

    let cancelled = false;

    async function bootstrap() {
      setIsBootstrapping(true);
      try {
        await refreshUser();
        if (!cancelled) {
          await refreshGroups();
        }
      } catch {
        // refreshUser/refreshGroups handle 401 redirects
      } finally {
        if (!cancelled) {
          setIsBootstrapping(false);
        }
      }
    }

    void bootstrap();

    return () => {
      cancelled = true;
    };
  }, [hasToken, refreshUser, refreshGroups]);

  const value = useMemo<AppContextValue>(
    () => ({
      user,
      groups,
      activeGroupId,
      activeGroup,
      isBootstrapping,
      isGroupsLoading,
      refreshUser,
      refreshGroups,
      selectGroup,
      logout,
    }),
    [
      user,
      groups,
      activeGroupId,
      activeGroup,
      isBootstrapping,
      isGroupsLoading,
      refreshUser,
      refreshGroups,
      selectGroup,
      logout,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp must be used within an AppProvider");
  }
  return context;
}
